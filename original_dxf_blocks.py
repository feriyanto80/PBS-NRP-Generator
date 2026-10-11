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
        if metadata:
            _DOCUMENT_SPECS[doc]=metadata
        return bool(metadata)
    except Exception:
        # Native original block mode must never break an offline export.
        return False

def insert_original(doc,model,kind,xy):
    source_name=_ALIAS.get(kind,kind)
    metadata=_DOCUMENT_SPECS.get(doc,{})
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
