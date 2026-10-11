"""Regression: supplied ABD St.Lemah Abang DXF 2018 reference profile.

The private uploaded source itself is not committed to the repository:
this tests public, neutral layer/block vocabulary extracted by local audit.
"""
import math
import os
import tempfile
import unittest
from pathlib import Path

import ezdxf
from pypdf import PdfReader
from reportlab.lib.pagesizes import A3,landscape

from reference_cad_profile import (
    REFERENCE_LAYERS,SYMBOL_NAMES,
    classify_network_point,resolve_reference_line_layer
)
from cad_sheet_layout import (name_for_sheet,webmercator,
                              MAP_LEFT,MAP_RIGHT,MAP_BOTTOM,MAP_TOP)
from reference_pdf_layout import sheet_map_transform
from engineering_render import draw_pdf,draw_dxf


class DXF2018ReferenceTest(unittest.TestCase):
    def setUp(self):
        self.bb=(106.997,-6.011,107.015,-5.994)
        self.sheets=[("Overview",self.bb),("Detail 01",
                     (106.997,-6.006,107.006,-5.994))]
        self.lines=[
            ("FEEDER_96C","FEEDER",[(107.,-6.0),(107.004,-6.004)]),
            ("DISTRIBUSI_12","DISTRIBUSI",[(107.004,-6.004),(107.007,-6.005)]),
            ("SUBFEEDER","SUBFEEDER",[(107.003,-6.002),(107.006,-6.002)])]
        self.points=[
            ("ODP 001",(107.003,-6.002)),
            ("ODC 001",(107.001,-6.001)),
            ("T6 001",(107.002,-6.002)),
            ("T7 001",(107.0025,-6.001)),
            ("T9 001",(107.0029,-6.001)),
            ("TE Existing",(107.0022,-6.001)),
            ("OTB 001",(107.004,-6.002)),
            ("HP 005",(107.005,-6.003)),
            ("UNKNOWN 008",(107.006,-6.002))]
        self.osm={
            "roads":[[(107.,-6.0),(107.011,-6.004)]],
            "road_widths":[5.5],
            "buildings":[[(107.002,-6.002),(107.0025,-6.002),
                          (107.0025,-6.0025),(107.002,-6.0025),
                          (107.002,-6.002)]],
            "_cad_reference_style":True,
            "_project_title":"PBS PROYEK TEST",
            "_drawing_style":{"point_shape":"Circle","point_size":2.0,
                              "point_labels":True}
        }

    def test_extracted_original_file_profile_is_documented(self):
        self.assertEqual(len(REFERENCE_LAYERS),49)
        self.assertIn(("Basic Map",251,None,"CONTINUOUS"),REFERENCE_LAYERS)
        self.assertIn(("FO 96 CORE",1,50,"CONTINUOUS"),REFERENCE_LAYERS)
        self.assertIn(("FO 288 CORE",250,50,"CONTINUOUS"),REFERENCE_LAYERS)
        self.assertEqual(resolve_reference_line_layer("FEEDER_96C","FEEDER"),"FO 96 CORE")
        self.assertEqual(resolve_reference_line_layer("Distribution","DISTRIBUSI"),"Precon to DC")
        self.assertEqual(classify_network_point("ODP 019"),"ODP")
        self.assertIsNone(classify_network_point("UNCLASSIFIED 100"))

    def test_cad_paperspace_layers_blocks_and_symbols(self):
        with tempfile.TemporaryDirectory() as temp:
            path=os.path.join(temp,"reference_output.dxf")
            draw_dxf(path,self.lines,self.points,self.sheets,self.osm)
            doc=ezdxf.readfile(path)
            self.assertEqual(doc.dxfversion,"AC1032")
            self.assertEqual(doc.header["$INSUNITS"],6)
            for layer,aci,weight,typ in REFERENCE_LAYERS:
                self.assertIn(layer,doc.layers)
                if layer!="0":
                    self.assertEqual(doc.layers.get(layer).dxf.color,aci)
            for name in SYMBOL_NAMES:
                self.assertIn(name,doc.blocks)
            model=doc.modelspace()
            self.assertEqual(len(model.query('LWPOLYLINE[layer=="FO 96 CORE"]')),1)
            self.assertEqual(len(model.query('LWPOLYLINE[layer=="Precon to DC"]')),1)
            self.assertEqual(len(model.query('LWPOLYLINE[layer=="Jalan"]')),1)
            self.assertEqual(len(model.query('LWPOLYLINE[layer=="buildings"]')),1)
            inserts=[item.dxf.name for item in model.query("INSERT")]
            # Source 2018 has no inserted HP symbol: Homepass is numbered TEXT.
            for marker in ("ODP","ODC","T6","T7","T9","TE","OTB"):
                self.assertIn(marker,inserts)
            self.assertNotIn("HP",inserts)
            hp_text=[e.dxf.text for e in model.query('TEXT[layer=="Homepass"]')]
            self.assertIn("005",hp_text)
            # One A3 map viewport per dynamic PDF sheet. AutoCAD also
            # includes its default viewport, which must not count here.
            for index,(name,_) in enumerate(self.sheets):
                layout=doc.layouts.get(name_for_sheet(index,name))
                vps=[v for v in layout.query("VIEWPORT") if v.dxf.id!=1]
                self.assertEqual(len(vps),1)
                labels=[e.dxf.text for e in layout.query("TEXT")]
                self.assertIn("AS BUILT DRAWING",labels)
                self.assertIn("CABLE TYPE",labels)
                self.assertTrue(any("Project Name" in val for val in labels))
                self.assertTrue(any("Page" in val for val in labels))
                self.assertFalse(any("Muhamad Bayu" in val for val in labels))

    def test_pdf_and_dxf_same_template_text_and_number_of_sheets(self):
        with tempfile.TemporaryDirectory() as temp:
            path=os.path.join(temp,"reference_output.pdf")
            draw_pdf(path,self.lines,self.points,None,*landscape(A3),
                     "PBS PROYEK TEST",self.sheets,self.osm)
            pages=PdfReader(path).pages
            self.assertEqual(len(pages),2)
            for index,page in enumerate(pages):
                content=page.extract_text()
                for phrase in ("AS BUILT DRAWING","CABLE TYPE",
                               "Nama Proyek / Project Name",
                               "Skala / Scale : N.T.S.",
                               "Halaman / Page"):
                    self.assertIn(phrase,content)
                self.assertIn(f"{index+1} OF 2",content)
                self.assertNotIn("MUHAMAD BAYU",content.upper())

    def test_paper_view_mapping_matches_cad_viewport(self):
        from cad_sheet_layout import A3_W_MM,A3_H_MM
        self.assertEqual((A3_W_MM,A3_H_MM),(420.0,297.0))
        xy,settings=sheet_map_transform(self.bb)
        p=webmercator((107.004,-6.004))
        expected_x=(MAP_LEFT+MAP_RIGHT)/2+(
            p[0]-settings["centre"][0])*settings["scale_mm_per_m"]
        expected_y=(MAP_BOTTOM+MAP_TOP)/2+(
            p[1]-settings["centre"][1])*settings["scale_mm_per_m"]
        self.assertAlmostEqual(xy((107.004,-6.004))[0],expected_x)
        self.assertAlmostEqual(xy((107.004,-6.004))[1],expected_y)


if __name__=="__main__":
    unittest.main()
