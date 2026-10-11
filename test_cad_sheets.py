"""v1.0.15 CAD/PDF parity tests for uploaded Lemah Abang reference conventions.

Checks editable AutoCAD-compatible paper-space layouts and viewports,
not unsupported byte-identical access to the original binary DWG.
"""
import os
import tempfile
import unittest
from pathlib import Path

import ezdxf
from reportlab.lib.pagesizes import A3,landscape

from cad_sheet_layout import (attach_a3_layouts,name_for_sheet,
    A3_W_MM,A3_H_MM,SIDEBAR_X,LEGEND_LEFT,LEGEND_RIGHT)
from engineering_render import draw_dxf,draw_pdf
from drafter_titleblock import draw_titleblock


class CadLayoutTests(unittest.TestCase):
    def setUp(self):
        self.lines=[
            ("FEEDER_96C","FEEDER",[(107.0,-6.0),(107.004,-6.003)]),
            ("DISTRIBUSI","DISTRIBUSI",[(107.004,-6.003),(107.005,-6.004)])]
        self.points=[("T6_001",(107.002,-6.001))]
        self.bbox=(106.999,-6.005,107.006,-5.999)
        self.sheets=[("Overview",self.bbox),
                     ("Detail 01",self.bbox),
                     ("Detail 02",self.bbox)]
        self.osm={"roads":[[(107,-6.0),(107.006,-6.004)]],
                  "buildings":[[(107.001,-6.001),(107.0014,-6.001),
                                (107.0014,-6.0013),(107.001,-6.0013)]],
                  "_project_title":"FTTH STASIUN LEMAH ABANG PHASE 1 SIMPANGAN"}

    def test_dwg_reference_headers_and_cable_legend(self):
        self.assertEqual(len(LEGEND_LEFT),11)
        self.assertEqual(len(LEGEND_RIGHT),11)
        self.assertIn("NEW ODP 24 HP",[x[0] for x in LEGEND_LEFT])
        self.assertIn("NEW CLOSURE",[x[0] for x in LEGEND_RIGHT])
        self.assertGreater(SIDEBAR_X,330)
        self.assertEqual((A3_W_MM,A3_H_MM),(420,297))

    def test_dxf_multisheet_has_matching_paperspace_layouts(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"nrp_reference.dxf"
            draw_dxf(str(path),self.lines,self.points,self.sheets,self.osm)
            doc=ezdxf.readfile(path)
            names=[name_for_sheet(i,name) for i,(name,_) in enumerate(self.sheets)]
            for name in names:
                self.assertIn(name,doc.layouts)
                sheet=doc.layouts.get(name)
                self.assertEqual(len(sheet.query("VIEWPORT")),1)
                vp=sheet.query("VIEWPORT")[0]
                self.assertGreater(vp.dxf.height,200)
                self.assertGreater(vp.dxf.width,300)
                frame=sheet.query('LWPOLYLINE[layer=="NRP_TB_FRAME"]')
                self.assertGreater(len(frame),2)
                labels=[entity.dxf.text for entity in sheet.query("TEXT")]
                self.assertIn("AS BUILT DRAWING",labels)
                self.assertIn("CABLE TYPE",labels)
                self.assertIn("S T A R L I T E",labels)
                self.assertTrue(any("SHEET" in t and "OF 3" in t for t in labels))
                self.assertTrue(any("LEMAH ABANG" in t for t in labels))
                self.assertFalse(any("Muhamad" in t for t in labels))
            self.assertEqual(len(doc.modelspace().query("LWPOLYLINE")),4)

    def test_pdf_same_dynamic_number_of_pages(self):
        import fitz
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"nrp_reference.pdf"
            draw_pdf(str(path),self.lines,self.points,None,
                     *landscape(A3),"FTTH STASIUN LEMAH ABANG PHASE 1 SIMPANGAN",
                     self.sheets,self.osm)
            pdf=fitz.open(path)
            self.assertEqual(len(pdf),len(self.sheets))
            for i,page in enumerate(pdf):
                self.assertAlmostEqual(page.rect.width,1190.55,delta=2)
                self.assertAlmostEqual(page.rect.height,841.89,delta=2)
                self.assertIn("AS BUILT DRAWING",page.get_text())
                self.assertIn("CABLE TYPE",page.get_text())
            pdf.close()


if __name__=="__main__":
    unittest.main()
