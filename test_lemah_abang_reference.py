"""Lemah Abang 2018 DXF-derived engineering output contract.

Reference facts: AC1032, 49 layer names, 30 block definitions, Layout1-ALL.
Does not require redistributing customer's original DWG/DXF in EXE.
"""
import tempfile
import unittest
from pathlib import Path

import ezdxf
from pypdf import PdfReader
from reportlab.lib.pagesizes import A3, landscape

from engineering_render import draw_dxf, draw_pdf
from reference_cad_profile import REFERENCE_LAYERS


class ExactSourceProfileTests(unittest.TestCase):
    def setUp(self):
        self.bb=(107.0,-6.0,107.005,-5.994)
        self.lines=[("FEEDER_96_CORE","FEEDER",[(107.001,-5.998),(107.003,-5.996)])]
        self.points=[("T6 001",(107.002,-5.997)),("ODP 2",(107.003,-5.996))]
        self.osm={"roads":[[(107.0,-6.0),(107.005,-5.995)]],
                  "buildings":[[(107.001,-5.999),(107.002,-5.999),
                                (107.002,-5.998),(107.001,-5.999)]],
                  "_cad_reference_style":True,
                  "_project_title":"TEST PROJECT — NOT LEMAH ABANG"}
        self.sheets=[("Overview",self.bb),("Detail 01",self.bb)]

    def test_exact_49_layer_profile(self):
        self.assertEqual(len(REFERENCE_LAYERS),49)
        names={row[0] for row in REFERENCE_LAYERS}
        for expected in ("Jalan","buildings","FO 96 CORE","FO 288 CORE",
                         "ODP","ODC","Homepass","NEW POLE T6"):
            self.assertIn(expected,names)

    def test_project_specific_cad_exports_and_pdf_sheet_parity(self):
        with tempfile.TemporaryDirectory() as directory:
            dxf=Path(directory)/"test_reference.dxf"
            pdf=Path(directory)/"test_reference.pdf"
            draw_dxf(str(dxf),self.lines,self.points,self.sheets,self.osm)
            doc=ezdxf.readfile(dxf)
            self.assertEqual(doc.dxfversion,"AC1032")
            layers={layer.dxf.name for layer in doc.layers}
            self.assertTrue({"FO 96 CORE","Jalan","buildings","NEW POLE T6"}.issubset(layers))
            self.assertGreater(len(doc.modelspace().query('LWPOLYLINE[layer=="FO 96 CORE"]')),0)
            self.assertGreater(len(doc.modelspace().query('INSERT[name=="T6"]')),0)
            names=[name for name in doc.layout_names() if name.lower() not in ("model","layout1")]
            self.assertEqual(len(names),len(self.sheets))
            for name in names:
                layout=doc.layouts.get(name)
                texts=[entry.dxf.text for entry in layout.query("TEXT")]
                self.assertIn("AS BUILT DRAWING",texts)
                self.assertIn("CABLE TYPE",texts)
                self.assertTrue(any("TEST PROJECT" in label for label in texts))
                self.assertFalse(any("FTTH STASIUN LEMAH ABANG" in label for label in texts))
            draw_pdf(str(pdf),self.lines,self.points,None,
                     *landscape(A3),"TEST PROJECT",self.sheets,self.osm)
            pages=PdfReader(str(pdf)).pages
            self.assertEqual(len(pages),2)
            for page in pages:
                text=page.extract_text()
                for phrase in ("AS BUILT DRAWING","CABLE TYPE","Project Name",
                               "Drawing Type","Drawing No."):
                    self.assertIn(phrase,text)
