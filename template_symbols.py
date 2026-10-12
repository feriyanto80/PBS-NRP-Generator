"""Single-source Lemah Abang symbol authority (DXF 2018 / plotted PDF).

The same vector primitives are used for:
  • 11x2 reference titleblock legend,
  • FTTH point symbols on the PDF map,
  • editable DXF block definitions (and the resulting licensed ODA DWG).

Colors and symbol semantics are taken from the user's real 2018 drawing
and plotted PDF, not the previous generic 'yellow dots everywhere' renderer.
Homepasses use numeric TEXT only; unclassified points have no glyph.
"""
import math
import re

# ACI values approximate the original CAD plot. True-color avoids differing
# user AutoCAD palettes while maintaining an ACI fallback for old viewers.
COLORS={
    "black":(17,17,17),"yellow":(255,210,0),
    "orange":(255,92,16),"red":(239,25,34),
    "blue":(20,49,245),"magenta":(231,20,201),
    "grey":(145,146,150),"lightgrey":(193,193,193),
    "white":(255,255,255),"purple":(138,42,216),
}
ACI={"black":7,"yellow":2,"orange":30,"red":1,"blue":5,
     "magenta":6,"grey":8,"lightgrey":9,"white":7,"purple":200}


def attrs(layer,colour):
    r,g,b=COLORS[colour]
    return {"layer":layer,"color":ACI[colour],
            "true_color":(r<<16)|(g<<8)|b}


def canonical(name):
    """Explicit semantic classification, never infer device from a numeric ID."""
    verified=getattr(name,"nrp_kind",None)
    if verified in ("HP","T6","T7","T9","TE","TL","ODC","ODC_EXIST",
                    "ODP","ODP16","ODP24","ODP_EXIST","OTB","ODT",
                    "CLOSURE","CLOSURE_EXIST","COIL","COIL_EXIST",
                    "HH","HH_EXIST","HH_OTHER"):
        return verified
    text=re.sub(r"[^A-Z0-9]+"," ",str(name or "").upper()).strip()
    words=set(text.split())
    if "ODC" in words:
        return "ODC_EXIST" if ("EXISTING" in words or "EXS" in words) else "ODC"
    if "ODP" in words or "FAT" in words:
        if "EXISTING" in words or "EXS" in words:return "ODP_EXIST"
        if "24" in words:return "ODP24"
        if "16" in words:return "ODP16"
        return "ODP"
    if "OPTIC" in words and "TERMINAL" in words or "ODT" in words:
        return "ODT"
    if "OTB" in words:return "OTB"
    if "CLOSURE" in words or "JOINT" in words:
        return "CLOSURE_EXIST" if "EXISTING" in words or "EXS" in words else "CLOSURE"
    if "COIL" in words:
        return "COIL_EXIST" if "EXISTING" in words or "EXS" in words else "COIL"
    if "BORING" in words and "CROSSING" in words:return "BORING_CROSSING"
    if "BORING" in words:return "BORING_ALUR"
    if "CROSSING" in words and "BRIDGE" in words:return "CROSSING_BRIDGE"
    if "HANDHOLE" in words or "HH" in words:
        return "HH_EXIST" if "EXISTING" in words or "EXS" in words else "HH"
    if (("EXISTING" in words or "EXS" in words or "EKSISTING" in words)
            and ("POLE" in words or "TIANG" in words)):
        return "TE"
    # Real field KMZ labels frequently use "NEW POLE 6", "TIANG 7"
    # or "POLE-9" rather than the original engineering T6/T7/T9 IDs.
    match=re.search(r"\b(?:POLE|TIANG)\s+(6|7|9)\b",text)
    if match:
        return "T"+match.group(1)
    for kind in ("T6","T7","T9","TE","TL"):
        if kind in words:return kind
    if "EXISTING" in words and ("POLE" in words or "TIANG" in words):return "TE"
    if "HOMEPASS" in words or "HP" in words or "HOME" in words:return "HP"
    return None


LEGEND_IDS_LEFT=(
    "T6","T7","T9","TL","TE","ODC","ODC_EXIST",
    "ODP","ODP16","ODP24","ODP_EXIST"
)
LEGEND_IDS_RIGHT=(
    "CLOSURE_EXIST","CLOSURE","COIL","COIL_EXIST",
    "ODT","HH_OTHER","HH","HH_EXIST",
    "BORING_ALUR","CROSSING_BRIDGE","BORING_CROSSING"
)


def symbol_layer(symbol):
    return {
        "T6":"NEW POLE T6","T7":"NEW POLE T7","T9":"NEW POLE T9",
        "TE":"POLE EXISTING","TL":"New Pole",
        "ODC":"ODC","ODC_EXIST":"ODC",
        "ODP":"ODP","ODP16":"ODP","ODP24":"ODP","ODP_EXIST":"ODP",
        "OTB":"OTB","ODT":"OTB","HP":"Homepass",
        "CLOSURE":"Closure","CLOSURE_EXIST":"Closure Exs",
        "COIL":"COIL","COIL_EXIST":"COIL",
        "HH":"New HH","HH_OTHER":"New HH","HH_EXIST":"HH Exs",
        "BORING_ALUR":"DROP DUCT","BORING_CROSSING":"DROP DUCT",
        "CROSSING_BRIDGE":"Jalan",
    }.get(symbol,"POINTS")


def draw_symbol(draw,kind,x,y,size=1.0,layer=None):
    """Draw self-contained engineering legend glyph, centered at (x,y).

    'draw' can be ezdxf BlockLayout/PaperSpace or PDFCADAdapter.
    DXF blocks use a single scalable insertion origin; PDF uses the identical
    geometry and color authority. ACI and true_color are emitted together.
    """
    kind=kind or "HP"
    layer=layer or symbol_layer(kind)
    s=float(size)
    def at(dx,dy):return (x+s*dx,y+s*dy)
    def line(path,color="black",closed=False):
        draw.add_lwpolyline([at(dx,dy) for dx,dy in path],close=closed,
                            dxfattribs=attrs(layer,color))
    def circle(dx,dy,r,color="black"):
        draw.add_circle(at(dx,dy),r*s,dxfattribs=attrs(layer,color))
    def fillpoly(coords,color):
        points=[at(dx,dy) for dx,dy in coords]
        # Triangulate convex or semicircular fan without an external geometry
        # dependency. Avoid appending extra point for 3D DXF SOLID if triangles.
        anchor=points[0]
        for j in range(1,len(points)-1):
            tri=[anchor,points[j],points[j+1]]
            draw.add_solid(tri+[tri[-1]],dxfattribs=attrs(layer,color))
    def disc(dx,dy,r,color):
        # Fast, visually equivalent PDF fill: no 16-triangle overhead per HP.
        if hasattr(draw,"add_filled_circle"):
            draw.add_filled_circle(at(dx,dy),r*s,dxfattribs=attrs(layer,color))
        else:
            vertices=[(dx+r*math.cos(2*math.pi*i/16),
                       dy+r*math.sin(2*math.pi*i/16)) for i in range(16)]
            fillpoly(vertices,color)
    def text(label,dx,dy,h,color="black"):
        draw.add_text(label,dxfattribs={**attrs(layer,color),
             "height":h*s,"insert":at(dx,dy),"style":"NRP_REFERENCE_ROMANS"})

    if kind in ("T6","T7","T9","TE","TL"):
        bg={"T6":"yellow","T7":"black","T9":"blue",
            "TE":"grey","TL":"orange"}[kind]
        border={"T6":"orange","T7":"yellow","T9":"blue",
                "TE":"grey","TL":"orange"}[kind]
        ink={"T6":"orange","T7":"yellow","T9":"yellow",
             "TE":"black","TL":"black"}[kind]
        disc(0,0,1.0,bg)
        circle(0,0,1.0,border)
        text(kind,-.62 if len(kind)==2 else -.75,-.23,.73,ink)
    elif kind in ("ODC","ODC_EXIST","ODP","ODP16","ODP24","ODP_EXIST"):
        ink={"ODC":"red","ODC_EXIST":"lightgrey","ODP":"blue",
             "ODP16":"orange","ODP24":"magenta","ODP_EXIST":"black"}[kind]
        line([(-1.0,-.8),(0,1.12),(1.0,-.8)],ink,closed=True)
    elif kind in ("CLOSURE","CLOSURE_EXIST"):
        ink="red" if kind=="CLOSURE" else "black"
        # Original DXF legend uses filled bow-tie / opposed wedges,
        # not the generic crossing X used in earlier NRP releases.
        fillpoly([(-1.1,-.7),(-1.1,.7),(0,0)],ink)
        fillpoly([(1.1,.7),(1.1,-.7),(0,0)],ink)
    elif kind in ("COIL","COIL_EXIST"):
        ink="red" if kind=="COIL" else "grey"
        circle(-.55,0,.65,ink)
        circle(.55,0,.65,ink)
    elif kind in ("OTB","ODT"):
        line([(-1,-.8),(1,-.8),(1,.8),(-1,.8)],"blue",True)
        if kind=="ODT":
            text("RAK",-.72,.13,.46,"blue")
            text("OTB",-.72,-.46,.46,"blue")
        else:
            text("OTB",-.76,-.20,.56,"blue")
    elif kind in ("HH","HH_EXIST","HH_OTHER"):
        ink={"HH":"blue","HH_EXIST":"black","HH_OTHER":"orange"}[kind]
        line([(-1,-.85),(1,-.85),(1,.85),(-1,.85)],ink,True)
        if kind!="HH_EXIST":text("HH",-.68,-.21,.65,ink)
    elif kind=="BORING_ALUR":
        line([(-1.1,-.63),(1.1,-.63),(1.1,.63),(-1.1,.63)],"red",True)
        for step in range(-3,4):
            x0=step*.35
            line([(max(-1.1,x0-.6),-.63),(min(1.1,x0+.6),.63)],"red")
    elif kind=="CROSSING_BRIDGE":
        fillpoly([(-1.1,-.4),(1.1,-.4),(1.1,.4),(-1.1,.4)],"grey")
    elif kind=="BORING_CROSSING":
        line([(-1.1,-.65),(1.1,-.65),(1.1,.65),(-1.1,.65)],"red",True)
        circle(0,0,.65,"red")
    else:
        # There is no generic waypoint symbol in the source CAD legend.
        # UNKNOWN and HP must never be rendered as yellow circles.
        return
