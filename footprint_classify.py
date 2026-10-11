"""Strict classification of KML/KMZ Polygon geometries.

Polygons are NOT automatically buildings. Field design KMLs often contain
parcels, administrative areas, cultivation plots and right-of-way corridors.
Only explicit building metadata or building/house/footprint placemark names
qualify as buildings. All other polygons are counted separately and excluded
from the building overlay; no guessed roofs are generated.
"""
import os
import re
import zipfile
from xml.etree import ElementTree as ET

from shapely.geometry import Polygon, box

POSITIVE = re.compile(r"(?i)(?:^|[\s_:/-])(building|buildings|bangunan|rumah|gedung|footprint|atap|house|houses|roof|rooftop)(?=$|[\s_:/-])")
NEGATIVE = re.compile(r"(?i)(boundary|batas|administrasi|parcel|persil|kavling|lot\s|bidang\s*tanah|lahan|sawah|kebun|ladang|area\s*kerja|wilayah|road|jalan|right.of.way|rt[/_ -]|rw[/_ -])")


def _name(tag):
    return tag.rsplit("}",1)[-1]


def _values(node):
    for item in node.iter():
        key=item.attrib.get("name","")
        tag=_name(item.tag).lower()
        if key and tag in ("data","simpledata"):
            if tag=="data":
                val=next((x.text for x in item if _name(x.tag).lower()=="value"),"")
            else:
                val=item.text
            yield key.lower().strip(),(val or "").lower().strip()


def _explicit_building(placemark):
    name=next(((x.text or "").strip() for x in placemark
               if _name(x.tag)=="name"),"")
    has_tag=False
    for key,value in _values(placemark):
        if key in ("building","building:part","building_type") and value in (
            "yes","house","residential","commercial","industrial","apartments",
            "detached","semidetached_house","roof","building","buildings"):
            has_tag=True
    if has_tag:
        return True
    if NEGATIVE.search(name):
        return False
    return POSITIVE.search(name) is not None


def _coord(text):
    out=[]
    for item in (text or "").split():
        pair=item.split(",")
        if len(pair)<2:continue
        try:
            x,y=float(pair[0]),float(pair[1])
        except ValueError:
            continue
        if -180<=x<=180 and -90<=y<=90:
            out.append((x,y))
    return out


def audit_main_kml(path,bbox):
    """Return only confirmed building footprints; raw and ignored counts audited."""
    path=os.fspath(path)
    if path.lower().endswith(".kmz"):
        with zipfile.ZipFile(path) as package:
            names=[x for x in package.namelist() if x.lower().endswith(".kml")]
            if not names:
                raise ValueError("KMZ tidak mempunyai KML")
            name=next((n for n in names if n.lower()=="doc.kml"),names[0])
            raw=package.read(name)
    elif path.lower().endswith(".kml"):
        with open(path,"rb") as handle:
            raw=handle.read()
    else:
        raise ValueError("File jaringan harus KML atau KMZ")
    root=ET.fromstring(raw)
    region=box(*bbox)
    raw_polygons=0
    ignored=0
    invalid=0
    accepted=[]
    confirmed_features=0
    for feature in root.iter():
        if _name(feature.tag)!="Placemark":
            continue
        explicit=_explicit_building(feature)
        for poly in feature.iter():
            if _name(poly.tag)!="Polygon":
                continue
            raw_polygons+=1
            if not explicit:
                ignored+=1
                continue
            outer=next((x for x in poly if _name(x.tag)=="outerBoundaryIs"),None)
            if outer is None:
                invalid+=1
                continue
            vals=next((x.text for x in outer.iter() if _name(x.tag)=="coordinates"),"")
            coords=_coord(vals)
            if len(coords)<3:
                invalid+=1
                continue
            polygon=Polygon(coords)
            if not polygon.is_valid:
                polygon=polygon.buffer(0)
            if polygon.is_empty:
                invalid+=1
                continue
            if not polygon.intersects(region):
                continue
            polygon=polygon.intersection(region)
            geometries=[polygon] if polygon.geom_type=="Polygon" else list(getattr(polygon,"geoms",[]))
            appended=False
            for geom in geometries:
                if geom.geom_type=="Polygon" and geom.area>1e-13:
                    accepted.append(list(geom.exterior.coords))
                    appended=True
            if appended:
                confirmed_features+=1
    return {"polygons":accepted,"raw_polygons":raw_polygons,
            "unclassified_polygons":ignored,"invalid_polygons":invalid,
            "confirmed_features":confirmed_features,"classification":"EXPLICIT_BUILDING_ONLY"}
