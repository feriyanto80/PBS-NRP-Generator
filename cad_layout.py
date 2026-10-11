"""A3 landscape printable CAD paperspace layouts, one for each NRP sheet.

Reference styling follows supplied Lemah Abang five-page engineering sample:
double border, right legend/title block, network layers, and sheet numbers.
Exact original DWG blocks/plot styles are not imported without a licensed
DWG reader; this creates editable CAD equivalents.
"""
from app import viewport
from drafter_titleblock import LEFT_LEGEND,RIGHT_LEGEND,CABLE_LINES,FEEDER_LINES
from road_topology import iter_road_boundaries

PAPER_W,PAPER_H=420.0,297.0
SIDE_X,SIDE_RIGHT=352.0,414.0


def add_sheet_layouts(doc,lines,points,sheets,osm=None,project_title=""):
    names=[]
    style=(osm or {}).get("_drawing_style",{})
    for index,(sheet_name,box) in enumerate(sheets,1):
        name=f"NRP_{index:02d}"
        paper=doc.layouts.new(name)
        paper.page_setup(size=(PAPER_W,PAPER_H),margins=(0,0,0,0),units="mm")
        names.append(name)
        def segment(a,b,layer="SHEET_BORDER"):
            paper.add_line(a,b,dxfattribs={"layer":layer})
        def frame(x,y,w,h,layer="SHEET_BORDER"):
            paper.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],
                close=True,dxfattribs={"layer":layer})
        def label(value,x,y,height=1.7,layer="TITLE_BLOCK"):
            if value:
                paper.add_text(str(value).replace("\n"," ")[:130],
                               dxfattribs={"height":height,"insert":(x,y),"layer":layer})
        frame(4,4,412,289)
        frame(6,6,408,285)
        frame(8,8,343,281)
        frame(SIDE_X,8,SIDE_RIGHT-SIDE_X,281)
        label("AS BUILT DRAWING",SIDE_X+5,282,3.2)
        segment((SIDE_X,277),(SIDE_RIGHT,277))
        mid=383
        segment((mid,210),(mid,277))
        for row in range(11):
            y=271-row*5.7
            label(LEFT_LEGEND[row][0],SIDE_X+1,y,1.27,"CAD_LEGEND")
            label(RIGHT_LEGEND[row][0],mid+1,y,1.17,"CAD_LEGEND")
            segment((SIDE_X,y-2),(SIDE_RIGHT,y-2),"CAD_LEGEND")
        label("CABLE TYPE",SIDE_X+19,205,2.55)
        for row in range(7):
            y=198-row*4.6
            label(CABLE_LINES[row][0],SIDE_X+1,y,1.42,"CAD_LEGEND")
            label(FEEDER_LINES[row][0],mid+1,y,1.42,"CAD_LEGEND")
            segment((SIDE_X,y-1.4),(SIDE_RIGHT,y-1.4),"CAD_LEGEND")
        for y in (162,141,128,105,87,49):
            segment((SIDE_X,y),(SIDE_RIGHT,y))
        label("STARLITE / PBS",SIDE_X+12,150,3)
        label("DATE     REVISION      SIGN",SIDE_X+2,137,1.8)
        label("PROJECT NAME",SIDE_X+2,123,1.6)
        label(project_title or "PROJECT",SIDE_X+2,117,1.7)
        label(sheet_name,SIDE_X+2,111,1.8)
        label("NETWORK ROUTE PLAN",SIDE_X+2,100,2.1)
        label("DRAWING SIGN & CHECK",SIDE_X+2,82,2.1)
        label("DRAWN BY:________________",SIDE_X+2,72,1.5)
        label("CHECKED :________________",SIDE_X+2,66,1.5)
        label("APPROVED:________________",SIDE_X+2,60,1.5)
        label("N",SIDE_X+14,36,3.5)
        segment((SIDE_X+15,14),(SIDE_X+15,34))
        segment((SIDE_X+10,24),(SIDE_X+20,24))
        label("SCALE N.T.S.",mid+1,35,1.8)
        label(f"SHEET {index} OF {len(sheets)}",mid+1,24,2.2)
        label("A3 LANDSCAPE",mid+1,16,1.6)

        tr=viewport(box,343,281,5)
        def map_xy(position):
            x,y=tr(position)
            return (8+x,8+y)

        if osm:
            for ring in osm.get("buildings",[]):
                if len(ring)>=3:
                    paper.add_lwpolyline([map_xy(pt) for pt in ring],close=True,
                          dxfattribs={"layer":"OSM_BUILDING_FOOTPRINT"})
            for ring in iter_road_boundaries(osm):
                if len(ring)>=3:
                    paper.add_lwpolyline([map_xy(pt) for pt in ring],close=True,
                          dxfattribs={"layer":"OSM_ROAD_EDGES"})
        for _,kind,vertices in lines:
            if len(vertices)>1:
                layer=kind if kind in ("FEEDER","SUBFEEDER","DISTRIBUSI") else "DISTRIBUSI"
                paper.add_lwpolyline([map_xy(pt) for pt in vertices],
                                     dxfattribs={"layer":layer})
        symbol=style.get("point_shape","Circle")
        radius=max(.2,min(1.5,float(style.get("point_size",2))*.18))
        for value,coord in points:
            x,y=map_xy(coord)
            if not 8<=x<=351 or not 8<=y<=289:
                continue
            if symbol=="Square":
                frame(x-radius,y-radius,2*radius,2*radius,"POINTS")
            elif symbol=="Triangle":
                paper.add_lwpolyline([(x,y+radius),(x-radius,y-radius),(x+radius,y-radius)],
                    close=True,dxfattribs={"layer":"POINTS"})
            else:
                paper.add_circle((x,y),radius,dxfattribs={"layer":"POINTS"})
            if style.get("point_labels",True) and index>1 and value:
                label(value,x+radius+.4,y+radius+.5,1.15,"LABELS")
    return names
