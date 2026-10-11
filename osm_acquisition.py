"""OpenStreetMap acquisition with Overpass failover, bounded tiles and persistent cache."""
import hashlib
import json
import math
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINTS = (
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
TILE_SIZE = 0.015
MAX_TILES = 196


def _cache_name(folder, bb):
    key = hashlib.sha256(",".join(f"{v:.7f}" for v in bb).encode()).hexdigest()[:24]
    return os.path.join(folder, "tile_" + key + ".json")


def _read_cache(path):
    try:
        with open(path, encoding="utf8") as f:
            obj = json.load(f)
        if isinstance(obj.get("features"), list):
            return obj
    except (OSError, ValueError, AttributeError, UnicodeError):
        pass
    return None


def _write_cache(path, obj):
    fd, tmp = tempfile.mkstemp(prefix=".osm-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as f:
            json.dump(obj, f, separators=(",", ":"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _get_one(bb, cache_dir, endpoints, opener, sleep, progress):
    cached_path = _cache_name(cache_dir, bb)
    cached = _read_cache(cached_path)
    if cached is not None:
        return cached
    w, s, e, n = bb
    box = ",".join(f"{v:.7f}" for v in (s, w, n, e))
    query = f'[out:json][timeout:35];(way["highway"]({box});way["building"]({box}););out geom;'
    request_body = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for index, endpoint in enumerate(endpoints):
        progress(f"OSM: server cadangan {index + 1}/{len(endpoints)}")
        request = urllib.request.Request(endpoint, data=request_body, headers={
            "User-Agent": "PBS-NRP-Generator/1.0.5 (+OSM)",
            "Accept": "application/json"})
        try:
            with opener(request, timeout=45) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
                raise ValueError("Overpass returned invalid JSON")
            features = []
            for element in payload["elements"]:
                if element.get("type") != "way":
                    continue
                tags = element.get("tags") or {}
                geometry = [(p["lon"], p["lat"]) for p in element.get("geometry", [])
                            if isinstance(p, dict) and isinstance(p.get("lon"), (int, float))
                            and isinstance(p.get("lat"), (int, float))
                            and math.isfinite(p["lon"]) and math.isfinite(p["lat"])]
                if len(geometry) < 2:
                    continue
                for category, tag in (("roads", "highway"), ("buildings", "building")):
                    if tag in tags:
                        features.append({"key": f'{category}:{element.get("id", "")}',
                                         "category": category, "points": geometry})
            result = {"features": features}
            _write_cache(cached_path, result)
            return result
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                OSError, ValueError) as exc:
            errors.append(f"{endpoint.split('/')[2]}: {str(exc)[:95]}")
            # A mirror may reject a request with 403/404 while other mirrors work.
            # Try all configured instances before considering tile subdivision.
            if index < len(endpoints) - 1:
                sleep(min(.25 + index * .5, 1))
    raise RuntimeError("Semua server OSM gagal: " + " | ".join(errors))


def _tile_boxes(bb):
    w, s, e, n = bb
    nx = max(1, math.ceil((e - w) / TILE_SIZE))
    ny = max(1, math.ceil((n - s) / TILE_SIZE))
    if nx * ny > MAX_TILES:
        raise ValueError(f"Area terlalu luas ({nx * ny} tile). Gunakan file boundary proyek lebih kecil.")
    for y in range(ny):
        for x in range(nx):
            yield (w + (e - w) * x / nx, s + (n - s) * y / ny,
                   w + (e - w) * (x + 1) / nx, s + (n - s) * (y + 1) / ny)


def _split(bb):
    w, s, e, n = bb
    x, y = (w + e) / 2, (s + n) / 2
    return ((w, s, x, y), (x, s, e, y), (w, y, x, n), (x, y, e, n))


def fetch_osm(bb, cache_dir=None, progress=None, endpoints=None, opener=None, sleep=None):
    """Fetch real OSM geometry, retaining successful cached tiles across retries.

    Injectable opener, endpoints, sleep allow offline unit tests.
    """
    if len(bb) != 4 or not all(math.isfinite(float(v)) for v in bb):
        raise ValueError("BBox tidak valid")
    bb = tuple(map(float, bb))
    w, s, e, n = bb
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("BBox di luar batas longitude/latitude")
    folder = cache_dir or os.path.join(os.path.expanduser("~"), ".pbs_nrp", "osm_cache")
    os.makedirs(folder, exist_ok=True)
    endpoints = ENDPOINTS if endpoints is None else tuple(endpoints)
    if not endpoints:
        raise ValueError("Tidak ada server Overpass")
    opener = opener or urllib.request.urlopen
    sleep = sleep or time.sleep
    progress = progress or (lambda msg: None)
    tiles = list(_tile_boxes(bb))
    unique, errors = {}, []
    successes = 0

    def get_region(region, depth=0):
        nonlocal successes
        try:
            result = _get_one(region, folder, endpoints, opener, sleep, progress)
            for f in result["features"]:
                unique[f["key"]] = (f["category"], f["points"])
            successes += 1
            return
        except RuntimeError as exc:
            if depth < 2 and max(region[2] - region[0], region[3] - region[1]) > .0025:
                progress("OSM: server sibuk, pecah tile untuk retry...")
                for child in _split(region):
                    get_region(child, depth + 1)
                return
            errors.append(str(exc))

    for number, tile in enumerate(tiles, start=1):
        progress(f"OSM tile {number}/{len(tiles)}: membaca cache atau mengunduh...")
        get_region(tile)
    if successes == 0:
        raise RuntimeError("OSM gagal: " + (errors[0] if errors else "Tidak ada tile berhasil"))
    roads = [pts for cat, pts in unique.values() if cat == "roads"]
    buildings = [pts for cat, pts in unique.values() if cat == "buildings"]
    return {"roads": roads, "buildings": buildings, "source": "OpenStreetMap via Overpass",
            "bbox": bb, "partial": bool(errors), "failed_tiles": len(errors),
            "successful_tiles": successes, "total_tiles": len(tiles), "warnings": errors[:4]}
