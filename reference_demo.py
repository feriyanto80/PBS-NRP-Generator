"""Offline reference parity sample. Synthetic geometry; NOT actual Lemah Abang survey.

Generated PDF and DXF are uploaded as Windows build verification artifacts.
This allows visual inspection without exposing the user's original CAD drawing.
"""
from pathlib import Path
import ezdxf
from pypdf import PdfReader
from reportlab.lib.pagesizes import A3, landscape
from engineering_render import draw_pdf, draw_dxf
from cad_sheet_layout import name_for_sheet


def run():
    out=Path("reference_demo_output")
    out.mkdir(exist_ok=True)
    bbox=(107.000,-6.210,107.010,-6.200)
    roads=[
        [(107.001,-6.205),(107.009,-6.205)],
        [(107.005,-6.209),(107.005,-6.201)],
        [(107.002,-6.205),(107.002,-6.202)],
        [(107.007,-6.205),(107.007,-6.208)],
    ]
    buildings=[]
    for row in range(6):
        for col in range(8):
            x=107.0008+col*.00105
            y=-6.2006-row*.00130
            # Avoid the central road right of way.
            if 107.0044 < x < 107.0055:
                continue
            buildings.append([
              (x,y),(x+.00035,y),(x+.00035,y-.00028),
              (x,y-.00028),(x,y)])
    lines=[
        ("FEEDER 96C - SAMPLE","FEEDER",[(107.0005,-6.205),(107.009,-6.205)]),
        ("SUBFEEDER 24 CORE","SUBFEEDER",[(107.005,-6.205),(107.005,-6.201)]),
        ("DISTRIBUSI_12","DISTRIBUSI",[(107.002,-6.205),(107.002,-6.203)]),
    ]
    points=[
        ("ODC 001",(107.0008,-6.205)),
        ("ODP 001",(107.002,-6.203)),
        ("T6 001",(107.003,-6.205)),
        ("T7 002",(107.006,-6.205)),
        ("T9 003",(107.008,-6.205)),
        ("TE EXISTING",(107.005,-6.208)),
        ("HP 001",(107.002,-6.202)),
        ("OTB 001",(107.005,-6.201)),
        ("CLOSURE",(107.007,-6.205)),
    ]
    sheets=[
        ("Overview",bbox),
        ("Detail Blok A",(107.000,-6.206,107.006,-6.200)),
    ]
    osm={"roads":roads,"road_widths":[5,6,4,5],
         "buildings":buildings,"_cad_reference_style":True,
         "_project_title":"PBS NRP - DEMO TEMPLATE",
         "_drawing_style":{"point_shape":"Circle","point_size":2,
                           "point_labels":True}}
    pdf=out/"PBS_NRP_v1.0.16_Reference_Demo.pdf"
    dxf=out/"PBS_NRP_v1.0.16_Reference_Demo.dxf"
    draw_pdf(str(pdf),lines,points,None,*landscape(A3),
             "PBS NRP - DEMO TEMPLATE",sheets,osm)
    draw_dxf(str(dxf),lines,points,sheets,osm)
    assert len(PdfReader(str(pdf)).pages)==len(sheets)
    doc=ezdxf.readfile(str(dxf))
    assert doc.dxfversion=="AC1032"
    assert all(name_for_sheet(i,s[0]) in doc.layouts
               for i,s in enumerate(sheets))
    assert len(doc.modelspace().query("INSERT"))>=7
    print("Offline PDF/DXF reference visual sample ready:",pdf,dxf)


if __name__=="__main__":
    run()
