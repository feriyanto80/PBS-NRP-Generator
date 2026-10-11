"""Offline Google tile size guard, cache and independent zoom regression tests."""
import tempfile
import unittest
from unittest.mock import MagicMock
from google_auto import acquire_google, TILE_PREFIX
from responsive_ui import ResponsiveNRP


def catalogue(size_mb):
    return {"type":"FeatureCollection","features":[{
      "type":"Feature",
      "geometry":{"type":"Polygon","coordinates":[[
         [106.95,-6.2],[107.15,-6.2],[107.15,-5.95],[106.95,-5.95],[106.95,-6.2]]]},
      "properties":{"tile_id":"fixture","size_mb":size_mb,
                    "tile_url":TILE_PREFIX+"abc_buildings.csv.gz"}}]}

BBOX=(107.,-6.1,107.04,-6.06)


class AutoGoogleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_too_large_tile_skips_without_false_footprints(self):
        result=acquire_google(BBOX,cache_dir=self.tmp.name,
                              manifest=catalogue(1500),
                              tile_loader=lambda url,bbox:self.fail("Large tile must not download"))
        self.assertEqual(result["status"],"skipped_large")
        self.assertEqual(result["polygons"],[])
        self.assertFalse(result["complete"])

    def test_public_small_tile_automatically_merges_and_caches(self):
        building=[(107.01,-6.08),(107.011,-6.08),(107.011,-6.081),(107.01,-6.08)]
        calls=[]
        def loader(url,bbox):
            calls.append(url)
            return [building]
        params={"cache_dir":self.tmp.name,"manifest":catalogue(2),
                "tile_loader":loader}
        result=acquire_google(BBOX,**params)
        self.assertEqual(result["status"],"ready")
        self.assertEqual(len(result["polygons"]),1)
        self.assertEqual(len(calls),1)
        cached=acquire_google(BBOX,**params)
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(len(calls),1)

    def test_no_coverage(self):
        data=catalogue(2)
        data["features"][0]["geometry"]["coordinates"]=[
          [[90,10],[91,10],[91,11],[90,11],[90,10]]]
        result=acquire_google(BBOX,cache_dir=self.tmp.name,manifest=data)
        self.assertEqual(result["status"],"no_coverage")


class PreviewZoomTests(unittest.TestCase):
    def test_map_zoom_and_fit_do_not_change_sheet(self):
        app=ResponsiveNRP.__new__(ResponsiveNRP)
        app.lines=[("road","DISTRIBUSI",[(107.,-6.1),(107.04,-6.06)])]
        app.points=[]
        app._map_view=None
        app._sheet_view=None
        app._draw_pending=None
        app.root=MagicMock()
        app.root.after.return_value="job"
        app.map=MagicMock()
        app.map.winfo_width.return_value=900
        app.map.winfo_height.return_value=700
        app.mini=MagicMock()
        app.mini.winfo_width.return_value=500
        app.mini.winfo_height.return_value=450
        app._zoom("map",.80)
        self.assertIsNotNone(app._map_view)
        self.assertIsNone(app._sheet_view)
        self.assertLess(app._map_view[2]-app._map_view[0],.04)
        app._fit("map")
        self.assertIsNone(app._map_view)


if __name__=="__main__":
    unittest.main()
