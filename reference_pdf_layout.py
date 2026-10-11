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
import os

from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from template_symbols import canonical, draw_symbol

_FONT_NAMES={}

def _system_font(bold=False):
    """Use the user's installed Windows Tahoma; never distribute font binaries."""
    key="bold" if bold else "normal"
    if key in _FONT_NAMES:
        return _FONT_NAMES[key]
    windows=os.environ.get("WINDIR",r"C:\Windows")
    candidates=([os.path.join(windows,"Fonts","tahomabd.ttf")] if bold
                else [os.path.join(windows,"Fonts","tahoma.ttf")])
    candidates+=([
        "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ])
    for path in candidates:
        if os.path.isfile(path):
            name="PBS_Reference_Tahoma"+("Bold" if bold else "")
            try:
                pdfmetrics.registerFont(TTFont(name,path))
                _FONT_NAMES[key]=name
                return name
            except Exception:
                continue
    _FONT_NAMES[key]="Helvetica-Bold" if bold else "Helvetica"
    return _FONT_NAMES[key]

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

    def add_filled_circle(self,center,radius,dxfattribs=None):
        c=self.c
        c.saveState()
        c.setFillColorRGB(*self._color(dxfattribs))
        c.circle(center[0],center[1],radius,stroke=0,fill=1)
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
        # Original plotted PDF uses Tahoma regular for technical legends;
        # CAD ROMANS is a SHX stroke font, not directly embeddable by ReportLab.
        c.setFont(_system_font(bold=False),height)
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
    """Compatibility entry point: original HP is numerical TEXT, not a disc."""
    from drafter_annotations import prepare_points
    info=prepare_points([(name,projected)])[0]
    _name,xy,kind,label=info
    x,y=xy
    if kind=="HP":
        c.saveState()
        c.setFillColorRGB(.08,.08,.08)
        c.setFont(_system_font(),1.35)
        c.drawString(x+.65,y+.10,label)
        c.restoreState()
        return
    from reference_pdf_glyphs import draw_reference_pdf_glyph
    glyph_kind="ODT" if kind=="OTB" else kind
    if not draw_reference_pdf_glyph(c,glyph_kind,x,y):
        draw_symbol(PDFCADAdapter(c),kind,x,y,size=.70)


def _pdf_map_annotations(c,points,project,style,viewport,sheet_index=0,source_mode=False):
    """Layer order and annotation placement follow source CAD drafter logic.

    Native symbol positions remain georeferenced. Homepass draws as 001,002...
    at *every* sheet level; the PDF never creates a yellow HP circle.
    A shared deterministic grid prevents labels crossing icons or each other.
    """
    from drafter_annotations import prepare_points, plan_labels, plan_symbols
    from reference_pdf_glyphs import draw_reference_pdf_glyph
    entries=prepare_points(points)
    xmin,ymin,xmax,ymax=viewport
    # No accidental superimposed triangles at the same or nearby pole.
    for kind,label,(x,y),(render_x,render_y) in plan_symbols(
            entries,project,viewport,radius=1.19):
        if abs(x-render_x)+abs(y-render_y)>.03:
            c.saveState()
            c.setLineWidth(.12)
            c.setStrokeColorRGB(.38,.38,.38)
            c.line(x,y,render_x,render_y)
            c.restoreState()
        source_kind="ODT" if kind=="OTB" else kind
        if not draw_reference_pdf_glyph(c,source_kind,render_x,render_y):
            draw_symbol(PDFCADAdapter(c),kind,render_x,render_y,size=.70)
    # Lemahabang original HP text: overview approx 2.2pt, detail 4-6pt.
    # v1.0.20 incorrectly printed every HP at approx 3.4pt.
    label_size=(.79 if sheet_index==0 else 1.67) if source_mode else 1.27
    placements=plan_labels(entries,project,viewport,size=label_size)
    for kind,label,anchor,(lx,ly),fs in placements:
        if kind!="HP" and not style.get("point_labels",True):
            continue
        # Source AutoCAD uses Tahoma for Homepass, not filled waypoint marker.
        c.saveState()
        c.setFillColorRGB(*((.10,.10,.10) if kind=="HP" else (.93,.55,.03)))
        c.setFont(_system_font(bold=False),fs)
        c.drawString(lx,ly,label[:54])
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
    if (osm or {}).get("_cad_reference_style",False):
        from reference_basemap import apply_reference_basemap
        osm=apply_reference_basemap(osm,points)
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
        _pdf_map_annotations(c,points,xy,style,
                             (MAP_LEFT+1,MAP_BOTTOM+1,MAP_RIGHT-1,MAP_TOP-1),
                             sheet_index=index,
                             source_mode=bool((osm or {}).get("_reference_basemap")))
        c.restoreState()

        from original_frame import original_titleblock
        original_titleblock(paper,title,sheetname,index,len(sheets),osm or {})
        c.restoreState()
        c.showPage()
    c.save()
    from exact_template import find_reference, overlay_pdf_upper_titleblock
    reference_pdf=(find_reference("pdf") if (osm or {}).get("_cad_reference_style",True) else None)
    if reference_pdf:
        overlay_pdf_upper_titleblock(
            path,reference_pdf,
            # The reference contains project-specific approvers/identities.
            # Copy those ONLY when 80+ geographic HP anchors prove this is
            # the same source project and sheet plan reproduces all five.
            full_source_project=bool((osm or {}).get("_reference_basemap")
                                     and len(sheets)==5))
