"""Junction-aware schematic road corridor topology for OSM network lines.

Each OSM centerline is buffered in local metric space. All road surfaces
are unioned BEFORE plotting boundaries: overlapping side offsets disappear,
T/X junctions become joined contours and bends receive round joins.

Width inferred from OSM road_widths if provided; otherwise SCHEMATIC width,
not surveyed road right-of-way.
"""
import math
from shapely.geometry import LineString
from shapely.ops import unary_union

DEFAULT_WIDTH_M = 5.5
MAX_WIDTH_M = 26.0
MIN_WIDTH_M = 1.8


def build_road_surfaces(osm):
    """Return polygons [{exterior, holes}] in lon/lat. Memoized on osm dict."""
    if not osm or not osm.get('roads'):
        return []
    old = osm.get('_road_surfaces_v108')
    if old is not None:
        return old
    roads = osm['roads']
    points = [p for line in roads if len(line) >= 2 for p in (line[0], line[-1])]
    if not points:
        return []
    lon0 = sum(float(p[0]) for p in points) / len(points)
    lat0 = sum(float(p[1]) for p in points) / len(points)
    xscale = 111320.0 * max(0.01, math.cos(math.radians(lat0)))
    yscale = 110574.0
    widths = osm.get('road_widths') or []
    shapes = []
    for index, way in enumerate(roads):
        if len(way) < 2:
            continue
        coords = []
        for lon, lat in way:
            try:
                xy = ((float(lon)-lon0)*xscale, (float(lat)-lat0)*yscale)
                if not math.isfinite(xy[0]) or not math.isfinite(xy[1]):
                    continue
                if not coords or math.dist(xy, coords[-1]) >= 0.04:
                    coords.append(xy)
            except (TypeError, ValueError):
                continue
        if len(coords) < 2:
            continue
        try:
            width = float(widths[index]) if index < len(widths) else DEFAULT_WIDTH_M
        except (ValueError, TypeError):
            width = DEFAULT_WIDTH_M
        if not math.isfinite(width):
            width = DEFAULT_WIDTH_M
        width = max(MIN_WIDTH_M, min(MAX_WIDTH_M, width))
        try:
            surface = LineString(coords).buffer(width / 2.0, resolution=5,
                                               cap_style=1, join_style=1)
            if not surface.is_empty:
                shapes.append(surface)
        except (ValueError, TypeError):
            continue
    if not shapes:
        osm['_road_surfaces_v108'] = []
        return []
    merged = unary_union(shapes).simplify(0.12, preserve_topology=True)
    def lonlat(point):
        return (point[0]/xscale+lon0, point[1]/yscale+lat0)
    def iter_polygons(geom):
        if geom.geom_type == 'Polygon':
            yield geom
        elif hasattr(geom, 'geoms'):
            for member in geom.geoms:
                yield from iter_polygons(member)
    output = []
    for poly in iter_polygons(merged):
        if poly.area < 0.5:
            continue
        ext = [lonlat(point) for point in poly.exterior.coords]
        holes = [[lonlat(point) for point in interior.coords]
                 for interior in poly.interiors if interior.length > 1.0]
        output.append({'exterior':ext, 'holes':holes})
    osm['_road_surfaces_v108'] = output
    osm['road_topology_stats'] = {
        'raw_osm_ways': len(roads),
        'joined_corridors': len(output),
        'junction_mode': 'BUFFER_UNION_ROUND',
        'width_source': 'OSM width or schematic default',
    }
    return output


def iter_road_boundaries(osm):
    """Yield merged road exterior/interior outlines for PDF and DXF."""
    for polygon in build_road_surfaces(osm):
        yield polygon['exterior']
        yield from polygon['holes']
