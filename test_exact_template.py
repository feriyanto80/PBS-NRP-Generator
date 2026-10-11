"""Reference fidelity v1.0.18: source CAD/PDF import and symbol authority tests.

Private Lemah Abang DXF/PDF are not stored in this repository. CI builds
synthetic A3 assets to verify exact-mode behavior without vendor/project data.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ezdxf
import fitz

from exact_template import (
    find_reference,has_exact_template,replace_cad_upper_titleblock,
    overlay_pdf_upper_titleblock
)
from template_symbols import (
    canonical, LEGEND_IDS_LEFT, LEGEND_IDS_RIGHT, draw_symbol
)
from reference_cad_profile import install_symbols
from cad_sheet_layout import attach_a3_layouts


class CanonicalSymbolTests(unittest.TestCase):
    def test_reference_legend_complete(self):
        self.assertEqual(len(LEGEND_IDS_LEFT),11)
        self.assertEqual(len(LEGEND_IDS_RIGHT),11)
        self.assertEqual(LEGEND_IDS_LEFT[:5],("T6","T7","T9","TL","TE"))
        self.assertEqual(LEGEND_IDS_LEFT[5],"ODC")
        self.assertEqual(LEGEND_IDS_LEFT[7:10],("ODP","ODP16","ODP24"))

    def test_distinct_device_types_and_unclassified_homepass(self):
        for label,expected in [
            ("T6-0001","T6"),("T7_01","T7"),("T9 21","T9"),
            ("ODC NEW","ODC"),("ODP 8 HP","ODP"),
            ("NEW ODP 16 HP","ODP16"),("NEW ODP 24 HP","ODP24"),
            ("EXISTING ODP","ODP_EXIST"),("Existing Closure","CLOSURE_EXIST"),
            ("NEW CLOSURE","CLOSURE"),("OTB 1","OTB"),("HP 001","HP"),
            ("001",None),
        ]:
            self.assertEqual(canonical(label),expected,label)

    def test_map_blocks_and_legend_are_same_glyph_family(self):
        doc=ezdxf.new("R2018")
        install_symbols(doc)
        for kind in ("T6","T7","T9","TE","ODC","ODP","ODP16",
                     "ODP24","CLOSURE","OTB","HP"):
            self.assertIn(kind,doc.blocks)
            block=doc.blocks.get(kind)
            self.assertTrue(len(list(block))>=1)
        t6=list(doc.blocks.get("T6"))
        t7=list(doc.blocks.get("T7"))
        self.assertNotEqual(
            [v.dxf.get("true_color") for v in t6 if v.dxftype()=="SOLID"],
            [v.dxf.get("true_color") for v in t7 if v.dxftype()=="SOLID"])


class TemplateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.dxf=self.path/"ABD St.Lemah Abang Phase 1 Simpangan.dxf"
        self.pdf=self.path/"ABD St.Lemah Abang Phase 1 Simpangan.pdf"

    def _make_dxf(self):
        source=ezdxf.new("R2018")
        layout=source.layouts.new("Layout1-ALL")
        for i in range(90):
            y=1245-i*5.3
            layout.add_line((1414,y),(1655,y),dxfattribs={"layer":"0"})
        layout.add_text("ORIGINAL REFERENCE LEGEND",dxfattribs={
            "insert":(1435,1202),"height":6.0})
        # Should never be imported: source project name is below static region.
        layout.add_text("PERSON PRIVATE SOURCE",dxfattribs={
            "insert":(1440,520),"height":5.0})
        source.saveas(self.dxf)

    def _make_pdf(self):
        source=fitz.open()
        page=source.new_page(width=842,height=1191)
        # Original AutoCAD print rotates portrait MediaBox to A3 landscape.
        page.insert_text((752,1030),"REFERENCE LEGEND GLYPHS",fontsize=13)
        page.set_rotation(270)
        source.save(self.pdf)
        source.close()

    def test_auto_discovery_in_sibling_template_directory(self):
        folder=self.path/"template"
        folder.mkdir()
        self.dxf.rename(folder/self.dxf.name)
        self.pdf.write_bytes(b"%PDF-1.4 test")
        self.pdf.rename(folder/self.pdf.name)
        with patch.dict(os.environ,{"PBS_NRP_TEMPLATE_DIR":str(self.path)}):
            self.assertTrue(has_exact_template())
            self.assertTrue(find_reference("dxf").endswith(".dxf"))

    def test_original_paperspace_static_only(self):
        self._make_dxf()
        target=ezdxf.new("R2018")
        extent=(106.99,-6.1,107.03,-6.07)
        layouts=attach_a3_layouts(target,[("Overview",extent)],
                                  "PBS NEW PROJECT",{"_cad_reference_style":False})
        sheet=target.layouts.get(layouts[0])
        before=len(list(sheet))
        added=replace_cad_upper_titleblock(target,sheet,str(self.dxf))
        self.assertGreater(added,80)
        self.assertGreater(len(list(sheet)),before)
        texts=[ent.dxf.text for ent in sheet.query("TEXT")]
        self.assertIn("ORIGINAL REFERENCE LEGEND",texts)
        self.assertNotIn("PERSON PRIVATE SOURCE",texts)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"tested.dxf"
            target.saveas(path)
            audit=ezdxf.readfile(path).audit()
            self.assertFalse(audit.has_errors)

    def test_rotated_reference_pdf_replaces_upper_legend(self):
        self._make_pdf()
        dest=self.path/"output.pdf"
        document=fitz.open()
        page=document.new_page(width=1191,height=842)
        page.insert_text((1000,55),"OLD APPROXIMATE LEGEND",fontsize=12)
        document.save(dest)
        document.close()
        count=overlay_pdf_upper_titleblock(dest,self.pdf)
        self.assertEqual(count,1)
        result=fitz.open(dest)
        text=result[0].get_text()
        self.assertIn("REFERENCE LEGEND GLYPHS",text)
        result.close()


if __name__=="__main__":
    unittest.main()
