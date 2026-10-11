"""Windows GUI smoke tests: verify widgets, responsive states, and zoom controls."""
import tkinter as tk
import unittest
from responsive_ui import ResponsiveNRP

class DesktopSmokeTest(unittest.TestCase):
    def test_responsive_relayout_and_controls(self):
        root=tk.Tk()
        try:
            root.geometry("1470x810")
            app=ResponsiveNRP(root)
            root.update_idletasks()
            app._layout()
            self.assertEqual(app._mode,"wide")
            self.assertTrue(app.sidebar.winfo_ismapped())
            self.assertTrue(app.map_panel.winfo_ismapped())
            self.assertTrue(app.sheet_panel.winfo_ismapped())
            root.geometry("990x680")
            root.update_idletasks()
            app._mode=None
            app._layout()
            self.assertEqual(app._mode,"medium")
            self.assertTrue(app.sidebar.winfo_ismapped())
            app.show_panel("sheet")
            root.update_idletasks()
            self.assertTrue(app.sheet_panel.winfo_ismapped())
            root.geometry("750x600")
            root.update_idletasks()
            app._mode=None
            app._layout()
            self.assertEqual(app._mode,"small")
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
