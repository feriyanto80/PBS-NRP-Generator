"""Exact reference geometry from the user's own Lemah Abang DXF 2018.

Read original Layout1-ALL. Use its CAD font styles, hatches, polylines,
legend glyphs and lineweights rather than the former manually drawn legend.
Keep private approval names and actual survey geometry out of new projects.
Original OLE2FRAME logo is represented by the existing vector logo.
The source DXF itself must be selected once in the desktop application.
"""
import json
import math
import os
from pathlib import Path
import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer
from ezdxf.math import Matrix44

X0,Y0=1413.818271580335,45.75242733457118
X1,Y1=1655.584478473314,1256.05595201469
XLEFT,XRIGHT,YBOTTOM,YTOP=351.0,414.0,5.5,291.5
SX=(XRIGHT-XLEFT)/(X1-X0)
SY=(YTOP-YBOTTOM)/(Y1-Y0)
KEEP_FIELDS=("Nama Proyek","Project Name","Tipe Gambar","Drawing Type",
             "DRAWING SIGN","Created by","Checked by","Approved by","Verified by",
             "Dibuat Oleh","Diperiksa Oleh","Disetujui Oleh","Diketahui Oleh",
             "Arah","Direction","Ref. Peta","Map Ref.","Drawing No.","No. Gambar",
             "Skala","Scale","Halaman","Page","N.T.S","DATE","REVISION","SIGN")
PRIVATE=("FTTH STASIUN LEMAH","MUHAMAD","SYEVAN","HANDY NUGROHO",
         "PT. MITRA","PT. INTEGRASI","SPV OF","HEAD OF",
         "SURVEY & DESIGN","PROJECT MANAGER","QUALITY CONTROL")


def settings_path():
    root=Path(os.getenv("LOCALAPPDATA") or Path.home()/".pbs_nrp")
    return root/"PBS_NRP_Generator"/"cad_reference.json"


def validate_template(path):
    if not path or not Path(path).is_file():
        raise ValueError("DXF referensi tidak ditemukan.")
    doc=ezdxf.readfile(str(path))
    if doc.dxfversion!="AC1032" or "Layout1-ALL" not in doc.layouts:
        raise ValueError("Pilih DXF 2018 Lemah Abang asli dengan Layout1-ALL.")
    titles=[e for e in doc.layouts["Layout1-ALL"].query("TEXT")
            if "AS BUILT DRAWING" in e.dxf.text.upper()]
    if not titles:
        raise ValueError("Title block AS BUILT DRAWING tidak ditemukan.")
    return str(Path(path).resolve())


def save_template_path(path):
    path=validate_template(path)
    config=settings_path()
    config.parent.mkdir(parents=True,exist_ok=True)
    temp=config.with_suffix(".tmp")
    temp.write_text(json.dumps({"reference_dxf":path}),encoding="utf-8")
    temp.replace(config)
    return path


def saved_template_path():
    try:
        path=json.loads(settings_path().read_text(encoding="utf-8")).get("reference_dxf")
        return validate_template(path)
    except (OSError,ValueError,TypeError,AttributeError):
        return None


def selected(ent):
    if ent.dxftype() in ("VIEWPORT","OLE2FRAME","IMAGE","WIPEOUT"):
        return False
    try:
        box=bbox.extents([ent])
    except Exception:
        return False
    if not box.has_data or box.extmin.x<X0-1.5 or box.extmax.x>X1+2:
        return False
    if box.extmin.y<Y0-2 or box.extmax.y>Y1+3:
        return False
    if ent.dxftype() in ("TEXT","MTEXT"):
        raw=ent.dxf.get("text","") if ent.dxftype()=="TEXT" else ent.text
        if any(marker in raw.upper() for marker in PRIVATE):
            return False
        pos=ent.dxf.get("insert")
        if pos is not None and pos.y<535:
            return any(key.lower() in raw.lower() for key in KEEP_FIELDS)
    return True


def source_entities(path):
    doc=ezdxf.readfile(str(path))
    return doc,[entity for entity in doc.layouts["Layout1-ALL"] if selected(entity)]


def to_paper(point):
    return XLEFT+(point[0]-X0)*SX,YBOTTOM+(point[1]-Y0)*SY


def import_titleblock(doc,layout,path,project,index,total,sheet_title):
    """Import original CAD titleblock, preserving block/font dependencies."""
    source,entities=source_entities(path)
    previous={e.dxf.handle for e in layout if e.dxf.hasattr("handle")}
    importer=Importer(source,doc)
    importer.import_entities(entities,layout)
    importer.finalize()
    matrix=Matrix44.chain(Matrix44.translate(-X0,-Y0,0),
        Matrix44.scale(SX,SY,1),Matrix44.translate(XLEFT,YBOTTOM,0))
    count=0
    for ent in list(layout):
        if ent.dxf.get("handle") in previous:
            continue
        try:
            ent.transform(matrix)
            count+=1
        except (ValueError,ArithmeticError,NotImplementedError):
            layout.delete_entity(ent)
    # Exact original legend/table, dynamic generic metadata; no copied signatures.
    layout.add_text(str(project or "")[:58],dxfattribs={
        "layer":"NRP_TB_TEXT","height":1.55,"insert":(352.5,126)})
    layout.add_text(str(sheet_title or "")[:50],dxfattribs={
        "layer":"NRP_TB_TEXT","height":1.35,"insert":(352.5,115)})
    layout.add_text(f"{index+1} OF {total}",dxfattribs={
        "layer":"NRP_TB_TEXT","height":1.50,"insert":(390,20)})
    return count


def paint_titleblock(c,path,project,sheet_title,index,total):
    """Draw same DXF line/text/contour geometry into vector PDF (mm coordinates).

    Original SHX-specific glyph shapes require the source SHX font; fallback
    Helvetica is used in PDF and DXF keeps the original TEXT style reference.
    """
    from reportlab.lib.colors import Color
    _,entities=source_entities(path)
    palette={1:(1,.04,.09),2:(1,.78,0),5:(.03,.22,.99),6:(.89,.10,.80),
             7:(.12,.12,.12),8:(.52,.52,.52),9:(.7,.7,.7),18:(.1,.42,.88),
             30:(.99,.4,.08),250:(.7,.7,.7)}
    def stroke(entity):
        aci=int(entity.dxf.get("color",7))
        c.setStrokeColor(Color(*palette.get(aci,(.13,.13,.13))))
        wt=entity.dxf.get("lineweight",0)
        c.setLineWidth(max(.08,min(.75,wt/100 if wt>0 else .15)))
    for entity in entities:
        ty=entity.dxftype()
        c.saveState()
        try:
            stroke(entity)
            if ty=="LINE":
                c.line(*to_paper(entity.dxf.start),*to_paper(entity.dxf.end))
            elif ty=="LWPOLYLINE":
                coords=[to_paper(p) for p in entity.get_points("xy")]
                if coords:
                    path=c.beginPath();path.moveTo(*coords[0])
                    for pt in coords[1:]:path.lineTo(*pt)
                    if entity.closed:path.close()
                    c.drawPath(path,stroke=1,fill=0)
            elif ty=="CIRCLE":
                x,y=to_paper(entity.dxf.center)
                c.ellipse(x-entity.dxf.radius*SX,y-entity.dxf.radius*SY,
                          x+entity.dxf.radius*SX,y+entity.dxf.radius*SY,
                          fill=0,stroke=1)
            elif ty=="ELLIPSE":
                coords=[]
                centre=entity.dxf.center
                major=entity.dxf.major_axis
                minor=(-major.y*entity.dxf.ratio,major.x*entity.dxf.ratio)
                for j in range(49):
                    theta=entity.dxf.start_param+(entity.dxf.end_param-entity.dxf.start_param)*j/48
                    coords.append(to_paper((centre.x+major.x*math.cos(theta)+minor[0]*math.sin(theta),
                                             centre.y+major.y*math.cos(theta)+minor[1]*math.sin(theta))))
                if coords:
                    p=c.beginPath();p.moveTo(*coords[0])
                    for point in coords[1:]:p.lineTo(*point)
                    c.drawPath(p,stroke=1,fill=0)
            elif ty=="TEXT":
                text=entity.dxf.get("text","").replace("%%U","")
                x,y=to_paper(entity.dxf.insert)
                c.setFont("Helvetica",max(.6,entity.dxf.get("height",4)*SY))
                c.drawString(x,y,text)
            elif ty=="MTEXT":
                x,y=to_paper(entity.dxf.insert)
                size=max(.65,entity.dxf.get("char_height",4)*SY)
                c.setFont("Helvetica",size)
                for row_i,row in enumerate(entity.plain_text().splitlines()[:3]):
                    c.drawString(x,y-size*1.2*row_i,row)
            elif ty=="HATCH":
                # Preserve solid hatch fill of CAD legend glyphs.
                c.setFillColor(c._strokeColor)
                for edge in entity.paths:
                    vertices=getattr(edge,"vertices",None)
                    if vertices and len(vertices)>2:
                        coords=[to_paper(p) for p in vertices]
                        p=c.beginPath();p.moveTo(*coords[0])
                        for point in coords[1:]:p.lineTo(*point)
                        p.close()
                        c.drawPath(p,stroke=0,fill=1)
        except (ValueError,TypeError,AttributeError,ZeroDivisionError):
            pass
        finally:
            c.restoreState()
    c.saveState()
    c.setFont("Helvetica",1.4)
    c.drawString(352.5,126,str(project or "")[:52])
    c.drawString(352.5,115,str(sheet_title or "")[:45])
    c.drawString(390,20,f"{index+1} OF {total}")
    c.restoreState()
