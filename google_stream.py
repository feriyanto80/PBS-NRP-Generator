"""Google Open Buildings v3: durable unlimited-size tile cache and extraction.

Only tiles intersecting the project are downloaded. CSV.GZ tiles can exceed 7GB.
Never read the whole archive into RAM. HTTP byte-range resume preserves partial
downloads and reuses complete tiles across DIFFERENT projects. The remaining
minimum free disk check protects the operating system; it is not a tile cap.
"""
import csv
import gzip
import hashlib
import http.client
import io
import json
import os
import shutil
import socket
import time
import urllib.error
import urllib.request

from shapely import wkt
from shapely.geometry import box

CHUNK_BYTES = 4*1024*1024
RETRIES = 8
MIN_SPARE_BYTES = 256*1024*1024


def default_cache():
    appdata = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and appdata:
        return os.path.join(appdata,"PBS_NRP_Generator","GoogleBuildings")
    return os.path.join(os.path.expanduser("~"),".pbs_nrp","google_cache")


def tile_paths(directory, identifier, url):
    # Untrusted manifest IDs must never become traversable filesystem paths.
    safe = "".join(c if c.isalnum() or c in ("-","_") else "_" for c in identifier)[:48]
    token = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    full = os.path.join(directory,"tiles",f"{safe}_{token}.csv.gz")
    return full,full+".part",full+".ready.json"


def _report(progress,label,bytes_now,bytes_total,started_at,base=0):
    pct = 100*bytes_now/bytes_total if bytes_total else None
    duration = max(.1,time.monotonic()-started_at)
    rate = max(0,(bytes_now-base)/duration)
    eta = max(0,(bytes_total-bytes_now)/rate) if bytes_total and rate>0 else None
    part=f"{bytes_now/(1024**3):.3f} GB"
    if bytes_total:
        part+=f"/{bytes_total/(1024**3):.3f} GB ({pct:.1f}%)"
    if rate:
        part+=f" | {rate/(1024**2):.1f} MB/s"
    if eta is not None:
        part+=f" | ETA {int(eta//60)}m {int(eta%60)}s"
    progress("Google Buildings | DOWNLOAD | "+label+" | "+part)


def _disk_guard(directory,estimated_left):
    # Keep enough free space for Windows/application stability; no fixed tile cap.
    free = shutil.disk_usage(directory).free
    needed = MIN_SPARE_BYTES + max(0,int(estimated_left))
    if free < needed:
        raise OSError(
            f"Disk tidak cukup untuk tile Google: kosong {free/(1024**3):.2f} GB; "
            f"perkiraan perlu {needed/(1024**3):.2f} GB. "
            "File .part tersimpan; kosongkan disk lalu klik Ambil/cache lagi.")


def download_tile(url, identifier, directory, size_mb=None, progress=None,
                  opener=None, chunk_bytes=CHUNK_BYTES, retries=RETRIES):
    """Stream download, use HTTP Range resume, persist complete compressed tiles."""
    progress = progress or (lambda msg: None)
    opener = opener or urllib.request.urlopen
    full, part, marker = tile_paths(directory,identifier,url)
    os.makedirs(os.path.dirname(full),exist_ok=True)
    if os.path.isfile(full) and os.path.isfile(marker):
        try:
            with open(marker,encoding="utf-8") as f:
                record=json.load(f)
            if record.get("url")==url and int(record.get("size",-1))==os.path.getsize(full):
                progress(f"Google Buildings | CACHE HIT | {identifier} | {os.path.getsize(full)/(1024**3):.3f} GB; unduhan dilewati")
                return full, True
        except (OSError,ValueError,TypeError):
            pass
    # Never silently use an incomplete tile as valid compressed CSV.
    if os.path.isfile(full) and not os.path.isfile(marker):
        progress(f"Google Buildings | CACHE VERIFY | {identifier}: metadata tidak ada, verifikasi ulang sumber")
        os.replace(full,part)
    expected = int(float(size_mb)*1024*1024) if size_mb is not None else None
    last_error=None
    for attempt in range(1,retries+1):
        offset = os.path.getsize(part) if os.path.exists(part) else 0
        # This check uses a size estimate only when available. It doesn't impose
        # an arbitrary cap. If the manifest is inaccurate, chunks are checked too.
        if expected:
            _disk_guard(directory,max(0,expected-offset))
        else:
            _disk_guard(directory,CHUNK_BYTES)
        headers={"User-Agent":"PBS-NRP-Generator/1.0.12","Accept-Encoding":"identity"}
        if offset:
            headers["Range"]=f"bytes={offset}-"
        request=urllib.request.Request(url,headers=headers)
        started=time.monotonic()
        previous_report=started
        initial=offset
        progress(f"Google Buildings | CONNECT {attempt}/{retries} | {identifier} | resume {offset/(1024**3):.3f} GB")
        try:
            with opener(request,timeout=90) as response:
                status=getattr(response,"status",None)
                if status is None and hasattr(response,"getcode"):
                    status=response.getcode()
                head=getattr(response,"headers",{}) or {}
                content_range=head.get("Content-Range","")
                content_length=head.get("Content-Length")
                if offset and status!=206:
                    # Server ignored Range: must overwrite, never append duplicate data.
                    offset=0
                    initial=0
                    progress(f"Google Buildings | RESTART | {identifier}: server tidak mendukung resume")
                if offset and status==206 and not str(content_range).startswith(f"bytes {offset}-"):
                    raise IOError(f"Content-Range tidak cocok: {content_range}")
                if content_length is not None:
                    expected=max(expected or 0,offset+int(content_length))
                _disk_guard(directory,max(0,(expected or (offset+CHUNK_BYTES))-offset))
                mode="ab" if offset else "wb"
                with open(part,mode) as output:
                    downloaded=offset
                    while True:
                        block=response.read(chunk_bytes)
                        if not block:
                            break
                        output.write(block)
                        downloaded+=len(block)
                        now=time.monotonic()
                        if now-previous_report>2 or downloaded-offset>=64*1024*1024 and previous_report==started:
                            _report(progress,identifier,downloaded,expected,started,initial)
                            previous_report=now
                        if downloaded%(128*1024*1024)<len(block):
                            _disk_guard(directory,max(0,(expected or downloaded)-downloaded))
                    output.flush()
                    os.fsync(output.fileno())
                # Detect truncated HTTP payloads, even if server closed "normally".
                if content_length and os.path.getsize(part) < offset+int(content_length):
                    raise IOError("Unduhan terputus sebelum Content-Length selesai")
                if expected is not None and os.path.getsize(part)<expected*0.999:
                    raise IOError(f"Unduhan masih sebagian ({os.path.getsize(part)} dari {expected} byte)")
            size=os.path.getsize(part)
            os.replace(part,full)
            meta={"url":url,"size":size,"tile_id":identifier,"completed_at":time.time()}
            temp_marker=marker+".tmp"
            with open(temp_marker,"w",encoding="utf-8") as output:
                json.dump(meta,output)
            os.replace(temp_marker,marker)
            _report(progress,identifier,size,size,started,initial)
            progress(f"Google Buildings | CACHE SAVED | {identifier} | {size/(1024**3):.3f} GB")
            return full,False
        except (urllib.error.URLError, OSError, ConnectionError,
                TimeoutError, socket.timeout, http.client.HTTPException) as exc:
            last_error=str(exc)
            progress(f"Google Buildings | RETRY {attempt}/{retries} | {identifier} | {last_error[:125]} | cache .part dipertahankan")
            if attempt<retries:
                time.sleep(min(5,attempt))
    raise IOError(f"Unduhan tile {identifier} belum selesai setelah {retries} percobaan: {last_error}. File .part tersimpan untuk Resume.")


def extract_region(gzip_path,bbox,confidence=.70,progress=None):
    """Scan compressed tile incrementally; materialize ONLY project-area polygons."""
    progress=progress or (lambda msg:None)
    region=box(*bbox)
    total_bytes=os.path.getsize(gzip_path)
    checked=0
    selected=[]
    last_report=time.monotonic()
    progress(f"Google Buildings | EXTRACT | mulai scan file cache {total_bytes/(1024**3):.3f} GB")
    try:
        with open(gzip_path,"rb") as raw:
            with gzip.GzipFile(fileobj=raw,mode="rb") as unzipped:
                with io.TextIOWrapper(unzipped,encoding="utf-8-sig",newline="") as reader:
                    rows=csv.DictReader(reader)
                    for row in rows:
                        checked+=1
                        try:
                            lat=float(row.get("latitude","nan"))
                            lon=float(row.get("longitude","nan"))
                            score=float(row.get("confidence","0"))
                        except (TypeError,ValueError):
                            continue
                        if score < confidence or not (bbox[0]<=lon<=bbox[2] and bbox[1]<=lat<=bbox[3]):
                            continue
                        geometry=row.get("geometry") or row.get("wkt")
                        if not geometry:
                            continue
                        try:
                            shape=wkt.loads(geometry)
                            if shape.is_empty or not shape.intersects(region):
                                continue
                            if not shape.is_valid:
                                shape=shape.buffer(0)
                            shape=shape.intersection(region)
                            pieces=([shape] if shape.geom_type=="Polygon" else
                                    [piece for piece in getattr(shape,"geoms",[])
                                     if piece.geom_type=="Polygon"])
                            for piece in pieces:
                                if piece.area>1e-13:
                                    selected.append([(float(x),float(y)) for x,y in piece.exterior.coords])
                        except (ValueError,TypeError,AttributeError):
                            continue
                        now=time.monotonic()
                        if now-last_report>=3:
                            pct=100*min(total_bytes,raw.tell())/max(1,total_bytes)
                            progress(f"Google Buildings | EXTRACT | {pct:.1f}% file | {checked:,} baris | {len(selected):,} footprint proyek")
                            last_report=now
    except (OSError,EOFError,gzip.BadGzipFile) as exc:
        raise IOError(f"Cache Google gzip rusak/tidak lengkap: {exc}") from exc
    progress(f"Google Buildings | EXTRACT DONE | {checked:,} baris diperiksa | {len(selected):,} bangunan dalam boundary")
    return selected
