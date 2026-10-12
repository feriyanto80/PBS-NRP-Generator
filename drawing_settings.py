"""PBS NRP v1.0.13 presentation controls. No network data is modified.

This module filters rendered/exported layers and passes symbol settings through
the renderer's per-project metadata; original KML/OSM features remain intact.
"""
DEFAULTS = {
    "feeder": True, "subfeeder": True, "distribution": True,
    "points": True, "roads": True, "buildings": True,
    "point_labels": True, "point_size": 2.0,
}

def normalized(values=None):
    result=dict(DEFAULTS)
    if values:
        for key in DEFAULTS:
            if key in values:
                result[key]=values[key]
    try:
        result["point_size"]=max(1.0,min(5.0,float(result["point_size"])))
    except (ValueError,TypeError):
        result["point_size"]=2.0
    for key in DEFAULTS:
        if isinstance(DEFAULTS[key],bool):
            result[key]=bool(result[key])
    return result


def apply_presentation(lines,points,osm,options=None):
    """Return render-safe, filtered views without editing original source."""
    settings=normalized(options)
    keys={"FEEDER":"feeder","SUBFEEDER":"subfeeder","DISTRIBUSI":"distribution"}
    visible_lines=[
        line for line in lines if settings.get(keys.get(line[1],"distribution"),True)
    ]
    visible_points=points if settings["points"] else []
    new_osm=dict(osm or {})
    if not settings["roads"]:
        new_osm["roads"]=[]
        new_osm["_road_surfaces_v108"]=[]
    if not settings["buildings"]:
        new_osm["buildings"]=[]
    new_osm["_drawing_style"]=settings
    return visible_lines,visible_points,new_osm
