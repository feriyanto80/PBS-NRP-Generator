"""Footprint source fusion: OSM + input KML/KMZ + supplemental Open Buildings.

Supports GeoJSON, KML/KMZ and Google Open Buildings CSV/CSV.GZ (WKT polygons).
No fake buildings: only polygons from supplied datasets are included.
"""
import csv
import gzip
import json
import math
import os
import zipfile
from collections import defaultdict
from xml.etree import ElementTree as ET

try:
    from shapely.geometry import Polygon, box, shape
    from shapely import wkt as shapely_wkt
except ImportError as exc:
    raise RuntimeError("shapely dibutuhkan untuk footprint GIS") from exc

MAX_SOURCE_POLYGONS = 150000


def _name(tag):
    return tag.rsplit("}", 1)[-1]


def _coordinates(value):
    pts = []
    for part in (value or "").split():
        try:
            lon, lat = map(float, part.split(",")[:2])
            if -180 <= lon <= 180 and -90 <= lat <= 90 and math.isfinite(lon) and math.isfinite(lat):
                pts.append((lon, lat))
        except (TypeError, ValueError):
            pass
    return pts


def _polygons_from_kml(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("KML XML tidak valid") from exc
    for node in root.iter():
        if _name(node.tag) != "Polygon":
            continue
        outer = next((x for x in node.iter() if _name(x.tag) == "outerBoundaryIs"), None)
        if outer is None:
            continue
        coords = next((x.text for x in outer.iter() if _name(x.tag) == "coordinates"), "")
        pts = _coordinates(coords)
        if len(pts) >= 3:
            yield pts


def _polygon_rings(geom):
    if not geom or geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        if geom.area > 1e-13:
            yield list(geom.exterior.coords)
    elif geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        for g in geom.geoms:
            yield from _polygon_rings(g)


def _geojson_polygons(data):
    payload = json.loads(data)
    features = payload.get("features") if isinstance(payload, dict) else None
    if features is None:
        features = [payload]
    for entry in features:
        geometry = (entry.get("geometry") or {}) if entry.get("type") == "Feature" else entry
        if not geometry or geometry.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        try:
            yield from _polygon_rings(shape(geometry))
        except (TypeError, ValueError):
            continue


def _wkt_polygons(path, min_confidence, limit):
    opener = gzip.open if path.lower().endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames or []
        wkt_column = next((v for v in names if v.lower() in
                           ("geometry", "wkt", "polygon", "building_polygon")), None)
        if not wkt_column:
            raise ValueError("CSV Google harus memiliki kolom geometry/WKT/polygon")
        for i, row in enumerate(reader):
            if i >= limit:
                raise ValueError(f"File terlalu besar: batas baca {limit:,} baris. Ekspor area desa saja.")
            raw_conf = row.get("confidence") or row.get("confidence_score") or "1"
            try:
                confidence = float(raw_conf)
            except (TypeError, ValueError):
                continue
            if confidence < min_confidence:
                continue
            raw = row.get(wkt_column) or ""
            if not raw:
                continue
            try:
                yield from _polygon_rings(shapely_wkt.loads(raw))
            except Exception:
                continue


def load_polygons(path, bbox=None, min_confidence=0.70, limit=MAX_SOURCE_POLYGONS):
    """Load real polygons from source; bbox restricts imports to project extent."""
    ext = os.path.basename(path).lower()
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if ext.endswith(".kmz"):
        with zipfile.ZipFile(path) as kmz:
            names = [v for v in kmz.namelist() if v.lower().endswith(".kml")]
            if not names:
                raise ValueError("KMZ tidak memiliki file KML")
            name = next((v for v in names if v.lower() == "doc.kml"), names[0])
            candidates = _polygons_from_kml(kmz.read(name))
            iterator = list(candidates)
    elif ext.endswith(".kml"):
        with open(path, "rb") as handle:
            iterator = list(_polygons_from_kml(handle.read()))
    elif ext.endswith((".geojson", ".json")):
        with open(path, "r", encoding="utf-8-sig") as handle:
            iterator = list(_geojson_polygons(json.load(handle)))
    elif ext.endswith((".csv", ".csv.gz")):
        iterator = _wkt_polygons(path, min_confidence, limit)
    else:
        raise ValueError("Footprint: gunakan KML, KMZ, GeoJSON, CSV atau CSV.GZ/WKT")
    extent = box(*bbox) if bbox is not None else None
    polygons, discarded = [], 0
    for raw in iterator:
        if len(polygons) >= limit:
            raise ValueError(f"Terlalu banyak footprint (>{limit:,}), kecilkan area")
        try:
            polygon = Polygon(raw)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty:
                discarded += 1
                continue
            if extent is not None:
                if not polygon.intersects(extent):
                    discarded += 1
                    continue
                polygon = polygon.intersection(extent)
            for ring in _polygon_rings(polygon):
                if len(ring) >= 4:
                    polygons.append([(float(x), float(y)) for x, y in ring])
        except (TypeError, ValueError, AttributeError):
            discarded += 1
    return {"polygons": polygons, "discarded": discarded, "file": os.path.basename(path)}


def _cell(p, size):
    lon, lat = p
    return (int(math.floor(lon / size)), int(math.floor(lat / size)))


def merge_sources(osm=None, kml=None, google=None):
    """Prefer OSM, then input KML, then supplemental source.

    Centroid-grid only limits candidates; actual polygon IoU >= .45
    is required before removing a duplicate.
    """
    osm = osm or {}
    grid = defaultdict(list)
    merged = []
    per_source = {"OSM": 0, "KML": 0, "GOOGLE": 0}
    duplicates = 0
    cell_size = .00025
    for source, polygons in (
        ("OSM", osm.get("buildings", [])),
        ("KML", kml or []),
        ("GOOGLE", google or []),
    ):
        for raw in polygons:
            try:
                poly = Polygon(raw)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.geom_type != "Polygon" or poly.area < 1e-13:
                    continue
                center = poly.centroid
                cell = _cell((center.x, center.y), cell_size)
                neighbors = [(cell[0] + dx, cell[1] + dy)
                             for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                is_duplicate = False
                for region in neighbors:
                    for candidate in grid[region]:
                        inter = poly.intersection(candidate).area
                        if inter > 0 and inter / max(1e-13, poly.area + candidate.area - inter) >= .45:
                            is_duplicate = True
                            break
                    if is_duplicate:
                        break
                if is_duplicate:
                    duplicates += 1
                    continue
                grid[cell].append(poly)
                merged.append(list(poly.exterior.coords))
                per_source[source] += 1
            except (ValueError, TypeError, AttributeError):
                continue
    output = dict(osm)
    output["buildings"] = merged
    output.setdefault("roads", [])
    output["footprint_sources"] = per_source
    output["footprint_duplicates"] = duplicates
    output["footprint_total"] = len(merged)
    output["footprint_source_label"] = "OSM + KML + SUPPLEMENTAL"
    output["partial"] = bool(osm.get("partial"))
    return output
