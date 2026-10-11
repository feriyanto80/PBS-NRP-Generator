"""v1.0.6 engineering drawing renderer.

Road edge offsets are SCHEMATIC when OSM width is not supplied:
they are not surveyed road boundaries. Buildings come from real OSM polygons.
"""
import math

import ezdxf
from reportlab.pdfgen import canvas as pdfcanvas

from app import COLORS, viewport
from road_topology import build_road_surfaces, iter_road_boundaries

DEFAULT_ROAD_WIDTH_M = 5.5
ROAD_COLOR = (0.66, 0.66, 0.66)
BUILDING_STROKE = (0.51, 0.55, 0.61)
BUILDING_FILL = (0.946, 0.955, 0.967)


def _polyline_offsets(points, halfwidth):
    """Return two polylines offset using bounded miter joins."""
    if len(points) < 2:
        return [], []
    clean = [tuple(map(float, points[0]))]
    for item in points[1:]:
        p = tuple(map(float, item))
        if math.hypot(p[0]-clean[-1][0], p[1]-clean[-1][1]) > 1e-9:
            clean.append(p)
    if len(clean) < 2:
        return [], []
    normals = []
    for p, q in zip(clean, clean[1:]):
        dx, dy = q[0]-p[0], q[1]-p[1]
        d = math.hypot(dx, dy)
        normals.append((-dy/d, dx/d))
    left, right = [], []
    for i, (x, y) in enumerate(clean):
        if i == 0:
            nx, ny = normals[0]
            strength = 1.0
        elif i == len(clean)-1:
            nx, ny = normals[-1]
            strength = 1.0
        else:
            a, b = normals[i-1], normals[i]
            sx, sy = a[0]+b[0], a[1]+b[1]
            mag = math.hypot(sx, sy)
            if mag < 0.1:
                nx, ny, strength = b[0], b[1], 1.0
            else:
                nx, ny = sx/mag, sy/mag
                strength = min(2.2, 1/max(.45, abs(nx*b[0]+ny*b[1])))
        left.append((x+nx*halfwidth*strength, y+ny*halfwidth*strength))
        right.append((x-nx*halfwidth*strength, y-ny*halfwidth*strength))
    return left, right


def _pdf_path(c, points, closed=False, fill=0):
    if len(points) < (3 if closed else 2):
        return
    p = c.beginPath()
    p.moveTo(*points[0])
    for xy in points[1:]:
        p.lineTo(*xy)
    if closed:
        p.close()
    c.drawPath(p, stroke=1, fill=fill)


def _roads(osm):
    widths = osm.get("road_widths") or []
    for i, pts in enumerate(osm.get("roads", [])):
        if len(pts) < 2:
            continue
        try:
            w = float(widths[i]) if i < len(widths) else DEFAULT_ROAD_WIDTH_M
        except (TypeError, ValueError):
            w = DEFAULT_ROAD_WIDTH_M
        yield pts, max(1.5, min(w, 24.0))


def _paper_halfwidth(xy, geographic_point, width_m):
    lon, lat = geographic_point
    p0 = xy((lon, lat))
    p1 = xy((lon, min(89.9999, lat + (width_m/2)/111320.0)))
    # Prevent complete road disappearance on overview and unrealistic fat roads.
    return max(.37, min(5.0, math.hypot(p1[0]-p0[0], p1[1]-p0[1])))


def draw_osm_pdf(c, osm, xy):
    """Render clean road corridors, erasing internal overlapping offset seams.

    Joined buffers make all T/X junctions and bends one contiguous road surface,
    so only outside contours are stroked. Draw buildings first, then white road
    pavement, then overlay the FTTH cable separately in draw_pdf().
    """
    if not osm:
        return
    c.saveState()
    c.setLineJoin(1)
    c.setLineCap(1)
    c.setStrokeColorRGB(*BUILDING_STROKE)
    c.setFillColorRGB(*BUILDING_FILL)
    c.setLineWidth(.30)
    for geo in osm.get("buildings", []):
        if len(geo) >= 3:
            _pdf_path(c, [xy(p) for p in geo], closed=True, fill=1)
    c.setStrokeColorRGB(*ROAD_COLOR)
    c.setFillColorRGB(1.0, 1.0, 1.0)
    c.setLineWidth(.43)
    for polygon in build_road_surfaces(osm):
        path = c.beginPath()
        for ring in [polygon["exterior"]] + polygon["holes"]:
            pts = [xy(pt) for pt in ring]
            if len(pts) < 4:
                continue
            path.moveTo(*pts[0])
            for xy0 in pts[1:]:
                path.lineTo(*xy0)
            path.close()
        # Even-odd winding preserves inner land-island holes.
        c.drawPath(path, stroke=1, fill=1, fillMode=0)
    c.restoreState()

def _text_fit(c, text, x, y, width, size=8, bold=False, align="left"):
    label = str(text or "")
    font = "Helvetica-Bold" if bold else "Helvetica"
    while size > 5.0 and c.stringWidth(label, font, size) > width:
        size -= .35
    if c.stringWidth(label, font, size) > width:
        while label and c.stringWidth(label+"...",font,size) > width:
            label=label[:-1]
        label += "..."
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x + width/2, y, label)
    else:
        c.drawString(x, y, label)


def _draw_titleblock(c, x, y, w, h, title, sheetname, index, count, osm):
    c.saveState()
    c.setStrokeColorRGB(.50,.50,.50)
    c.setFillColorRGB(.16,.16,.16)
    c.setLineWidth(.55)
    c.rect(x,y,w,h)
    top=y+h
    c.line(x,top-34,x+w,top-34)
    _text_fit(c,"AS BUILT DRAWING",x+5,top-15,w-10,11,bold=True,align="center")
    _text_fit(c,"NETWORK ROUTE PLAN",x+5,top-27,w-10,7,align="center")
    symbols=[
        ("NEW POLE","T","orange"),
        ("EXISTING POLE","T","black"),
        ("ODC","△","red"),
        ("ODP 8 HP","△","blue"),
        ("ODP 16 HP","△","orange"),
        ("ODP 24 HP","△","magenta"),
        ("CLOSURE","◇","red"),
        ("HOME PASS","●","gold"),
        ("FEEDER 96C","━","red"),
        ("SUBFEEDER","━","purple"),
        ("DISTRIBUTION","━","magenta"),
        ("ROAD EDGE","━","gray"),
        ("BUILDING FOOTPRINT","□","gray"),
    ]
    legends_top=top-48
    c.setFont("Helvetica-Bold",7)
    c.drawCentredString(x+w/2,legends_top,"LEGEND & CABLE TYPE")
    cursor=legends_top-10
    stroke_colors={"red":(0.91,.15,.15),"orange":(1,.35,.08),
                   "blue":(.08,.22,.9),"magenta":(.92,.17,.56),
                   "purple":(.54,.17,.72),"gray":(.60,.60,.60),
                   "gold":(.87,.66,.03),"black":(.22,.22,.22)}
    for label,symbol,color in symbols:
        c.setStrokeColorRGB(.86,.86,.86)
        c.line(x,cursor-5,x+w,cursor-5)
        c.setFillColorRGB(*stroke_colors[color])
        c.setFont("Helvetica-Bold",7)
        try:
            if symbol in ("△","◇","●"):
                c.circle(x+9,cursor+.5,3,stroke=1,fill=1 if symbol=="●" else 0)
            elif symbol=="━":
                c.setStrokeColorRGB(*stroke_colors[color])
                c.setLineWidth(1.2)
                c.line(x+4,cursor+1,x+17,cursor+1)
            else:
                c.drawString(x+7,cursor-1,symbol if ord(symbol[0])<128 else "*")
        except ValueError:
            pass
        c.setFillColorRGB(.17,.17,.17)
        _text_fit(c,label,x+21,cursor-1,w-24,6.6)
        cursor-=19
    sep=max(y+175,cursor-8)
    c.setStrokeColorRGB(.50,.50,.50)
    c.line(x,sep,x+w,sep)
    c.setFillColorRGB(.12,.32,.56)
    _text_fit(c,"STARLITE  /  PBS",x+6,sep-24,w-12,13,bold=True,align="center")
    c.setFillColorRGB(.18,.18,.18)
    c.line(x,sep-34,x+w,sep-34)
    _text_fit(c,"PROJECT / DRAWING",x+6,sep-46,w-12,7,bold=True)
    _text_fit(c,title,x+6,sep-59,w-12,7)
    _text_fit(c,sheetname,x+6,sep-72,w-12,7,bold=True)
    c.line(x,sep-81,x+w,sep-81)
    _text_fit(c,"SOURCE: KML/KMZ + OpenStreetMap",x+6,sep-94,w-12,6)
    _text_fit(c,"ROAD OFFSET: SCHEMATIC / NOT SURVEYED",x+6,sep-107,w-12,5.3)
    info=("NO OSM - MAP INCOMPLETE" if not osm else
          "OSM PARTIAL - CHECK COVERAGE" if osm.get("partial") else
          f"OSM: {len(osm.get('roads',[]))} roads, {len(osm.get('buildings',[]))} buildings")
    _text_fit(c,info,x+6,sep-120,w-12,6,bold=True)
    c.line(x,y+49,x+w,y+49)
    _text_fit(c,"SCALE: N.T.S.",x+6,y+33,w-12,6.4)
    _text_fit(c,f"SHEET {index+1} OF {count}",x+6,y+20,w-12,7,bold=True)
    _text_fit(c,"N",x+w-24,y+32,15,9,bold=True)
    c.line(x+w-19,y+14,x+w-19,y+28)
    c.restoreState()


def draw_pdf(path,lines,points,project,page_w,page_h,title,sheets,osm=None):
    """A3 5-sheet engineering PDF with real building polygons and road edges."""
    c=pdfcanvas.Canvas(path,pagesize=(page_w,page_h))
    sidebar=177
    x0,y0=22,21
    map_w=page_w-sidebar-49
    map_h=page_h-43
    bx=x0+map_w+4
    for idx,(sheetname,bb) in enumerate(sheets):
        c.setStrokeColorRGB(.22,.22,.22)
        c.setLineWidth(.7)
        c.rect(13,13,page_w-26,page_h-26)
        c.setLineWidth(.32)
        c.rect(18,18,page_w-36,page_h-36)
        c.setStrokeColorRGB(.6,.6,.6)
        c.setLineWidth(.48)
        c.rect(x0,y0,map_w,map_h)
        tr=viewport(bb,map_w,map_h,12)
        def xy(p):
            xx,yy=tr(p)
            return x0+xx,y0+yy
        c.saveState()
        p=c.beginPath()
        p.rect(x0+1,y0+1,map_w-2,map_h-2)
        c.clipPath(p,stroke=0)
        draw_osm_pdf(c,osm,xy)
        for name,cat,geo in lines:
            c.setStrokeColor(COLORS.get(cat,COLORS["DISTRIBUSI"]))
            c.setLineWidth(1.15 if cat=="FEEDER" else .50)
            _pdf_path(c,[xy(pt) for pt in geo])
        # Point symbology configured in Pemetaan & Simbol.
        style=(osm or {}).get("_drawing_style",{})
        symbol=str(style.get("point_shape","Circle"))
        radius=float(style.get("point_size",2.0))
        show_labels=bool(style.get("point_labels",True))
        c.setFont("Helvetica",4.0)
        for name,geo in points:
            x,y=xy(geo)
            c.setFillColorRGB(.95,.75,.10)
            c.setStrokeColorRGB(.17,.17,.17)
            if symbol=="Square":
                c.rect(x-radius,y-radius,2*radius,2*radius,stroke=1,fill=1)
            elif symbol=="Triangle":
                mark=c.beginPath()
                mark.moveTo(x,y+radius*1.2)
                mark.lineTo(x-radius*1.2,y-radius)
                mark.lineTo(x+radius*1.2,y-radius)
                mark.close()
                c.drawPath(mark,stroke=1,fill=1)
            else:
                c.circle(x,y,radius,stroke=1,fill=1)
            if idx>0 and show_labels and name:
                c.setFillColorRGB(.13,.13,.13)
                c.drawString(x+radius+1,y+1.2,name[:20])
        c.restoreState()
        _draw_titleblock(c,bx,y0,sidebar-1,map_h,title,sheetname,idx,len(sheets),osm)
        c.showPage()
    c.save()


def draw_dxf(path,lines,points,sheets,osm=None):
    """Projected-meter DXF: two road edges + closed building footprint polylines."""
    doc=ezdxf.new("R2010")
    m=doc.modelspace()
    for name,color in [("FEEDER",1),("SUBFEEDER",200),("DISTRIBUSI",6),
                       ("POINTS",2),("LABELS",7),("OSM_ROAD_EDGES",8),
                       ("OSM_BUILDING_FOOTPRINT",9)]:
        doc.layers.new(name,dxfattribs={"color":color})
    R=6378137.0
    def metric(pt):
        lon,lat=pt
        lat=max(-85,min(85,lat))
        return (R*math.radians(lon), R*math.log(math.tan(math.pi/4+math.radians(lat)/2)))
    if osm:
        for geo in osm.get("buildings",[]):
            if len(geo)>=3:
                m.add_lwpolyline([metric(p) for p in geo],close=True,
                                 dxfattribs={"layer":"OSM_BUILDING_FOOTPRINT"})
        # One closed boundary per joined road contour; no double seams at junctions.
        for geo in iter_road_boundaries(osm):
            if len(geo) >= 4:
                m.add_lwpolyline([metric(p) for p in geo],close=True,
                                 dxfattribs={"layer":"OSM_ROAD_EDGES"})
    for name,cat,geo in lines:
        m.add_lwpolyline([metric(p) for p in geo],
                         dxfattribs={"layer":cat if cat in COLORS else "DISTRIBUSI"})
    style=(osm or {}).get("_drawing_style",{})
    shape=str(style.get("point_shape","Circle"))
    radius=float(style.get("point_size",2.0))
    labels=bool(style.get("point_labels",True))
    for name,geo in points:
        x,y=metric(geo)
        if shape=="Square":
            vertices=[(x-radius,y-radius),(x+radius,y-radius),
                      (x+radius,y+radius),(x-radius,y+radius)]
            m.add_lwpolyline(vertices,close=True,dxfattribs={"layer":"POINTS"})
        elif shape=="Triangle":
            vertices=[(x,y+radius*1.2),(x-radius*1.2,y-radius),
                      (x+radius*1.2,y-radius)]
            m.add_lwpolyline(vertices,close=True,dxfattribs={"layer":"POINTS"})
        else:
            m.add_circle((x,y),radius,dxfattribs={"layer":"POINTS"})
        if labels and name:
            m.add_text(name[:64],dxfattribs={"height":1.5,"insert":(x+radius+1,y+radius+1),"layer":"LABELS"})
    doc.header["$INSUNITS"]=6
    doc.saveas(path)


def draw_preview(canvas,bb,lines,points,osm,mainmap):
    """OSM styling matches the PDF: building polygons and dual road edges."""
    canvas.delete("all")
    w=max(canvas.winfo_width(),200)
    h=max(canvas.winfo_height(),200)
    if not lines and not points:
        canvas.create_text(w/2,h/2,text="Import KML/KMZ untuk melihat jaringan",fill="#667788")
        return
    tr=viewport(bb,w,h,18)
    def xy(p):
        x,y=tr(p)
        return x,h-y
    if osm:
        # True polygon footprint when zoom allows it. For sub-pixel buildings,
        # show a small footprint locator rather than an invisible hairline.
        # Locators are display-only and are not exported to engineering PDF/DXF.
        in_view=0
        displayed=0
        for geo in osm.get("buildings",[]):
            if len(geo)<3:
                continue
            plotted=[xy(pt) for pt in geo]
            xs=[p[0] for p in plotted]
            ys=[p[1] for p in plotted]
            if max(xs)<0 or min(xs)>w or max(ys)<0 or min(ys)>h:
                continue
            in_view+=1
            if max(xs)-min(xs)<1.5 or max(ys)-min(ys)<1.5:
                cx=(min(xs)+max(xs))/2
                cy=(min(ys)+max(ys))/2
                canvas.create_rectangle(cx-1.1,cy-1.1,cx+1.1,cy+1.1,
                                        fill="#607c95",outline="")
            else:
                coords=[v for pt in plotted for v in pt]
                canvas.create_polygon(*coords,fill="#e1eaf1",
                                      outline="#627f95",width=1.0)
            displayed+=1
        if mainmap:
            canvas.create_text(14,14,anchor="nw",
                               text=f"Footprint: {in_view:,} terlihat dari {len(osm.get('buildings',[])):,} terkonfirmasi",
                               font=("Segoe UI",8,"bold"),fill="#244f70")
        # Preview uses the same polygon topology as PDF and DXF.
        for polygon in build_road_surfaces(osm):
            exterior = [coordinate for pt in polygon["exterior"] for coordinate in xy(pt)]
            if len(exterior) >= 8:
                canvas.create_polygon(*exterior,fill="#ffffff",outline="#949494",width=.85)
            for ring in polygon["holes"]:
                pts=[coordinate for pt in ring for coordinate in xy(pt)]
                if len(pts) >= 8:
                    canvas.create_line(*pts,fill="#949494",width=.85)
    for name,cat,geo in lines:
        coords=[v for pt in geo for v in xy(pt)]
        if len(coords)>=4:
            canvas.create_line(*coords,fill=COLORS.get(cat,COLORS["DISTRIBUSI"]),
                               width=2 if cat=="FEEDER" else 1)
    style=(osm or {}).get("_drawing_style",{})
    radius=float(style.get("point_size",2.0))
    mark=str(style.get("point_shape","Circle"))
    if mainmap:
        for name,p in points:
            x,y=xy(p)
            if -5<x<w+5 and -5<y<h+5:
                if mark=="Square":
                    canvas.create_rectangle(x-radius,y-radius,x+radius,y+radius,
                                            fill="#ffcf32",outline="#333")
                elif mark=="Triangle":
                    canvas.create_polygon(x,y-radius*1.3,
                                          x-radius*1.2,y+radius,
                                          x+radius*1.2,y+radius,
                                          fill="#ffcf32",outline="#333")
                else:
                    canvas.create_oval(x-radius,y-radius,x+radius,y+radius,
                                       fill="#ffcf32",outline="#333")
    canvas.create_rectangle(4,4,w-4,h-4,outline="#555")
    canvas.create_rectangle(8,8,w-8,h-8,outline="#aaa")
