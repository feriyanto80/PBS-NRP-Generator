"""Optional exact original Lemah Abang 2018 reference template assets.

When the user's original drawing is shipped in sibling template directory,
use its exact DXF titleblock shapes and original plotted PDF glyphs.
Never copy historic client/project names or approvals: only STATIC title,
legend, cable matrix, logo and their boundary graphics are imported.

Portable ZIP ships template/*.dxf and template/*.pdf; EXE-only releases fall
back to our vector reconstruction. No private source is committed to GitHub.

This uses PDF reference page 1 only for the upper static A3 titleblock
region, preserving actual fonts and OLE logo as printed.
"""
import os
from pathlib import Path
import sys

SOURCE_STEM="ABD St.Lemah Abang Phase 1 Simpangan"
REFERENCE_SCALE=.236
SOURCE_LEFT=1413.9
SOURCE_BOTTOM=45.8
TARGET_LEFT=351.0
TARGET_BOTTOM=5.5
CAD_UPPER_Y=621.5
PDF_UPPER_BOTTOM_PT=442.0


def resource_roots():
    roots=[]
    if getattr(sys,"frozen",False):
        roots.append(Path(sys.executable).resolve().parent)
    roots += [Path(__file__).resolve().parent,Path.cwd()]
    env=os.environ.get("PBS_NRP_TEMPLATE_DIR")
    if env:
        roots.insert(0,Path(env))
    local=os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local)/"PBS_NRP_Generator")
    unique=[]
    for item in roots:
        for root in (item/"template",item):
            if root not in unique:unique.append(root)
    return unique


def find_reference(extension):
    extension="."+extension.lower().lstrip(".")
    candidates=[SOURCE_STEM+extension, SOURCE_STEM+"(1)"+extension]
    for directory in resource_roots():
        for name in candidates:
            candidate=directory/name
            if candidate.is_file():
                return str(candidate)
    return None


def has_exact_template():
    return bool(find_reference("pdf") and find_reference("dxf"))


def _source_bbox(entity):
    from ezdxf import bbox
    try:
        bb=bbox.extents([entity],fast=True)
        if bb.has_data:
            return bb
    except Exception:
        pass
    return None


def _original_static_entity(ent,bb):
    if ent.dxftype() in ("VIEWPORT","OLE2FRAME"):
        return False
    if bb is None:
        return False
    # Source CAD includes extraneous inserts whose blocks span thousands
    # of units. Selection MUST check insertion point as well.
    if ent.dxftype()=="INSERT" and ent.dxf.insert.x<1400:
        return False
    if (bb.extmax.x<1413 or bb.extmin.x<1300 or
            bb.extmin.y<CAD_UPPER_Y or bb.extmax.y<620):
        return False
    return True


def _target_upper_entity(ent):
    if ent.dxftype()=="VIEWPORT":
        return False
    bb=_source_bbox(ent)
    if bb is None:
        return False
    # Do not delete the outer full-height border or map/viewport lines.
    return (bb.extmin.x>=350.8 and bb.extmin.y>=141.4 and
            bb.extmax.y<294.0)


def replace_cad_upper_titleblock(doc,layout,source_path):
    """Transplant original upper PaperSpace geometry from user DXF.

    Template's original model network is NEVER copied.
    """
    import ezdxf
    from ezdxf.math import Matrix44
    source=ezdxf.readfile(source_path)
    if source.dxfversion!="AC1032":
        raise ValueError("Template harus DXF 2018 / AC1032")
    if "Layout1-ALL" not in source.layouts:
        raise ValueError("Template DXF tidak punya Layout1-ALL")
    selected=[]
    for entity in source.layouts.get("Layout1-ALL"):
        bb=_source_bbox(entity)
        if _original_static_entity(entity,bb):
            selected.append(entity)
    if len(selected)<80:
        raise ValueError("Template tidak memiliki cukup entitas legenda")
    matrix=Matrix44.chain(
        Matrix44.scale(REFERENCE_SCALE,REFERENCE_SCALE,1),
        Matrix44.translate(
            TARGET_LEFT-SOURCE_LEFT*REFERENCE_SCALE,
            TARGET_BOTTOM-SOURCE_BOTTOM*REFERENCE_SCALE,0))
    imported=[]
    for entity in selected:
        if entity.dxftype()=="INSERT" and entity.dxf.name=="OTB":
            if "NRP_REF_LEGEND_OTB" not in doc.blocks:
                dest=doc.blocks.new("NRP_REF_LEGEND_OTB")
                for item in source.blocks.get("OTB"):
                    dest.add_entity(item.copy())
            copy=entity.copy()
            copy.dxf.name="NRP_REF_LEGEND_OTB"
        elif entity.dxftype()=="INSERT":
            continue
        else:
            copy=entity.copy()
        try:
            copy.transform(matrix)
            imported.append(copy)
        except Exception:
            continue
    for style in source.styles:
        if style.dxf.name not in doc.styles:
            props={"font":style.dxf.font}
            if style.dxf.get("bigfont"):
                props["bigfont"]=style.dxf.bigfont
            doc.styles.new(style.dxf.name,dxfattribs=props)
    for src_layer in source.layers:
        name=src_layer.dxf.name
        if name not in doc.layers:
            doc.layers.new(name,dxfattribs={
                "color":int(src_layer.dxf.color),
                "linetype":"CONTINUOUS"})
    old=[item for item in layout if _target_upper_entity(item)]
    for item in old:
        layout.delete_entity(item)
    for item in imported:
        layout.add_entity(item)
    return len(imported)


def overlay_pdf_upper_titleblock(output_pdf,reference_pdf):
    """Use source PDF's actual plotted vector glyphs and logo in output.

    Only static upper title/legend/cables/logo region is copied, never
    old project names, signatures or approvals from lower titleblock.
    """
    import fitz
    path=Path(output_pdf)
    output=fitz.open(path)
    source=fitz.open(reference_pdf)
    try:
        if source.page_count<1:
            raise ValueError("PDF template kosong")
        first=source[0]
        if abs(first.rect.width-1191)>8 or abs(first.rect.height-842)>8:
            raise ValueError("PDF template bukan A3 Landscape")
        for page in output:
            template=fitz.Rect(993.0,16.0,1158.0,PDF_UPPER_BOTTOM_PT)
            target=fitz.Rect(
                template.x0*page.rect.width/first.rect.width,
                template.y0*page.rect.height/first.rect.height,
                template.x1*page.rect.width/first.rect.width,
                template.y1*page.rect.height/first.rect.height)
            page.draw_rect(target,color=None,fill=(1,1,1),overlay=True)
            page.show_pdf_page(target,source,0,clip=template,
                               keep_proportion=False,overlay=True)
        dest=path.with_name(path.stem+".template.tmp.pdf")
        output.save(str(dest),garbage=4,deflate=True)
    finally:
        source.close()
        output.close()
    os.replace(dest,path)
    check=fitz.open(path)
    try:
        return check.page_count
    finally:
        check.close()
