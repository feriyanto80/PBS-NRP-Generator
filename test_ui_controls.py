"""v1.0.13 regression coverage: meaningful drawing toggles and live transfer progress."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import ezdxf
from reportlab.lib.pagesizes import A3,landscape

from drawing_settings import apply_presentation
from engineering_render import draw_dxf,draw_pdf
from responsive_ui import ResponsiveNRP


class LayerSettingTests(unittest.TestCase):
    def setUp(self):
        self.lines=[
          ("FEEDER 96C","FEEDER",[(107.0,-6.0),(107.001,-6.001)]),
          ("Distribution","DISTRIBUSI",[(107.001,-6.001),(107.002,-6.002)])]
        self.points=[("Pole 001",(107.001,-6.001))]
        self.osm={"roads":[[(107.0,-6.0),(107.003,-6.002)]],
                  "buildings":[[(107.001,-6.001),(107.0012,-6.001),
                                (107.0012,-6.0013),(107.001,-6.001)]]}
        self.bb=(106.999,-6.004,107.005,-5.998)
        self.sheets=[("Overview",self.bb),("Detail 01",self.bb)]

    def test_layer_filters_do_not_destroy_imported_sources(self):
        visible,pts,osm=apply_presentation(
            self.lines,self.points,self.osm,
            {"feeder":False,"roads":False,"buildings":False,
             "points":False,"point_shape":"Square","point_labels":False})
        self.assertEqual(len(visible),1)
        self.assertEqual(visible[0][1],"DISTRIBUSI")
        self.assertEqual(pts,[])
        self.assertEqual(osm["roads"],[])
        self.assertEqual(osm["buildings"],[])
        self.assertEqual(len(self.lines),2)
        self.assertEqual(len(self.osm["roads"]),1)
        self.assertEqual(osm["_drawing_style"]["point_shape"],"Square")

    def test_dxf_symbols_and_labels_changes_real_export(self):
        with tempfile.TemporaryDirectory() as temp:
            lines,points,osm=apply_presentation(
                self.lines,self.points,self.osm,
                {"feeder":False,"roads":False,"buildings":False,
                 "point_shape":"Square","point_size":3,
                 "point_labels":False})
            path=os.path.join(temp,"setting.dxf")
            draw_dxf(path,lines,points,self.sheets,osm)
            model=ezdxf.readfile(path).modelspace()
            self.assertEqual(len(model.query('LWPOLYLINE[layer=="FEEDER"]')),0)
            self.assertEqual(len(model.query('LWPOLYLINE[layer=="DISTRIBUSI"]')),1)
            self.assertEqual(len(model.query('LWPOLYLINE[layer=="POINTS"]')),1)
            self.assertEqual(len(model.query('TEXT[layer=="LABELS"]')),0)
            pdf=os.path.join(temp,"setting.pdf")
            draw_pdf(pdf,lines,points,None,*landscape(A3),
                     "Route Plan",self.sheets,osm)
            self.assertGreater(Path(pdf).stat().st_size,3000)

    def test_point_shape_limits(self):
        _,_,osm=apply_presentation([],[],None,{"point_shape":"nonsense","point_size":99})
        self.assertEqual(osm["_drawing_style"]["point_shape"],"Circle")
        self.assertEqual(osm["_drawing_style"]["point_size"],5.0)


class DownloadProgressTests(unittest.TestCase):
    def test_google_byte_progress_is_separate_from_workflow(self):
        app=ResponsiveNRP.__new__(ResponsiveNRP)
        app.google_download_value=MagicMock()
        app.google_download_stage=MagicMock()
        app.google_download_detail=MagicMock()
        app._update_google_download_display(
            "Google Buildings | TILE 1/1 | Google Buildings | DOWNLOAD | "
            "2e7 | 0.172 GB/5.476 GB (3.1%) | 9.1 MB/s | ETA 9m55s")
        app.google_download_value.set.assert_called_once_with(3.1)
        stage=app.google_download_stage.set.call_args.args[0]
        detail=app.google_download_detail.set.call_args.args[0]
        self.assertIn("3.1%",stage)
        self.assertIn("0.172 / 5.476 GB",detail)
        self.assertIn("ETA 9m55s",detail)

    def test_completed_download_marked_without_changing_workflow(self):
        app=ResponsiveNRP.__new__(ResponsiveNRP)
        app.google_download_value=MagicMock()
        app.google_download_stage=MagicMock()
        app.google_download_detail=MagicMock()
        app._update_google_download_display(
            "Google Buildings | TILE 1/1 | Google Buildings | CACHE HIT | 2e7")
        app.google_download_value.set.assert_called_once_with(100)


if __name__=="__main__":
    unittest.main()
