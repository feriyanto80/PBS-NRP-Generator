"""Preserve genuine DXF 2018 device blocks with native HATCH/MTEXT/CAD paths.

The Lemah Abang source blocks have non-zero geometry offsets even with
base_point=(0,0). Retain source primitives UNMODIFIED and compensate their
bbox centre at insertion. No reconstructed triangles, circles, or glyphs.
"""
from functools import lru_cache
import os
from pathlib import Path
from weakref import WeakKeyDictionary

_REAL_TYPES=("T6","T7","T9","TE","ODC","ODP","OTB")
_ALIAS={"ODP16":"ODP","ODP24":"ODP","ODP_EXIST":"ODP",
        "ODC_EXIST":"ODC","ODT":"OTB"}
_DOCUMENT_SPECS=WeakKeyDictionary()

@lru_cache(maxsize=4)
def _load(path,mtime):
    import ezdxf
    doc=ezdxf.readfile(path)
    if doc.dxfversion!="AC1032":
        raise ValueError("Reference bukan DXF 2018")
    return doc

def import_original_blocks(doc):
    from exact_template import find_reference
    try:
        source_path=find_reference("dxf")
        if not source_path:
            return False
        source=_load(str(Path(source_path).resolve()),os.path.getmtime(source_path))
        from ezdxf.addons import Importer
        from ezdxf import bbox
        importer=Importer(source,doc)
        names=[name for name in _REAL_TYPES if name in source.blocks]
        # Import nested dependencies (TE includes TIANG EXISTING/ODP).
        importer.import_blocks(names)
        # Extract native editable legend glyphs straight from the ORIGINAL
        # paper-space drawing. Includes native HATCH / ELLIPSE / MTEXT,
        # not any hand-traced surrogate shapes.
        from template_symbols import LEGEND_IDS_LEFT,LEGEND_IDS_RIGHT
        row_baselines=(1168.6,1133.7,1101.3,1068.8,1036.4,
                       1003.9,971.5,939.0,907.6,876.1,844.7)
        glyph_rows=[]
        if "Layout1-ALL" in source.layouts:
            paper=source.layouts.get("Layout1-ALL")
            candidates=[]
            for entity in paper:
                if entity.dxftype() in ("VIEWPORT","OLE2FRAME"):
                    continue
                try:
                    box=bbox.extents([entity],fast=True)
                    if box.has_data:
                        candidates.append((entity,box))
                except Exception:
                    pass
            for col,ids in enumerate((LEGEND_IDS_LEFT,LEGEND_IDS_RIGHT)):
                left,right=((1414.0,1445.0) if col==0 else (1536.0,1570.0))
                for i,kind in enumerate(ids):
                    low=row_baselines[i]+.8
                    high=(1203.4 if i==0 else row_baselines[i-1])-.8
                    selection=[item for item,box in candidates
                        if box.extmin.x>=left and box.extmax.x<=right
                        and box.extmin.y>=low and box.extmax.y<=high
                        and item.dxf.layer!="0"]
                    if not selection:
                        continue
                    blk_name="NRP_NATIVE_"+kind
                    block=doc.blocks.new(blk_name)
                    importer.import_entities(selection,target_layout=block)
                    glyph_rows.append((kind,blk_name,selection))
        importer.finalize()
        metadata={}
        for name in names:
            if name not in doc.blocks:
                continue
            bb=bbox.extents(list(source.blocks.get(name)),fast=True)
            if not bb.has_data:
                continue
            x0,y0=bb.extmin.x,bb.extmin.y
            x1,y1=bb.extmax.x,bb.extmax.y
            longest=max(x1-x0,y1-y0)
            if not 0<longest<100000:
                continue
            # A pole in the source drawing is about 3.2 drawing units wide.
            scale=min(1.05,3.25/longest)
            metadata[name]=(((x0+x1)/2,(y0+y1)/2),scale)
        for kind,block_name,items in glyph_rows:
            if block_name not in doc.blocks:
                continue
            bb=bbox.extents(items,fast=True)
            if not bb.has_data:continue
            x0,y0=bb.extmin.x,bb.extmin.y
            x1,y1=bb.extmax.x,bb.extmax.y
            longest=max(x1-x0,y1-y0)
            if not 0<longest<100000:continue
            # Legend glyphs scaled from source CAD region; their vector
            # geometry/colors/fonts remain original and editable.
            scale=3.25/longest
            metadata[block_name]=(((x0+x1)/2,(y0+y1)/2),scale)
        if metadata:
            _DOCUMENT_SPECS[doc]=metadata
        return bool(metadata)
    except Exception:
        # Native original block mode must never break an offline export.
        return False

def insert_original(doc,model,kind,xy):
    metadata=_DOCUMENT_SPECS.get(doc,{})
    native="NRP_NATIVE_"+kind
    source_name=(native if native in metadata else _ALIAS.get(kind,kind))
    data=metadata.get(source_name)
    if not data:
        return False
    (cx,cy),scale=data
    model.add_blockref(source_name,(xy[0]-cx*scale,xy[1]-cy*scale),
                       dxfattribs={"layer":model_layer(kind),
                                   "xscale":scale,"yscale":scale})
    return True

def model_layer(kind):
    from template_symbols import symbol_layer
    return symbol_layer(kind)
