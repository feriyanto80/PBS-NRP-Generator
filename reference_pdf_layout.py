"""Shared A3 drawing geometry for PDF and the editable DXF/DWG paper layouts.

A3 title block is rendered with EXACTLY the same cad_sheet_layout._build_tab()
geometry. This replaces the old independent PDF approximation. The PDF map
uses the same EPSG:3857 model/view transform and viewport sizing as the DXF.
Template conventions come from the user-supplied 2018 Lemah Abang sample:
AS BUILT DRAWING, dual symbol columns, cable matrix, revision/approval,
compass, A3 landscape and N.T.S.

DWG is still produced by an appropriately licensed local ODA installation.
"""
import math

from reportlab.pdfgen import canvas as pdfcanvas

from cad_sheet_layout import (
    A3_W_MM, A3_H_MM, FRAME_MARGIN, SIDEBAR_X,
    TOP, BOTTOM, MAP_LEFT, MAP_RIGHT, MAP_BOTTOM, MAP_TOP,
    _build_tab, webmercator,
)


def cad_rgb(aci):
    """The main palette from source AutoCAD 2018 ACI values."""
    palette={
        1:(.92,.08,.13), 2:(.98,.78,.04), 3:(.10,.69,.25),
        5:(.10,.27,.86), 6:(.80,.15,.73), 7:(.15,.15,.15),
        8:(.55,.55,.55), 9:(.78,.78,.78), 12:(.92,.33,.08),
        30:(1,.48,.05), 40:(.95,.74,.08), 190:(.07,.69,.94),
        210:(.49,.52,.82), 250:(.67,.67,.67),
        251:(.78,.78,.78), 255:(.63,.63,.63),
    }
    return palette.get(int(aci or 7),(.19,.19,.19))


class PDFCADAdapter:
    """Minimal ezdxf-layout interface implemented on a ReportLab canvas."""

    def __init__(self,c):
        self.c=c

    def _color(self, attrs=None):
        attrs=attrs or {}
        if attrs.get("true_color") is not None:
            packed=int(attrs["true_color"])
            return ((packed>>16&255)/255,(packed>>8&255)/255,(packed&255)/255)
        color=attrs.get("color")
        return cad_rgb(color if color is not None else 7)

    def add_line(self,a,b,dxfattribs=None):
        c=self.c
        c.saveState()
        c.setStrokeColorRGB(*self._color(dxfattribs))
        c.setLineWidth(.20)
        c.line(a[0],a[1],b[0],b[1])
        c.restoreState()

    def add_lwpolyline(self,vertices,close=False,dxfattribs=None):
        if not vertices:
            return
        c=self.c
        c.saveState()
        c.setStrokeColorRGB(*self._color(dxfattribs))
        c.setLineWidth(.20)
        p=c.beginPath()
        p.moveTo(*vertices[0][:2])
        for item in vertices[1:]:
            p.lineTo(*item[:2])
        if close:
            p.close()
        c.drawPath(p,stroke=1,fill=0)
        c.restoreState()

    def add_circle(self,center,radius,dxfattribs=None):
        c=self.c
        c.saveState()
        c.setStrokeColorRGB(*self._color(dxfattribs))
        c.setLineWidth(.25)
        c.circle(center[0],center[1],radius,stroke=1,fill=0)
        c.restoreState()

    def add_solid(self,points,dxfattribs=None):
        if len(points)<3:
            return
        c=self.c
        c.saveState()
        c.setFillColorRGB(*self._color(dxfattribs))
        c.setStrokeColorRGB(*self._color(dxfattribs))
        p=c.beginPath()
        p.moveTo(*points[0][:2])
        for vertex in points[1:]:
            p.lineTo(*vertex[:2])
        p.close()
        c.drawPath(p,stroke=0,fill=1)
        c.restoreState()

    def add_text(self,label,dxfattribs=None):
        c=self.c
        attrs=dxfattribs or {}
        height=float(attrs.get("height",1.5))
        px,py=attrs.get("insert",(0,0))
        c.saveState()
        c.setFillColorRGB(*self._color(attrs))
        # In a canvas scaled by 72/25.4, a 1.5-unit font is 1.5 mm on paper.
        c.setFont("Helvetica",height)
        string=str(label or "").replace("%%U","").replace("\n"," ")
        c.drawString(px,py,string)
        c.restoreState()


def sheet_map_transform(extent):
    """Match CAD viewport exactly: projected metres to 420x297mm paper coordinates."""
    xa,ya=webmercator((extent[0],extent[1]))
    xb,yb=webmercator((extent[2],extent[3]))
    cx,cy=(xa+xb)/2,(ya+yb)/2
    w=MAP_RIGHT-MAP_LEFT-3.0
    h=MAP_TOP-MAP_BOTTOM-3.0
    view_h=max((yb-ya)*1.055,(xb-xa)*h/w*1.055,1.0)
    centre_x=(MAP_LEFT+MAP_RIGHT)/2
    centre_y=(MAP_BOTTOM+MAP_TOP)/2
    scale=h/view_h
    def project(coords):
        xx,yy=webmercator(coords)
        return (centre_x+(xx-cx)*scale,centre_y+(yy-cy)*scale)
    return project, {"centre":(cx,cy),"view_height":view_h,
                     "width_mm":w,"height_mm":h,"scale_mm_per_m":scale}


def _pdf_point(c,projected,name,style,sheet_index):
    x,y=projected
    r=max(.35,min(1.3,float(style.get("point_size",2.0))*.26))
    typ=str(style.get("point_shape","Circle"))
    c.setFillColorRGB(.99,.80,.13)
    c.setStrokeColorRGB(.08,.08,.08)
    c.setLineWidth(.14)
    if typ=="Square":
        c.rect(x-r,y-r,r*2,r*2,fill=1,stroke=1)
    elif typ=="Triangle":
        p=c.beginPath()
        p.moveTo(x,y+r*1.1)
        p.lineTo(x-r,y-r)
        p.lineTo(x+r,y-r)
        p.close()
        c.drawPath(p,stroke=1,fill=1)
    else:
        c.circle(x,y,r,fill=1,stroke=1)
    if sheet_index>0 and style.get("point_labels",True) and name:
        c.saveState()
        c.setFillColorRGB(.15,.15,.15)
        c.setFont("Helvetica",1.4)
        c.drawString(x+r+0.5,y+r*0.5,str(name)[:38])
        c.restoreState()


def draw_pdf_reference(path,lines,points,project,page_w,page_h,title,sheets,osm=None):
    """Reference-profile PDF with identical sheet geometry to exported DXF.

    All map features come from actual KML/OSM/Google data, never the reference DWG.
    """
    from engineering_render import draw_osm_pdf, _pdf_path, COLORS
    c=pdfcanvas.Canvas(path,pagesize=(page_w,page_h))
    # ReportLab has points; CAD design uses fixed A3 paper in millimetres.
    scalex=page_w/A3_W_MM
    scaley=page_h/A3_H_MM
    style=(osm or {}).get("_drawing_style",{})
    for index,(sheetname,extent) in enumerate(sheets):
        c.saveState()
        c.scale(scalex,scaley)
        paper=PDFCADAdapter(c)
        paper.add_lwpolyline([
            (FRAME_MARGIN,FRAME_MARGIN),
            (A3_W_MM-FRAME_MARGIN,FRAME_MARGIN),
            (A3_W_MM-FRAME_MARGIN,A3_H_MM-FRAME_MARGIN),
            (FRAME_MARGIN,A3_H_MM-FRAME_MARGIN),
        ],close=True)
        paper.add_lwpolyline([
            (MAP_LEFT,MAP_BOTTOM),(MAP_RIGHT,MAP_BOTTOM),
            (MAP_RIGHT,MAP_TOP),(MAP_LEFT,MAP_TOP),
        ],close=True)
        xy,params=sheet_map_transform(extent)
        c.saveState()
        clip=c.beginPath()
        clip.rect(MAP_LEFT+1,MAP_BOTTOM+1,MAP_RIGHT-MAP_LEFT-2,
                  MAP_TOP-MAP_BOTTOM-2)
        c.clipPath(clip,stroke=0,fill=0)
        draw_osm_pdf(c,osm,xy)
        for name,category,geometry in lines:
            if len(geometry)<2:
                continue
            # Preserve established magenta/red FTTH output while honoring
            # sample DWG's relatively thin cable lineweights.
            c.setStrokeColor(COLORS.get(category,COLORS["DISTRIBUSI"]))
            c.setLineWidth(.41 if category=="FEEDER" else .22)
            _pdf_path(c,[xy(point) for point in geometry])
        for name,point in points:
            _pdf_point(c,xy(point),name,style,index)
        c.restoreState()

        _build_tab(paper,title,sheetname,index,len(sheets),osm or {})
        c.restoreState()
        c.showPage()
    c.save()
