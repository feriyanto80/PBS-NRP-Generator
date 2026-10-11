"""Regression tests for v1.0.19 printed-glyph and KML type parity."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from reportlab.pdfgen import canvas
from template_symbols import canonical
from reference_pdf_glyphs import draw_reference_pdf_glyph, _load_reference_icon
from kml_support import parse_kml_bytes


class ExactPdfGlyphTests(unittest.TestCase):
    def test_reference_glyphs_appear_in_map_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ref=root/"ABD St.Lemah Abang Phase 1 Simpangan.pdf"
            source=fitz.open()
            page=source.new_page(width=1191,height=842)
            # Synthetic static legend with precisely located test glyphs.
            page.draw_circle((1003.7,67.25),3,fill=(1,.72,0),color=(.95,.4,.0))
            # Row 8 (index 7) in the source left column is ODP8.
            pt=(1003.7,67.25+7*21.555)
            page.draw_polyline([(pt[0],pt[1]-4),(pt[0]-4,pt[1]+4),
                                (pt[0]+4,pt[1]+4),(pt[0],pt[1]-4)],
                               color=(0,0,1),width=1.5)
            source.save(ref)
            source.close()
            result=root/"generated.pdf"
            pdf=canvas.Canvas(str(result),pagesize=(1191,842))
            with patch("exact_template.find_reference",return_value=str(ref)):
                self.assertTrue(draw_reference_pdf_glyph(pdf,"T6",50,100))
                self.assertTrue(draw_reference_pdf_glyph(pdf,"ODP",70,100))
                self.assertFalse(draw_reference_pdf_glyph(pdf,"HP",90,100))
            pdf.save()
            doc=fitz.open(result)
            self.assertGreaterEqual(len(doc[0].get_images()),2)
            doc.close()
            _load_reference_icon.cache_clear()


class KmlAuthorityTests(unittest.TestCase):
    def test_folder_device_overrides_generic_homepass_label(self):
        xml=b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
          <Folder><name>ODP 8 HP</name><Placemark><name>HP 001</name>
          <Point><coordinates>107.001,-6.201,0</coordinates></Point>
          </Placemark></Folder>
          <Folder><name>New Pole 7</name><Placemark><name>005</name>
          <Point><coordinates>107.002,-6.202,0</coordinates></Point>
          </Placemark></Folder></Document></kml>"""
        _,points=parse_kml_bytes(xml)
        self.assertEqual([canonical(name) for name,_ in points],
                         ["ODP","T7"])
    def test_descriptive_poles(self):
        self.assertEqual(canonical("NEW POLE 6 - 001"),"T6")
        self.assertEqual(canonical("TIANG 9"),"T9")
        self.assertEqual(canonical("EXISTING POLE 7"),"TE")


if __name__=="__main__":
    unittest.main()
