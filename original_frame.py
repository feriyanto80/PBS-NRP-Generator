"""Exact-measurement title block geometry based on user's 2018 Lemah Abang DXF.

Source entity measurements: right frame spans x=1413.9..1655.6,
y=45.8..1256.1 (units from Layout1-ALL). Converted uniformly into
A3 420x297 mm; unlike the earlier hand-drawn generic template, rows and
column separators now follow the actual CAD coordinates.

Technical legend preserved; personal approval names, historical project
identity and embedded OLE are NOT copied to new projects. STaRLITE contour
is traced from the supplied PDF screenshot, and is editable vector geometry
in both DXF/DWG and PDF (not a broken OLE link).
"""
from cad_sheet_layout import LEGEND_LEFT, LEGEND_RIGHT, CABLE_LEFT, CABLE_RIGHT
from template_symbols import draw_symbol, LEGEND_IDS_LEFT, LEGEND_IDS_RIGHT

REFERENCE_LEFT=1413.9
REFERENCE_BOTTOM=45.8
REFERENCE_SCALE=0.236
RIGHT=1655.6
TOP=1256.1


def pt(x,y):
    return (351.0+(x-REFERENCE_LEFT)*REFERENCE_SCALE,
            5.5+(y-REFERENCE_BOTTOM)*REFERENCE_SCALE)


def original_titleblock(draw,project,sheetname,index,total,stats=None):
    """Emit same editable drawing entities to ezdxf PaperSpace or ReportLab."""
    def line(a,b,c,d,layer="NRP_TB_FRAME",color=7):
        draw.add_line(pt(a,b),pt(c,d),dxfattribs={"layer":layer,"color":color})
    def poly(coords,layer="NRP_TB_SYMBOL",color=5,close=False):
        draw.add_lwpolyline([pt(a,b) for a,b in coords],close=close,
                            dxfattribs={"layer":layer,"color":color})
    def circle(x,y,r,color=7):
        draw.add_circle(pt(x,y),r*REFERENCE_SCALE,
                        dxfattribs={"layer":"NRP_TB_SYMBOL","color":color})
    def text(value,x,y,h=6,color=7,layer="NRP_TB_TEXT"):
        style=("NRP_REFERENCE_TAHOMA" if h>=8 else "NRP_REFERENCE_ROMANS")
        draw.add_text(str(value or "")[:85],dxfattribs={
            "layer":layer,"color":color,"height":h*REFERENCE_SCALE,
            "insert":pt(x,y),"style":style})

    # Paper-frame and titleblock coordinates are from source DXF measurements.
    line(1413.9,45.8,1413.9,1256.1)
    line(1655.6,45.8,1655.6,1256.1)
    line(1413.9,1256.1,1655.6,1256.1)
    line(1413.9,45.8,1655.6,45.8)
    line(1413.9,1242.7,1655.6,1242.7)
    line(1413.9,1203.4,1655.6,1203.4)
    line(1413.9,1201.1,1655.6,1201.1)
    text("AS BUILT DRAWING",1419.7,1210.47,15.03)

    # Original legend 11 rows on two columns, with row pitch about 32.45 CAD units.
    row_ys=[1168.6,1133.7,1101.3,1068.8,1036.4,1003.9,
            971.5,939.0,907.6,876.1,844.7]
    line(1535.5,844.7,1535.5,1203.4)
    for row_index,yy in enumerate(row_ys):
        line(1413.9,yy,1655.6,yy)
        left=LEGEND_LEFT[row_index]
        right=LEGEND_RIGHT[row_index]
        # The titleblock and map draw from the SAME symbol authority.
        for start,entry,identifier in (
            (1413.9,left,LEGEND_IDS_LEFT[row_index]),
            (1535.5,right,LEGEND_IDS_RIGHT[row_index]),
        ):
            label,colour,_kind,_short=entry
            middle=yy+16.1
            sx=start+9.8
            gx,gy=pt(sx,middle)
            draw_symbol(draw,identifier,gx,gy,size=5.8*REFERENCE_SCALE)
            text(label,start+21,yy+13,5.2 if len(label)>21 else 6.0)

    line(1413.9,842.6,1655.6,842.6)
    line(1413.9,824.3,1655.6,824.3)
    text("CABLE TYPE",1489.25,828.37,9.71)
    cable_levels=[822.0,806.9,791.8,776.7,760.6,745.9,730.5,714.9]
    line(1535.5,714.9,1535.5,822.0)
    for yy in cable_levels:
        line(1413.9,yy,1655.6,yy)
    for i in range(7):
        yy=(cable_levels[i]+cable_levels[i+1])/2
        for left,entry in ((1413.9,CABLE_LEFT[i]),(1535.5,CABLE_RIGHT[i])):
            label,color=entry
            text(label,left+3,yy-2,5.1)
            line(left+83,yy,left+115,yy,"NRP_TB_CABLE",color)

    # Starlite logo: reconstructed from original 2018 source PDF outline.
    # The OLD module's seven-point logo was geometrically different.
    # Points below follow the S-shaped central wing, not a generic star.
    # Two-tone original OLE emblem is supplied as vector contours,
    # avoiding the broken external OLE link / distorted invented star.
    from starlite_logo import starlite_logo
    centre_x, base_y=pt(1535.5,632.0)
    starlite_logo(draw,centre_x,base_y,height=18.5)
    text("S T A R L I T E",1495.5,625.9,8.0,7)
    line(1413.9,621.5,1655.6,621.5)

    # Revision grid in precisely measured original location.
    for yy in (620.2,602.7,585.3,567.8,550.3,545.1):
        line(1413.9,yy,1655.6,yy)
    line(1470.1,550.3,1470.1,621.5)
    line(1606.9,550.3,1606.9,621.5)
    text("DATE",1433.45,607.38,7.77)
    text("REVISION",1518.95,607.66,7.77)
    text("SIGN",1623.9,607.79,7.77)

    # Project title. Historical names and approvals deliberately excluded.
    for yy in (539.4,537.4,488.3,467.1,465.6,445.1,443.6,
               427.4,426.0,353.1,351.6,332.5,331.0,249.1,247.6,175.6):
        line(1413.9,yy,1655.6,yy)
    line(1535.6,353.1,1535.6,426.0)
    line(1532.4,56.9,1532.4,247.6)
    line(1532.4,249.1,1532.4,331.0)
    line(1532.4,93.5,1655.6,93.5)
    text("Project Name",1419.89,522.88,5.6)
    short=str(project or "PBS NETWORK ROUTE PLAN").replace("_"," ")
    text(short[:43],1430,500.8,6.8)
    if len(short)>43:
        text(short[43:80],1430,491,5.5)
    text("Drawing Type",1418.94,475.73,5.6)
    text("AS BUILT DRAWING",1497.17,473.54,8.0)
    text("DRAWING SIGN & CHECK",1452.49,451.13,9.71)
    text("Created by: __________  Checked by: __________",1420,432.8,5.2)
    text("PROJECT CONTROL / APPROVAL",1450,338.7,7.0)
    for xx,yy,label in [
        (1421,406,"Created by"),(1541,406,"Checked by"),
        (1421,320,"Approved by"),(1541,320,"Verified by"),
    ]:
        text(label,xx,yy,5.2)
        text("_________________",xx,yy-46,5.2)
    text("Drawing No.",1536.32,159.75,4.19)
    text(f"NRP-{index+1:02d}",1540,142.0,6.2)
    text("Scale",1535.74,106.04,4.19)
    text("N.T.S.",1540,96.2,5.0)
    text("Page",1536.04,71.54,4.19)
    text(f"{index+1} / {total}",1540,60.2,6.0)
    text("N",1467,151.5,7)
    line(1469,96,1469,148,"NRP_TB_COMPASS",7)
    line(1451,118,1487,118,"NRP_TB_COMPASS",7)
    text("S",1467,89,6)
    # Keep bilingual metadata expected by user and previous releases.
    text("Nama Proyek / Project Name",1419.89,530.5,3.8)
    text("Skala / Scale : N.T.S.",1536.0,118,4.5)
    text(f"Halaman / Page : {index+1} OF {total}",1536,82,4.5)
    text("Ref. Peta / Map Ref.",1420,172,4.5)
