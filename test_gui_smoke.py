"""Windows Tk widgets and simulated desktop/laptop/narrow breakpoint smoke test."""
import tkinter as tk
import unittest
from responsive_ui import ResponsiveNRP


class DesktopSmokeTest(unittest.TestCase):
    def test_responsive_relayout_and_controls(self):
        root = tk.Tk()
        try:
            app = ResponsiveNRP(root)
            root.update_idletasks()
            # Hosted CI desktops may be only 1024 pixels wide.
            # Simulate available panel width but exercise REAL Tk grid widgets.
            for available, expected in ((1450,"wide"),(990,"medium"),(740,"small")):
                app.body.winfo_width = lambda width=available: width
                app._mode = None
                app._layout()
                root.update_idletasks()
                self.assertEqual(app._mode,expected)
                if expected=="wide":
                    self.assertTrue(app.sidebar.winfo_ismapped())
                    self.assertTrue(app.map_panel.winfo_ismapped())
                    self.assertTrue(app.sheet_panel.winfo_ismapped())
                elif expected=="medium":
                    app.show_panel("sheet")
                    root.update_idletasks()
                    self.assertTrue(app.sidebar.winfo_ismapped())
                    self.assertTrue(app.sheet_panel.winfo_ismapped())
                else:
                    self.assertFalse(app.header_steps.winfo_ismapped())
                    app.show_panel("settings")
                    root.update_idletasks()
                    self.assertTrue(app.sidebar.winfo_ismapped())
            self.assertEqual(app.osm_button.cget("text"),
                             "Ambil / gunakan cache OSM + Google")
            # All five sections support Collapse/Expand independently.
            self.assertEqual(len(app._section_panels),5)
            first=app._section_panels["1"]
            second=app._section_panels["2"]
            self.assertGreater(len(first["widgets"]),1)
            self.assertTrue(first["widgets"][0][0].winfo_manager())
            app._set_section_expanded("1",False)
            root.update_idletasks()
            self.assertEqual(first["widgets"][0][0].winfo_manager(),"")
            self.assertTrue(second["expanded"])
            app._set_section_expanded("1",True)
            self.assertTrue(first["widgets"][0][0].winfo_manager())
            app._set_all_sections(False)
            self.assertTrue(all(not item["expanded"] for item in app._section_panels.values()))
            app._set_all_sections(True)
            self.assertTrue(all(item["expanded"] for item in app._section_panels.values()))
            # Collapsing is only a UI operation; an active acquisition state remains.
            app._running=True
            app._toggle_section("3")
            self.assertTrue(app._running)
            app._toggle_section("3")
            app._running=False
            self.assertFalse(hasattr(app,"import_google_button"))
            app._show_progress_banner()
            root.update_idletasks()
            self.assertTrue(app.progress_banner.winfo_ismapped())
            self.assertTrue(hasattr(app,"banner_download"))
            self.assertTrue(hasattr(app,"banner_overall"))
            self.assertIn("feeder",app.layer_flags)
            self.assertIn("buildings",app.layer_flags)
            app.lines=[("Distribution","DISTRIBUSI",[(107.0,-6.0),(107.009,-6.009)])]
            app.points=[("P"+str(i),(107.0+(i%12)*.00065,-6.0-(i//12)*.00065))
                        for i in range(120)]
            app.target_points.set(30)
            app.target_routes.set(30)
            app.max_detail_sheets.set(3)
            app.sheet_overlap_pct.set(12.5)
            app._rebuild_sheet_plan()
            self.assertLessEqual(len(app._planned_sheets),4)
            self.assertGreater(len(app._planned_sheets),1)
            self.assertAlmostEqual(app._sheet_report["overlap_fraction"],.125)
            self.assertEqual(app._sheet_report["target_points_per_sheet"],30)
        finally:
            root.destroy()


if __name__=="__main__":
    unittest.main()
