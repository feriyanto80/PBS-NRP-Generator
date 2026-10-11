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


def acquire_google(bbox, progress=None, cache_dir=None, opener=None,
                   max_download_mb=None, max_tiles=None,
                   min_confidence=.70, manifest=None, tile_loader=None):
    """Download ALL Google V3 tiles crossing the project, without a size cap.

    Complete compressed tiles are cached permanently; interrupted transfers
    are resumed via HTTP Range, and regional polygons are cached separately.
    A minimum free-disk reserve remains mandatory for machine safety.
    Legacy size-limit parameters are accepted but intentionally ignored.
    """
    from google_stream import download_tile, extract_region, default_cache

    progress = progress or (lambda msg:None)
    directory = cache_dir or default_cache()
    opener = opener or urllib.request.urlopen
    os.makedirs(directory,exist_ok=True)
    bb = tuple(map(float,bbox))
    if len(bb)!=4 or not (-180<=bb[0]<bb[2]<=180 and -90<=bb[1]<bb[3]<=90):
        raise ValueError("Boundary Google tidak valid")
    key=hashlib.sha256((",".join(f"{v:.7f}" for v in bb)+f":v3:{min_confidence}").encode()).hexdigest()[:22]
    path=os.path.join(directory,"regions","region_"+key+".json")
    if os.path.isfile(path):
        try:
            with open(path,encoding="utf-8") as handle:
                saved=json.load(handle)
            if saved.get("complete") and saved.get("source")=="GOOGLE_OPEN_BUILDINGS_V3":
                saved["cache_hit"]=True
                progress(f"Google Buildings | REGION CACHE HIT | {len(saved.get('polygons',[])):,} footprint proyek, tanpa scan ulang")
                return saved
        except (OSError,ValueError,TypeError):
            pass
    progress("Google Buildings | fase 1/4: membaca katalog tile resmi (cache 14 hari)")
    try:
        data=manifest if manifest is not None else _catalog(directory,opener)
    except (OSError,ValueError,urllib.error.URLError) as exc:
        return {"polygons":[],"source":"GOOGLE_OPEN_BUILDINGS_V3",
                "status":"unavailable","reason":"Katalog Google gagal: "+str(exc)[:180],
                "complete":False,"cache_dir":directory}
    progress("Google Buildings | fase 2/4: filter tile yang beririsan dengan batas proyek")
    tiles=_matching_tiles(data,bb)
    if not tiles:
        return {"polygons":[],"source":"GOOGLE_OPEN_BUILDINGS_V3",
                "status":"no_coverage","reason":"Belum ada tile Google untuk boundary ini",
                "complete":False,"cache_dir":directory}
    progress(f"Google Buildings | {len(tiles)} tile relevan | TANPA batas ukuran/jumlah, cache {directory}")
    polygons=[]
    failures=[]
    reused=0
    for index,(ident,url,size_mb) in enumerate(tiles,1):
        estimate=(f"{size_mb:,.0f} MB" if size_mb else "ukuran tidak tersedia")
        progress(f"Google Buildings | fase 3/4: tile {index}/{len(tiles)} {ident} | {estimate} | unduh/resume")
        try:
            if tile_loader is not None:
                # Injectable offline test hook. Production always uses disk.
                extracted=tile_loader(url,bb)
            else:
                def report(msg,index=index,total=len(tiles)):
                    progress(f"Google Buildings | TILE {index}/{total} | "+msg)
                archive,cache_hit=download_tile(
                    url,ident,directory,size_mb=size_mb,
                    progress=report,opener=opener)
                reused+=int(cache_hit)
                extracted=extract_region(archive,bb,confidence=min_confidence,progress=report)
            polygons.extend(extracted)
            progress(f"Google Buildings | tile {index}/{len(tiles)} DONE | {len(extracted):,} polygon area | total {len(polygons):,}")
        except (OSError,ValueError,TypeError,urllib.error.URLError) as exc:
            reason=f"{ident}: {str(exc)[:250]}"
            failures.append(reason)
            progress(f"Google Buildings | tile {index}/{len(tiles)} ERROR | {reason} | cache parsial dipertahankan")
    progress(f"Google Buildings | fase 4/4: {len(polygons):,} footprint; tile berhasil {len(tiles)-len(failures)}/{len(tiles)}; cache hit {reused}")
    complete=not failures
    result={"polygons":polygons,"source":"GOOGLE_OPEN_BUILDINGS_V3",
            "status":"ready" if complete else ("partial" if polygons else "unavailable"),
            "reason":"; ".join(failures[:3]),
            "complete":complete,"tiles_found":len(tiles),"tiles_failed":len(failures),
            "tiles_cached":reused,"cache_hit":False,"cache_dir":directory,
            "confidence":min_confidence}
    if complete:
        _atomic_json(path,result)
    return result
