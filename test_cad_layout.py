"""A3 CAD/paperspace equivalence and collapsible UI regression."""
import os
import tempfile
import unittest
import tkinter as tk

import ezdxf
from engineering_render import draw_dxf


class PaperSpaceTests(unittest.TestCase):
    def test_dynamic_cad_layouts_match_sheet_count(self):
        coords=[(107.0,-6.0),(107.003,-6.001)]
        lines=[("FEEDER 96C","FEEDER",coords)]
        points=[("ODP 001",coords[0])]
        region=(106.999,-6.005,107.008,-5.998)
        sheets=[("Overview",region),("Detail Barat",region),
                ("Detail Timur",region)]
        osm={"roads":[coords],
             "buildings":[[(107.,-6.),(107.001,-6.),
                           (107.001,-6.001),(107.,-6.)]]}
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"test.dxf")
            draw_dxf(path,lines,points,sheets,osm)
            doc=ezdxf.readfile(path)
            for idx in range(1,4):
                layout=doc.layouts.get(f"NRP_{idx:02d}")
                self.assertIsNotNone(layout)
                self.assertGreater(len(list(layout)),15)
                contents=[entity.dxf.text for entity in layout.query("TEXT")]
                self.assertIn(f"SHEET {idx} OF 3",contents)
                self.assertIn("AS BUILT DRAWING",contents)
                self.assertGreater(len(layout.query('LWPOLYLINE[layer=="FEEDER"]')),0)
                self.assertGreater(len(layout.query('LWPOLYLINE[layer=="OSM_BUILDING_FOOTPRINT"]')),0)
            self.assertGreater(len(doc.modelspace().query('LWPOLYLINE[layer=="FEEDER"]')),0)


class AccordionTests(unittest.TestCase):
    def test_accordion_independent_and_expand_all(self):
        from responsive_ui import ResponsiveNRP
        root=tk.Tk()
        try:
            app=ResponsiveNRP(root)
            root.update_idletasks()
            self.assertEqual(set(app._section_panels),{"1","2","3","4","5"})
            self.assertTrue(all(x["expanded"] for x in app._section_panels.values()))
            app._set_section_expanded("3",False)
            self.assertFalse(app._section_panels["3"]["expanded"])
            self.assertTrue(app._section_panels["2"]["expanded"])
            app._set_all_sections(False)
            self.assertTrue(all(not x["expanded"] for x in app._section_panels.values()))
            app._set_all_sections(True)
            self.assertTrue(all(x["expanded"] for x in app._section_panels.values()))
            app._jump_to_section("4")
            root.update_idletasks()
            self.assertTrue(app._section_panels["4"]["expanded"])
        finally:
            root.destroy()


if __name__=="__main__":
    unittest.main()
