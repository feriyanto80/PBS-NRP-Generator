"""Automatic optional Google Open Buildings V3 tile enrichment.

Official polygon tiles are very large (occasionally GB). Only safely sized
public gzip CSV tiles are downloaded. Skipped Google tiles are reported and
never presented as acquired footprints.
"""
import csv
import gzip
import hashlib
import io
import json
import os
import tempfile
import time
import urllib.error
import urllib.request

from shapely.geometry import box, shape
from shapely import wkt

MANIFEST_URL = "https://openbuildings-public-dot-gweb-research.uw.r.appspot.com/public/tiles.geojson"
TILE_PREFIX = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/"
MAX_DOWNLOAD_MB = 80
MAX_TILES = 2
MAX_FOOTPRINTS = 50000


def _atomic_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".google_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _catalog(cache_dir, opener):
    path = os.path.join(cache_dir, "open_buildings_v3_tiles.json")
    if os.path.isfile(path) and time.time()-os.path.getmtime(path)<14*86400:
        try:
            with open(path, encoding="utf-8") as handle:
                saved=json.load(handle)
            if saved.get("type")=="FeatureCollection":
                return saved
        except (OSError,ValueError,AttributeError):
            pass
    req=urllib.request.Request(MANIFEST_URL, headers={"User-Agent":"PBS-NRP-Generator/1.0.10"})
    with opener(req, timeout=20) as response:
        raw=response.read(12*1024*1024+1)
    if len(raw)>12*1024*1024:
        raise ValueError("Katalog Google melebihi batas 12 MB")
    manifest=json.loads(raw)
    if not isinstance(manifest,dict) or manifest.get("type")!="FeatureCollection":
        raise ValueError("Katalog Google tidak valid")
    _atomic_json(path,manifest)
    return manifest


def _matching_tiles(manifest,bbox):
    region=box(*bbox)
    found=[]
    for entry in manifest.get("features",[]):
        info=entry.get("properties") or {}
        url=info.get("tile_url") or ""
        if not isinstance(url,str) or not url.startswith(TILE_PREFIX) or not url.endswith(".csv.gz"):
            continue
        try:
            if not shape(entry.get("geometry") or {}).intersects(region):
                continue
        except (TypeError,ValueError,AttributeError):
            continue
        try:
            size=float(info.get("size_mb"))
        except (TypeError,ValueError):
            size=None
        found.append((str(info.get("tile_id","tile")), url, size))
    return found


def _load_tile(url,bbox,opener,confidence,max_bytes,max_count):
    request=urllib.request.Request(url,headers={"User-Agent":"PBS-NRP-Generator/1.0.9"})
    with opener(request,timeout=60) as response:
        amount=response.headers.get("Content-Length") if hasattr(response,"headers") else None
        if amount and int(amount)>max_bytes:
            raise ValueError("Tile Google terlalu besar")
        raw=response.read(max_bytes+1)
    if len(raw)>max_bytes:
        raise ValueError("Tile Google melebihi batas unduh")
    polygons=[]
    extent=box(*bbox)
    with gzip.GzipFile(fileobj=io.BytesIO(raw),mode="rb") as gz:
        rows=csv.DictReader(io.TextIOWrapper(gz,encoding="utf-8-sig"))
        for row in rows:
            try:
                score=float(row.get("confidence","0"))
                lon=float(row.get("longitude","nan"))
                lat=float(row.get("latitude","nan"))
            except (TypeError,ValueError):
                continue
            if score<confidence or not (bbox[0]<=lon<=bbox[2] and bbox[1]<=lat<=bbox[3]):
                continue
            rawgeom=row.get("geometry") or row.get("wkt")
            if not rawgeom:
                continue
            try:
                geom=wkt.loads(rawgeom)
                if geom.is_empty or not geom.intersects(extent):
                    continue
                if not geom.is_valid:
                    geom=geom.buffer(0)
                geom=geom.intersection(extent)
                if geom.geom_type=="Polygon":
                    pieces=[geom]
                elif hasattr(geom,"geoms"):
                    pieces=[g for g in geom.geoms if g.geom_type=="Polygon"]
                else:
                    pieces=[]
                for polygon in pieces:
                    if polygon.area>=1e-13:
                        polygons.append([tuple(map(float,p)) for p in polygon.exterior.coords])
                        if len(polygons)>max_count:
                            raise ValueError("Batas jumlah bangunan terlampaui")
            except (TypeError,ValueError,AttributeError):
                continue
    return polygons


def acquire_google(bbox, progress=None, cache_dir=None, opener=None,
                   max_download_mb=MAX_DOWNLOAD_MB, max_tiles=MAX_TILES,
                   min_confidence=.70, manifest=None, tile_loader=None):
    """Return polygons, status, reason. No Google data is invented on failure."""
    progress=progress or (lambda message:None)
    opener=opener or urllib.request.urlopen
    directory=cache_dir or os.path.join(os.path.expanduser("~"),".pbs_nrp","google_cache")
    os.makedirs(directory,exist_ok=True)
    bb=tuple(map(float,bbox))
    if len(bb)!=4 or not (-180<=bb[0]<bb[2]<=180 and -90<=bb[1]<bb[3]<=90):
        raise ValueError("Boundary Google tidak valid")
    key=hashlib.sha256((", ".join(f"{v:.7f}" for v in bb)+f":v3:{min_confidence}").encode()).hexdigest()[:22]
    path=os.path.join(directory,"region_"+key+".json")
    if os.path.isfile(path):
        try:
            with open(path,encoding="utf-8") as handle:
                result=json.load(handle)
            if result.get("complete") and result.get("source")=="GOOGLE_OPEN_BUILDINGS_V3":
                result["cache_hit"]=True
                progress("Google Buildings: menggunakan cache regional")
                return result
        except (OSError,ValueError,AttributeError):
            pass
    try:
        progress("Google Buildings: memeriksa katalog tile resmi")
        data=manifest if manifest is not None else _catalog(directory,opener)
    except (OSError,ValueError,urllib.error.URLError) as exc:
        return {"polygons":[],"source":"GOOGLE_OPEN_BUILDINGS_V3","status":"unavailable",
                "reason":"Katalog Google gagal: "+str(exc)[:160],"complete":False}
    tiles=_matching_tiles(data,bb)
    if not tiles:
        return {"polygons":[],"source":"GOOGLE_OPEN_BUILDINGS_V3","status":"no_coverage",
                "reason":"Tidak ada cakupan tile Google V3","complete":False}
    budget=int(max_download_mb*1024*1024)
    selected=[]
    skipped=[]
    for ident,url,size in tiles:
        if size is not None and size>max_download_mb:
            skipped.append(f"{ident}: {size:.0f} MB")
        elif len(selected)>=max_tiles:
            skipped.append(f"{ident}: batas jumlah tile")
        else:
            selected.append((ident,url))
    if not selected:
        return {"polygons":[],"source":"GOOGLE_OPEN_BUILDINGS_V3",
                "status":"skipped_large","complete":False,
                "tiles_found":len(tiles),"tiles_skipped":len(skipped),
                "reason":"Tile Google terlalu besar: "+", ".join(skipped[:3])}
    polygons=[]
    errors=[]
    for index,(ident,url) in enumerate(selected,1):
        progress(f"Google Buildings tile {index}/{len(selected)}: {ident}")
        try:
            data=(tile_loader(url,bb) if tile_loader else
                  _load_tile(url,bb,opener,min_confidence,budget,MAX_FOOTPRINTS-len(polygons)))
            polygons.extend(data)
        except (ValueError,OSError,urllib.error.URLError) as exc:
            errors.append(f"{ident}: {str(exc)[:100]}")
    complete=not errors and not skipped
    result={"polygons":polygons,"source":"GOOGLE_OPEN_BUILDINGS_V3",
            "status":"ready" if complete else ("partial" if polygons else "unavailable"),
            "reason":"; ".join((errors+skipped)[:3]),"complete":complete,
            "tiles_found":len(tiles),"tiles_skipped":len(skipped),
            "cache_hit":False,"confidence":min_confidence}
    if complete:
        _atomic_json(path,result)
    return result
