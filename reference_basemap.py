"""2018 Lemahabang CAD-authoritative basemap, georegistered to input KML.

Never copy an unrelated project's buildings into another project. Require
>=80 matching numbered HP with a checked affine registration. The original
DXF is user-supplied in template/; no client GIS/CAD bytes in public source.
"""
import math
import os
import re
import statistics
from functools import lru_cache

R=6378137.0

def mercator(pos):
    lon,lat=pos
    return (R*math.radians(float(lon)),
            R*math.log(math.tan(math.pi/4+math.radians(float(lat))/2)))

def unmercator(pos):
    x,y=pos
    return (math.degrees(x/R),
            math.degrees(2*math.atan(math.exp(y/R))-math.pi/2))

def _solve(a,b):
    m=[list(row)+[float(value)] for row,value in zip(a,b)]
    for j in range(3):
        p=max(range(j,3),key=lambda i:abs(m[i][j]))
        m[j],m[p]=m[p],m[j]
        if abs(m[j][j])<1e-10:
            raise ValueError("CAD registration is singular")
        d=m[j][j]
        for k in range(j,4):
            m[j][k]/=d
        for i in range(3):
            if i!=j:
                f=m[i][j]
                for k in range(j,4):
                    m[i][k]-=f*m[j][k]
    return tuple(row[3] for row in m)

def _fit(pairs):
    matrix=[[0.]*3 for _ in range(3)]
    bx=[0.]*3
    by=[0.]*3
    for x,y,mx,my in pairs:
        row=(x,y,1.)
        for i in range(3):
            bx[i]+=row[i]*mx
            by[i]+=row[i]*my
            for j in range(3):
                matrix[i][j]+=row[i]*row[j]
    return _solve(matrix,bx),_solve(matrix,by)

def _residual(pair,affine):
    x,y,mx,my=pair
    ax,ay=affine
    return math.hypot(ax[0]*x+ax[1]*y+ax[2]-mx,
                      ay[0]*x+ay[1]*y+ay[2]-my)

def _hp_id(label):
    match=re.fullmatch(r"\s*(?:HP[\s_-]*)?(\d{3})\s*",str(label or ""),re.I)
    return match.group(1) if match else None

@lru_cache(maxsize=2)
def _source(path,mtime):
    import ezdxf
    return ezdxf.readfile(path)

def register_source(points):
    from exact_template import find_reference
    source_path=find_reference("dxf")
    if not source_path:
        return None
    document=_source(source_path,os.path.getmtime(source_path))
    known={}
    for name,coordinate in points:
        key=_hp_id(name)
        if key and key not in known:
            known[key]=mercator(coordinate)
    if len(known)<80:
        return None
    cad={}
    for entity in document.modelspace():
        if entity.dxftype()=="TEXT" and entity.dxf.layer=="Homepass":
            key=_hp_id(entity.dxf.text)
            if key and key not in cad:
                cad[key]=(entity.dxf.insert.x,entity.dxf.insert.y)
    common=sorted(set(known)&set(cad))
    if len(common)<80:
        return None
    pairs=[(*cad[key],*known[key]) for key in common]
    try:
        transform=_fit(pairs)
        errors=[_residual(pair,transform) for pair in pairs]
        med=statistics.median(errors)
        if med>12:
            return None
        robust=[pair for pair,error in zip(pairs,errors)
                if error<max(8,med*3.0)]
        if len(robust)>=80:
            transform=_fit(robust)
        errors=[_residual(pair,transform) for pair in pairs]
        med=statistics.median(errors)
        ax,ay=transform
        det=ax[0]*ay[1]-ax[1]*ay[0]
        if not (.80<det<1.25 and med<8.0):
            return None
    except (ValueError,ArithmeticError,OverflowError):
        return None
    return document,transform,{"anchors":len(pairs),
        "median_error_m":round(med,2),"max_error_m":round(max(errors),2)}

def basemap_from_reference(points):
    """Return original DXF footprint/road linework georeferenced to KML.

    This is source geometry, not buildings guessed from OSM. An unrelated
    KML never passes numeric-geometric registration and falls back to OSM.
    """
    registered=register_source(points)
    if not registered:
        return None
    document,coeff,quality=registered
    ax,ay=coeff
    def geographic(p):
        x,y=p
        return unmercator((ax[0]*x+ax[1]*y+ax[2],
                           ay[0]*x+ay[1]*y+ay[2]))
    outline=[]
    roads=[]
    for entity in document.modelspace():
        layer=entity.dxf.layer
        if layer not in ("Basic Map","Jalan","railways","buildings"):
            continue
        if entity.dxftype()=="LWPOLYLINE":
            vertices=[geographic((x,y)) for x,y in entity.get_points("xy")]
        elif entity.dxftype()=="LINE":
            vertices=[geographic(entity.dxf.start[:2]),
                      geographic(entity.dxf.end[:2])]
        else:
            continue
        if len(vertices)<2:
            continue
        if layer in ("Basic Map","buildings"):
            outline.append(vertices)
        else:
            roads.append(vertices)
    if len(outline)<100:
        return None
    return {"_reference_basemap":True,
            "_reference_quality":quality,
            "reference_paths":outline,
            "reference_roads":roads}

def apply_reference_basemap(osm,points):
    source=basemap_from_reference(points)
    if source is None:
        return osm
    context=dict(osm or {})
    context.update(source)
    # Keep acquisition metadata but suppress mismatched OSM/Google linework.
    # Exact source footprint CAD is spatial authority for THIS project only.
    return context
