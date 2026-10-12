"""Road-only recovery for PBS NRP: adaptive Overpass failover + zero-road cache repair.

A separate highway-only acquisition avoids re-downloading Google Open Buildings.
It reuses successful OSM road tiles, refuses to treat cached zero-road results
as proof that a road network is available, and retains each successful tile.
No Geofabrik, binary extracts, new paid API or additional external dependency.
"""
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from osm_acquisition import (ENDPOINTS, _cache_name, _read_cache, _write_cache,
                             _tile_boxes, _split)

EMPTY_TTL_SECONDS=6*3600
COOLDOWN_SECONDS=90
RETRIABLE=(429,500,502,503,504)


def _road_cache_name(folder,bb):
    digest=hashlib.sha256(",".join(f"{v:.7f}" for v in bb).encode()).hexdigest()[:24]
    return os.path.join(folder,"roads_"+digest+".json")


def _roads_from_features(features):
    return [item for item in features
            if item.get("category")=="roads" and len(item.get("points",[]))>=2]


def _read_roads_cache(folder,bb,now,force_empty=False):
    # Prefer road-specific verified cache over shared all-features tile cache.
    dedicated=_read_cache(_road_cache_name(folder,bb))
    if dedicated is not None:
        roads=_roads_from_features(dedicated["features"])
        if roads:
            return roads,"CACHED_ROADS"
        checked=dedicated.get("checked_at")
        if (not force_empty and dedicated.get("verified_empty") and
                isinstance(checked,(int,float)) and
                0<=now-checked<EMPTY_TTL_SECONDS):
            return [],"CACHED_EMPTY"
    combined=_read_cache(_cache_name(folder,bb))
    if combined is not None:
        roads=_roads_from_features(combined["features"])
        if roads:
            return roads,"CACHED_ROADS"
        # IMPORTANT: a building-only cached tile has zero road features.
        # A historical false success must not hide the zero-road condition.
    return None,None


def _way_features(data):
    features=[]
    if not isinstance(data,dict) or not isinstance(data.get("elements"),list):
        raise ValueError("Invalid Overpass JSON")
    for item in data["elements"]:
        if item.get("type")!="way" or "highway" not in (item.get("tags") or {}):
            continue
        geometry=[(p["lon"],p["lat"]) for p in item.get("geometry",[])
                  if isinstance(p,dict)
                  and isinstance(p.get("lon"),(float,int))
                  and isinstance(p.get("lat"),(float,int))
                  and math.isfinite(p["lon"]) and math.isfinite(p["lat"])]
        if len(geometry)<2:
            continue
        features.append({"category":"roads","key":"roads:"+str(item.get("id","")),
                         "points":geometry})
    return features


def _overpass_roads(bb,endpoint,opener):
    west,south,east,north=bb
    box=",".join(f"{v:.7f}" for v in (south,west,north,east))
    # Highway ONLY. Never fetch footprints again in road recovery.
    query='[out:json][timeout:25];way["highway"]('+box+');out geom;'
    body=urllib.parse.urlencode({"data":query}).encode()
    request=urllib.request.Request(endpoint,data=body,
                   headers={"User-Agent":"PBS-NRP-Generator/1.0.22.6 (OSM road recovery)",
                            "Accept":"application/json"})
    with opener(request,timeout=36) as response:
        return _way_features(json.load(response))


def merge_recovered_roads(old_osm,recovery):
    """Preserve buildings/Google and prior successful roads if recovery partial."""
    merged=dict(old_osm or {})
    prior=merged.get("roads") or []
    seen=set()
    roads=[]
    for segment in list(prior)+list(recovery.get("roads") or []):
        if len(segment)<2:
            continue
        key=tuple((round(float(x),7),round(float(y),7)) for x,y in segment)
        if key not in seen:
            seen.add(key)
            roads.append(segment)
    merged["roads"]=roads
    merged["road_acquisition_status"]=recovery.get("status","FAILED")
    merged["road_success_tiles"]=recovery.get("successful_tiles",0)
    merged["road_failed_tiles"]=recovery.get("failed_tiles",0)
    merged["road_empty_tiles"]=recovery.get("empty_tiles",0)
    merged["road_warnings"]=recovery.get("warnings",[])
    merged["partial"]=bool(merged.get("partial") or
                           recovery.get("status") in ("PARTIAL","FAILED"))
    # RoadTopology polygons are computed from 'roads'; discard stale memo.
    merged.pop("_road_surfaces_v108",None)
    merged.pop("road_topology_stats",None)
    return merged


def fetch_roads_only(bb,cache_dir=None,progress=None,endpoints=None,
                     opener=None,sleep=None,clock=None,force_empty=False):
    """Return road-only acquisition result with finite, bounded failover.

    One tile per OSM tile; on service failure move to another independent
    configured instance. Repeatedly failing instances are placed in cooldown
    for the current run. A rate-limited server is never hammered per tile.
    Successful tiles persist. Empty tiles use a short TTL and are distinguishable
    from failed tiles. A manual retry can recheck verified-empty tiles.
    """
    bb=tuple(map(float,bb))
    west,south,east,north=bb
    if not (-180<=west<east<=180 and -90<=south<north<=90):
        raise ValueError("BBox jalan OSM tidak valid")
    folder=cache_dir or os.path.join(os.path.expanduser("~"),".pbs_nrp","osm_cache")
    os.makedirs(folder,exist_ok=True)
    instances=tuple(ENDPOINTS if endpoints is None else endpoints)
    if not instances:
        raise ValueError("Tidak ada server Overpass")
    opener=opener or urllib.request.urlopen
    sleep=sleep or time.sleep
    clock=clock or time.time
    progress=progress or (lambda text:None)
    tiles=list(_tile_boxes(bb))
    # Failure circuit breakers are per run. Do not permanently blacklist APIs.
    failures={e:0 for e in instances}
    blocked_until={e:0 for e in instances}
    features={}
    checked=0
    empty=0
    failed=0
    warnings=[]
    cache_hits=0

    def collect(items):
        for item in items:
            features[item["key"]]=item["points"]

    for i,tile in enumerate(tiles,1):
        progress(f"OSM ROAD tile {i}/{len(tiles)}: cache/failover...")
        cached,state=_read_roads_cache(folder,tile,clock(),force_empty)
        if state:
            cache_hits+=1
            checked+=1
            if state=="CACHED_EMPTY":
                empty+=1
            else:
                collect(cached)
            progress(f"OSM ROAD tile {i}/{len(tiles)}: {state}")
            continue

        acquired=False
        # Circuit-breaker avoids hammering a down server for every tile.
        for endpoint in sorted(instances,key=lambda e:failures[e]):
            if blocked_until[endpoint]>clock():
                continue
            host=urllib.parse.urlsplit(endpoint).hostname or endpoint
            progress(f"OSM ROAD tile {i}/{len(tiles)}: mencoba {host}")
            try:
                roads=_overpass_roads(tile,endpoint,opener)
                now=clock()
                _write_cache(_road_cache_name(folder,tile),
                    {"features":roads,"checked_at":now,
                     "verified_empty":not bool(roads),"source":host})
                checked+=1
                if not roads:
                    empty+=1
                collect(roads)
                acquired=True
                failures[endpoint]=0
                progress(f"OSM ROAD tile {i}/{len(tiles)}: "+
                         ("READY" if roads else "COMPLETE_EMPTY"))
                break
            except (urllib.error.HTTPError,urllib.error.URLError,
                    TimeoutError,OSError,ValueError) as exc:
                status=getattr(exc,"code",None)
                failures[endpoint]+=1
                if status==429 or failures[endpoint]>=2:
                    blocked_until[endpoint]=clock()+COOLDOWN_SECONDS
                reason=f"{host}: HTTP {status}" if status else f"{host}: {str(exc)[:90]}"
                warnings.append(reason)
                progress(f"OSM ROAD: {reason}, failover...")
                # Lightweight backoff; no busy polling or unbounded wait.
                if status in RETRIABLE:
                    sleep(min(.25*failures[endpoint],1.0))
        if not acquired:
            failed+=1
            progress(f"OSM ROAD tile {i}/{len(tiles)}: FAILED, lanjut tile lain")

    roads=list(features.values())
    status=("FAILED" if checked==0 else
            "PARTIAL" if failed else
            "COMPLETE_EMPTY" if not roads else "READY")
    return {"roads":roads,"status":status,"partial":bool(failed),
            "successful_tiles":checked,"failed_tiles":failed,
            "empty_tiles":empty,"cached_tiles":cache_hits,
            "total_tiles":len(tiles),"warnings":warnings[-10:],
            "source":"OpenStreetMap Overpass highway-only"}
