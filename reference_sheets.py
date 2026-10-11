"""Derive five Lemahabang print windows from source PDF, not hard-coded tiles.

Only enabled when 2018 DXF/KMZ can be registered by 80+ matching HP numbers.
Original reference: 1 overview + 4 locality-driven details.
"""
import os
import re

def reference_sheet_extents(points,bbox):
    from exact_template import find_reference
    from reference_basemap import register_source,_hp_id
    if not register_source(points):
        return None
    pdf=find_reference("pdf")
    if not pdf:
        return None
    import fitz
    coords={}
    for name,geo in points:
        key=_hp_id(name)
        if key:
            coords[key]=geo
    doc=fitz.open(pdf)
    try:
        if doc.page_count!=5:
            return None
        result=[("Overview",tuple(bbox))]
        for i in range(1,5):
            page=doc[i]
            keys={word[4] for word in page.get_text("words")
                  if re.fullmatch(r"\d{3}",word[4])}
            common=keys&coords.keys()
            if len(common)<35:
                return None
            geos=[coords[key] for key in common]
            west=min(pos[0] for pos in geos)
            south=min(pos[1] for pos in geos)
            east=max(pos[0] for pos in geos)
            north=max(pos[1] for pos in geos)
            if east-west<1e-6 or north-south<1e-6:
                return None
            # Pad by 8%: prevent cables at HP extremities getting clipped.
            dx=(east-west)*.08
            dy=(north-south)*.08
            w=max(bbox[0],west-dx)
            s=max(bbox[1],south-dy)
            e=min(bbox[2],east+dx)
            n=min(bbox[3],north+dy)
            result.append((f"Detail {i:02d} · Referensi Lemahabang",(w,s,e,n)))
        return result
    finally:
        doc.close()
