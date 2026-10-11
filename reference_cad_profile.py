"""PBS CAD Reference Profile: extracted layer/block vocabulary from the uploaded
ABD St.Lemah Abang Phase 1 Simpangan DXF 2018 (AC1032).

Original drawing audit: 49 layers, 30 block definitions, 1 paper layout
'Layout1-ALL'. The source DXF itself is deliberately NOT distributed; this
profile contains only generic technical layer definitions and original naming
conventions. Company-specific project names and signatures are not copied.
"""
import re

# Name / ACI index / approximate lineweight (hundredths mm) / linetype.
# Values follow the supplied source drawing, not guessed from the sample PDF.
REFERENCE_LAYERS = [
 ("0",7,None,"CONTINUOUS"),("20FCBD0",7,None,"CONTINUOUS"),
 ("buildings",7,None,"CONTINUOUS"),("railways",7,None,"CONTINUOUS"),
 ("parks",7,None,"CONTINUOUS"),("outline",7,None,"CONTINUOUS"),
 ("Basic Map",251,None,"CONTINUOUS"),("Jalan",255,None,"CONTINUOUS"),
 ("Precon to DC",1,None,"CONTINUOUS"),("Line Feeder",1,None,"CONTINUOUS"),
 ("ODP",1,None,"CONTINUOUS"),("Line ODC",1,None,"CONTINUOUS"),
 ("Homepass",1,None,"CONTINUOUS"),("ODC",1,None,"CONTINUOUS"),
 ("WPTATTRIBS",7,None,"CONTINUOUS"),("HC",7,None,"CONTINUOUS"),
 ("FAT",7,None,"CONTINUOUS"),("LOGO",250,9,"CONTINUOUS"),
 ("New Pole",7,None,"CONTINUOUS"),("NEW POLE T6",7,None,"CONTINUOUS"),
 ("NEW POLE T7",7,None,"CONTINUOUS"),("NEW POLE T9",7,None,"CONTINUOUS"),
 ("POLE EXISTING",7,None,"CONTINUOUS"),("NAMA",255,50,"CONTINUOUS"),
 ("OTB",5,13,"CONTINUOUS"),("TEXT",40,None,"CONTINUOUS"),
 ("ClosureCoilan",7,None,"CONTINUOUS"),("Exs Pole",7,None,"CONTINUOUS"),
 ("New HH",7,None,"CONTINUOUS"),("HH Exs",7,None,"CONTINUOUS"),
 ("Closure",7,None,"CONTINUOUS"),("FAT Exs",7,None,"CONTINUOUS"),
 ("Closure Exs",7,None,"CONTINUOUS"),("Grid",210,None,"CONTINUOUS"),
 ("Rel KA",7,100,"DASHED"),("DROP WIRE",190,None,"CONTINUOUS"),
 ("STRAND UG",3,None,"DASHED"),("FO 96 CORE",1,50,"CONTINUOUS"),
 ("FO 12 CORE",12,50,"CONTINUOUS"),("FO 24 CORE",30,50,"CONTINUOUS"),
 ("FEEDER",7,50,"CONTINUOUS"),("FO 48 CORE",5,50,"CONTINUOUS"),
 ("FO 144 CORE",3,50,"CONTINUOUS"),("STRAND AE",3,None,"CONTINUOUS"),
 ("FO 72 CORE",6,50,"CONTINUOUS"),("FO 288 CORE",250,50,"CONTINUOUS"),
 ("DROP DUCT",5,None,"CONTINUOUS"),("COIL",1,13,"CONTINUOUS"),
 ("Defpoints",7,None,"CONTINUOUS"),
]

SYMBOL_NAMES=("ODP","ODC","T6","T7","T9","TE","OTB",
              "CLOSURE","HH","HP")

CABLE_CORE_LAYERS={12:"FO 12 CORE",24:"FO 24 CORE",48:"FO 48 CORE",
                   72:"FO 72 CORE",96:"FO 96 CORE",144:"FO 144 CORE",
                   288:"FO 288 CORE"}


def add_reference_layers(doc):
    if "DASHED" not in doc.linetypes:
        doc.linetypes.new("DASHED",dxfattribs={"description":"Dashed __ __",
                                             "pattern":[1.0,.65,-.35]})
    for name, color, weight, linetype in REFERENCE_LAYERS:
        if name in doc.layers:
            layer=doc.layers.get(name)
        else:
            layer=doc.layers.new(name,dxfattribs={"color":color})
        if name not in ("0","Defpoints"):
            layer.dxf.color=color
            if weight is not None:
                layer.dxf.lineweight=weight
            layer.dxf.linetype=linetype


def resolve_reference_line_layer(name, category):
    """Classify only when metadata actually identifies fiber size/kind."""
    label=str(name or "").upper()
    for core,layer in sorted(CABLE_CORE_LAYERS.items(),reverse=True):
        if re.search(r"(?<!\d)"+str(core)+r"\s*(?:C(?:ORE)?|FO|F)(?!\d)",label):
            return layer
        if re.search(r"(?<!\d)"+str(core)+r"\s*[-_/]*\s*CORE(?!\d)",label):
            return layer
    if category=="FEEDER":
        return "Line Feeder"
    if category=="SUBFEEDER":
        return "FEEDER"
    return "Precon to DC"


def classify_network_point(name):
    """Do not infer an ODP/ODC from arbitrary HP numeric IDs."""
    value=re.sub(r"[^A-Z0-9]+"," ",str(name or "").upper())
    keys=value.split()
    if "ODC" in keys:
        return "ODC"
    if "ODP" in keys or "FAT" in keys:
        return "ODP"
    if "OTB" in keys:
        return "OTB"
    if "CLOSURE" in keys or "JOINT" in keys:
        return "CLOSURE"
    if "HANDHOLE" in keys or "HH" in keys:
        return "HH"
    if "T6" in keys or ("TIANG" in keys and "6" in keys):
        return "T6"
    if "T7" in keys or ("TIANG" in keys and "7" in keys):
        return "T7"
    if "T9" in keys or ("TIANG" in keys and "9" in keys):
        return "T9"
    if "TE" in keys or ("EXISTING" in keys and ("POLE" in keys or "TIANG" in keys)):
        return "TE"
    if "HOMEPASS" in keys or "HP" in keys or "HOME" in keys:
        return "HP"
    return None


def _circle(b,layer,radius,color=None):
    attrs={"layer":layer}
    if color is not None:
        attrs["color"]=color
    b.add_circle((0,0),radius,dxfattribs=attrs)


def install_symbols(doc):
    """Install editable CAD blocks from the SAME authority as PDF/map legend."""
    from template_symbols import (draw_symbol, symbol_layer,
                                  LEGEND_IDS_LEFT, LEGEND_IDS_RIGHT)
    for style,font in (
        ("NRP_REFERENCE_ROMANS","romans.shx"),
        ("NRP_REFERENCE_TAHOMA","tahoma.ttf"),
    ):
        if style not in doc.styles:
            doc.styles.new(style,dxfattribs={"font":font})
    kinds=set(SYMBOL_NAMES)|set(LEGEND_IDS_LEFT)|set(LEGEND_IDS_RIGHT)
    for kind in sorted(kinds):
        if kind in doc.blocks:
            continue
        block=doc.blocks.new(name=kind,base_point=(0,0))
        draw_symbol(block,kind,0,0,size=1.0,layer=symbol_layer(kind))


def add_device(doc,model,name,xy,size=2.0,labels=True):
    from template_symbols import canonical, symbol_layer
    kind=canonical(name)
    if kind is None:
        return False
    size=max(0.45,min(2.6,float(size)/2))
    model.add_blockref(kind,xy,dxfattribs={
        "layer":symbol_layer(kind),
        "xscale":size,"yscale":size})
    if labels:
        model.add_text(str(name)[:64],dxfattribs={
            "height":1.35,"insert":(xy[0]+2.1*size,xy[1]+1.1*size),
            "layer":"TEXT","style":"NRP_REFERENCE_ROMANS"})
    return True
