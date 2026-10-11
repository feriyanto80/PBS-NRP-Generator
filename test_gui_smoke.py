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
            self.assertFalse(hasattr(app,"import_google_button"))
        finally:
            root.destroy()


if __name__=="__main__":
    unittest.main()
