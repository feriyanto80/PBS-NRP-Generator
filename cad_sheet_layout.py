"""Reference-style editable A3 paper-space sheets for generated DXF/DWG.

Template derived from the provided Lemah Abang engineering PDF/DWG reference:
A3 landscape; main plan drawing; right title block; 2-column pole/ODP/closure
legend; cable-type lines; revision grid; dynamic project fields; blank sign-offs;
scale N.T.S. and compass. Original proprietary DWG AC1032 internals are NOT
claimed to be parsed or reproduced byte-for-byte.
"""
import math
import re

A3_W_MM = 420.0
A3_H_MM = 297.0
FRAME_MARGIN = 5.5
SIDEBAR_X = 351.0
SIDEBAR_W = 63.0
TOP = 291.5
BOTTOM = 5.5
MAP_LEFT = 7.0
MAP_RIGHT = SIDEBAR_X - 1.0
MAP_BOTTOM = 7.0
MAP_TOP = 290.0

LEGEND_LEFT = [
    ("NEW POLE 6", 2, "POLE", "T6"),
    ("NEW POLE 7", 7, "POLE", "T7"),
    ("NEW POLE 9", 5, "POLE", "T9"),
    ("NEW POLE 6", 30, "POLE", "TL"),
    ("EXISTING POLE", 8, "POLE", "TE"),
    ("NEW ODC", 1, "TRI", ""),
    ("EXISTING ODC", 9, "TRI", ""),
    ("NEW ODP 8 HP", 5, "TRI", ""),
    ("NEW ODP 16 HP", 30, "TRI", ""),
    ("NEW ODP 24 HP", 6, "TRI", ""),
    ("EXISTING ODP", 7, "TRI", ""),
]
LEGEND_RIGHT = [
    ("EXISTING CLOSURE", 7, "BOW", ""),
    ("NEW CLOSURE", 1, "BOW", ""),
    ("NEW COIL", 1, "COIL", ""),
    ("EXISTING COIL", 8, "COIL", ""),
    ("OPTIC DISTRIBUTION TERMINAL", 5, "BOX", "ODT"),
    ("OTHER HANDHOLE", 30, "BOX", "HH"),
    ("NEW HANDHOLE", 5, "BOX", "HH"),
    ("EXISTING HANDHOLE", 7, "BOX", ""),
    ("BORING ALUR", 1, "LINE", ""),
    ("CROSSING BRIDGE", 8, "LINE", ""),
    ("BORING CROSSING", 1, "COIL", ""),
]
CABLE_LEFT = [
    ("DROPWIRE 1 CORE", 6),
    ("AERIAL STRAND", 8),
    ("UNDERGROUND STRAND", 3),
    ("UG DROP DUCT", 5),
    ("FEEDER CABLE ROUTE", 8),
    ("RAIL WAY", 7),
    ("SEWER LINE", 6),
]
CABLE_RIGHT = [
    ("FIBER 12/2T", 1),
    ("FIBER 24/2T", 30),
    ("FIBER 48/4T", 5),
    ("FIBER 72/6T", 6),
    ("FIBER 96/8T", 1),
    ("FIBER 144/12T", 3),
    ("FIBER 288/24T", 8),
]


def webmercator(point):
    lon,lat=map(float,point[:2])
    lat=max(-85.0,min(85.0,lat))
    r=6378137.0
    return (r*math.radians(lon), r*math.log(math.tan(math.pi/4+math.radians(lat)/2)))


def name_for_sheet(index,title):
    """Names are ASCII and <= 31 characters for DWG/Paperspace compatibility."""
    slug=re.sub(r"[^A-Za-z0-9]+","_",str(title)).strip("_").upper()
    return f"NRP_{index+1:02d}_{slug}"[:31]


def _build_tab(draw, project, sheetname, index, total, stats):
    """Vector title block primitives, all kept in edit-friendly CAD layers."""
    x,y,w,h = SIDEBAR_X,BOTTOM,SIDEBAR_W,TOP-BOTTOM
    mid=x+w*0.51

    def line(x1,y1,x2,y2,layer="NRP_TB_FRAME",color=None):
        attr={"layer":layer}
        if color is not None:attr["color"]=int(color)
        draw.add_line((x1,y1),(x2,y2),dxfattribs=attr)

    def box(x1,y1,x2,y2):
        draw.add_lwpolyline(
            [(x1,y1),(x2,y1),(x2,y2),(x1,y2)],
            close=True,dxfattribs={"layer":"NRP_TB_FRAME"})

    def text(label,x0,y0,height=1.45,bold=False,layer="NRP_TB_TEXT"):
        label=str(label or "").replace("\n"," ")
        if len(label)>64:
            label=label[:61]+"..."
        draw.add_text(label,dxfattribs={
            "layer":layer,"height":float(height),"insert":(x0,y0)})

    def marker(x0,y0,kind,color,short):
        attr={"layer":"NRP_TB_SYMBOL","color":int(color)}
        if kind=="TRI":
            draw.add_lwpolyline([(x0-1.3,y0-1.0),
                                 (x0+1.3,y0-1.0),(x0,y0+1.6)],
                                close=True,dxfattribs=attr)
        elif kind=="POLE":
            draw.add_circle((x0,y0),1.35,dxfattribs=attr)
            text(short,x0-1.0,y0-.52,.92,layer="NRP_TB_TEXT")
        elif kind=="BOX":
            boxpts=[(x0-1.45,y0-1.5),(x0+1.45,y0-1.5),
                    (x0+1.45,y0+1.5),(x0-1.45,y0+1.5)]
            draw.add_lwpolyline(boxpts,close=True,dxfattribs=attr)
            if short:
                text(short,x0-1.13,y0-.39,.7)
        elif kind=="BOW":
            draw.add_lwpolyline([(x0-1.5,y0+1),(x0,y0),
                                 (x0-1.5,y0-1)],dxfattribs=attr)
            draw.add_lwpolyline([(x0+1.5,y0+1),(x0,y0),
                                 (x0+1.5,y0-1)],dxfattribs=attr)
        elif kind=="COIL":
            for dx in (-.68,.68):
                draw.add_circle((x0+dx,y0),.8,dxfattribs=attr)
        else:
            line(x0-1.8,y0,x0+1.8,y0,"NRP_TB_SYMBOL",color)

    box(x,y,x+w,y+h)
    title_bottom=TOP-13.3
    line(x,title_bottom,x+w,title_bottom)
    text("AS BUILT DRAWING",x+3.0,TOP-8.7,4.15)

    # Fixed-style row ordering from the example title block.
    legend_row=6.8
    legend_bottom=title_bottom-11*legend_row
    line(mid,legend_bottom,mid,title_bottom)
    for i in range(11):
        upper=title_bottom-i*legend_row
        line(x,upper,x+w,upper)
        for sx,items in ((x,LEGEND_LEFT),(mid,LEGEND_RIGHT)):
            label,color,kind,short=items[i]
            marker(sx+3.5,upper-3.55,kind,color,short)
            max_len=24 if sx==x else 27
            text(label[:max_len],sx+7,upper-4.1,
                 1.24 if len(label)>18 else 1.55)
    line(x,legend_bottom,x+w,legend_bottom)

    cable_head=legend_bottom-5.6
    line(x,cable_head,x+w,cable_head)
    text("CABLE TYPE",x+20.0,legend_bottom-4.25,2.75)
    cable_row=4.4
    cable_bottom=cable_head-7*cable_row
    line(mid,cable_bottom,mid,cable_head)
    for i in range(7):
        rowtop=cable_head-i*cable_row
        line(x,rowtop,x+w,rowtop)
        for sx,end,entry in (
            (x,mid,CABLE_LEFT[i]),(mid,x+w,CABLE_RIGHT[i])
        ):
            label,color=entry
            text(label,sx+1.05,rowtop-2.95,1.09)
            line(end-12.5,rowtop-2.55,end-1.0,rowtop-2.55,
                 "NRP_TB_CABLE",color)
    line(x,cable_bottom,x+w,cable_bottom)

    logo_bottom=cable_bottom-24.5
    line(x,logo_bottom,x+w,logo_bottom)
    logo_x=x+w/2
    logo_y=logo_bottom+14
    from starlite_logo import starlite_logo
    # Traced original logo geometry; not the previous invented polygon.
    starlite_logo(draw,logo_x,logo_bottom+4.3,height=18.5)
    text("S T A R L I T E",logo_x-12.5,logo_bottom+3.0,2.3)

    revision_bottom=logo_bottom-19
    line(x,revision_bottom,x+w,revision_bottom)
    rev_1=x+w*.24
    rev_2=x+w*.79
    line(rev_1,revision_bottom,rev_1,logo_bottom)
    line(rev_2,revision_bottom,rev_2,logo_bottom)
    for j in range(1,4):
        yy=logo_bottom-j*4.75
        line(x,yy,x+w,yy)
    text("DATE",x+2.5,logo_bottom-3.4,1.7)
    text("REVISION",rev_1+5,logo_bottom-3.4,1.7)
    text("SIGN",rev_2+2.5,logo_bottom-3.4,1.7)

    proj_bottom=revision_bottom-21
    line(x,proj_bottom,x+w,proj_bottom)
    text("Nama Proyek / Project Name",x+2,revision_bottom-3.6,1.42)
    clean_project=str(project or "PBS NETWORK ROUTE PLAN").replace("_"," ")
    # Split very long project name within two editable text rows.
    text(clean_project[:48],x+2,revision_bottom-9,1.55)
    if len(clean_project)>48:
        text(clean_project[48:96],x+2,revision_bottom-13,1.55)
    text("Tipe Gambar / Drawing Type",x+2,proj_bottom+5.2,1.42)
    text("AS PLAN DRAWING - "+str(sheetname)[:30],x+2,proj_bottom+1.7,1.5)

    sign_bottom=proj_bottom-11
    line(x,sign_bottom,x+w,sign_bottom)
    text("DRAWING SIGN & CHECK",x+8.5,proj_bottom-5,2.35)
    text("Created by: __________  Checked by: __________",
         x+2,sign_bottom+2.3,1.35)

    company_bottom=sign_bottom-9.0
    line(x,company_bottom,x+w,company_bottom)
    text("PROJECT CONTROL / APPROVAL",x+8,sign_bottom-5.6,1.85)

    approvals_bottom=company_bottom-34.0
    line(x,approvals_bottom,x+w,approvals_bottom)
    line(mid,approvals_bottom,mid,company_bottom)
    line(x,approvals_bottom+17,x+w,approvals_bottom+17)
    roles=(
        ("Dibuat Oleh / Created by","Survey & Design"),
        ("Diperiksa Oleh / Checked by","Project Manager"),
        ("Disetujui Oleh / Approved by","Quality Control"),
        ("Diketahui Oleh / Verified by","Owner / Client"),
    )
    for i,(label,role) in enumerate(roles):
        ax=x if i%2==0 else mid
        ay=company_bottom-17*(i//2)
        text(label,ax+1.4,ay-3.3,1.6)
        text(role,ax+1.4,ay-6.7,1.4)
        text("__________________",ax+1.4,ay-13.0,1.4)

    # Remaining space: section-level footer, reference, north and pagination.
    footer_top=approvals_bottom
    footer_bottom=y
    if footer_top-footer_bottom<10:
        return
    foot_mid=x+w*.49
    line(foot_mid,footer_bottom,foot_mid,footer_top)
    line(foot_mid,footer_bottom+14, x+w,footer_bottom+14)
    text("Ref. Peta / Map Ref.",x+1.5,footer_top-3.5,1.55)
    text("Arah / Direction",x+1.5,footer_top-11,1.3)
    north=(x+16,footer_bottom+10)
    line(north[0],north[1]-6,north[0],north[1]+7,"NRP_TB_COMPASS",7)
    line(north[0]-6,north[1],north[0]+6,north[1],"NRP_TB_COMPASS",7)
    text("N",north[0]-.8,north[1]+8.1,1.9)
    text("S",north[0]-.8,north[1]-9.0,1.9)
    text("No. Gambar / Drawing No.",foot_mid+1.5,footer_top-3.5,1.22)
    text(f"NRP-{index+1:02d}",foot_mid+1.5,footer_top-7,1.8)
    text("Skala / Scale : N.T.S.",foot_mid+1.5,footer_bottom+9.0,1.55)
    text(f"Halaman / Page : {index+1} OF {total}",foot_mid+1.5,footer_bottom+3.0,1.5)


def attach_a3_layouts(doc,sheets,project_name="",osm=None):
    """Build one editable A3 paper-space layout and viewport PER NRP PDF sheet.

    ModelSpace stays geographic/projected in metres, PaperSpace is millimetres.
    Native DWG is still produced only via ODA converter installed/licensed by user.
    """
    for name,aci in [
        ("NRP_TB_FRAME",8),("NRP_TB_TEXT",7),
        ("NRP_TB_SYMBOL",7),("NRP_TB_CABLE",7),
        ("NRP_TB_COMPASS",7),("NRP_TB_LOGO",5),
        ("NRP_SHEET_BORDER",8),("NRP_VIEWPORT",8),
    ]:
        if name not in doc.layers:
            doc.layers.new(name,dxfattribs={"color":aci})
    for style,font in (
        ("NRP_REFERENCE_ROMANS","romans.shx"),
        ("NRP_REFERENCE_TAHOMA","tahoma.ttf"),
    ):
        if style not in doc.styles:
            doc.styles.new(style,dxfattribs={"font":font})
    ids=[]
    for i,(title,extent) in enumerate(sheets):
        name=name_for_sheet(i,title)
        if name in doc.layouts:
            name=f"NRP_{i+1:02d}_DETAIL"
        layout=doc.layouts.new(name)
        layout.page_setup(
            size=(A3_W_MM,A3_H_MM),units="mm",
            margins=(0,0,0,0),name="ISO_A3_LANDSCAPE",
            device="DWG To PDF.pc3"
        )
        layout.add_lwpolyline(
            [(FRAME_MARGIN,FRAME_MARGIN),
             (A3_W_MM-FRAME_MARGIN,FRAME_MARGIN),
             (A3_W_MM-FRAME_MARGIN,A3_H_MM-FRAME_MARGIN),
             (FRAME_MARGIN,A3_H_MM-FRAME_MARGIN)],
            close=True,dxfattribs={"layer":"NRP_SHEET_BORDER"})
        layout.add_lwpolyline(
            [(MAP_LEFT,MAP_BOTTOM),(MAP_RIGHT,MAP_BOTTOM),
             (MAP_RIGHT,MAP_TOP),(MAP_LEFT,MAP_TOP)],
            close=True,dxfattribs={"layer":"NRP_TB_FRAME"})
        # Keep paper-frame entities from the original Lemah Abang 2018 drawing.
        # Both PDF and DXF invoke precisely this drawing function.
        from original_frame import original_titleblock
        original_titleblock(layout,project_name,title,i,len(sheets),osm or {})
        from exact_template import find_reference, replace_cad_upper_titleblock
        reference_dxf=find_reference("dxf")
        if reference_dxf:
            # Imported original glyphs, hatch patterns and CAD font style:
            # only the static top, not historic project/approvals.
            replace_cad_upper_titleblock(doc,layout,reference_dxf)
        # Match A3 map viewport dimensions and fit the entire specified detail.
        xa,ya=webmercator((extent[0],extent[1]))
        xb,yb=webmercator((extent[2],extent[3]))
        cx,cy=(xa+xb)/2,(ya+yb)/2
        w=MAP_RIGHT-MAP_LEFT-3.0
        h=MAP_TOP-MAP_BOTTOM-3.0
        view_h=max((yb-ya)*1.055,(xb-xa)*h/w*1.055,1.0)
        vp=layout.add_viewport(
            center=((MAP_LEFT+MAP_RIGHT)/2,(MAP_BOTTOM+MAP_TOP)/2),
            size=(w,h),view_center_point=(cx,cy),
            view_height=view_h,status=2,
            dxfattribs={"layer":"NRP_VIEWPORT"}
        )
        try:
            vp.dxf.render_mode=0
        except Exception:
            pass
        ids.append(name)
    doc.header["$MEASUREMENT"]=1
    return ids
