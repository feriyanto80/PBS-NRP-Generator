"""Faithful STARLITE emblem silhouette traced from user-supplied reference PDF.

The two colored contours follow the original light-blue and navy emblem,
rather than the older invented star polygon. Coordinates are sampled from the
user's original PDF; no external image files are required by the standalone EXE.
"""
LIGHT=[(38,19),(30,44),(27,47),(10,54),(25,59),(17,85),(35,67),(44,54),(44,51),(33,52),(31,50),(34,43),(40,37),(42,38),(50,32),(43,37),(41,36),(43,34),(43,30)]
NAVY=[(76,19),(48,33),(36,45),(36,48),(46,48),(48,50),(48,54),(41,64),(66,86),(51,52)]
LOGO_WIDTH=86
LOGO_HEIGHT=95

def starlite_logo(draw,center_x,bottom_y,height=19):
    """Filled vector outlines shared by both CAD PaperSpace and PDF adapter.

    Assumes draw.add_solid(4 vertices); concave shape is triangulated with
    shapely and each triangle lies inside the real silhouette.
    """
    from shapely.geometry import Polygon
    from shapely.ops import triangulate
    scale=float(height)/LOGO_HEIGHT
    left=center_x-LOGO_WIDTH*scale/2
    for coords,color in ((LIGHT,0x219BE6),(NAVY,0x0D3F77)):
        vertices=[(left+x*scale,bottom_y+(LOGO_HEIGHT-y)*scale) for x,y in coords]
        polygon=Polygon(vertices).buffer(0)
        if polygon.is_empty:
            continue
        shapes=[polygon] if polygon.geom_type=="Polygon" else list(polygon.geoms)
        for shape in shapes:
            for triangle in triangulate(shape):
                sample=triangle.representative_point()
                if not shape.covers(sample):
                    continue
                pts=list(triangle.exterior.coords)[:3]
                # SOLID entities are portable DXF R2018 geometry.
                draw.add_solid(pts+[pts[-1]],dxfattribs={
                    "layer":"NRP_TB_LOGO", "true_color":color})
