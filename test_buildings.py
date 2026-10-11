"""Tests for v1.0.7 polygon sources and drafter titleblock."""
import csv
import gzip
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from reportlab.pdfgen import canvas as pdfcanvas

from building_sources import load_polygons, merge_sources
from drafter_titleblock import draw_titleblock


KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>Sample Building</name><Polygon><outerBoundaryIs><LinearRing>
<coordinates>107.000,-6.000 107.001,-6.000 107.001,-6.001 107.000,-6.001 107.000,-6.000</coordinates>
</LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document></kml>"""


class BuildingSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.bbox = (106.99, -6.02, 107.02, -5.99)
        self.coords = [(107,-6),(107.001,-6),(107.001,-6.001),(107,-6.001),(107,-6)]

    def test_kml_and_kmz_source(self):
        kml = self.directory / "building.kml"
        kmz = self.directory / "building.kmz"
        kml.write_bytes(KML)
        with zipfile.ZipFile(kmz,"w") as archive:
            archive.writestr("doc.kml",KML)
        self.assertEqual(len(load_polygons(kml,bbox=self.bbox)["polygons"]),1)
        self.assertEqual(len(load_polygons(kmz,bbox=self.bbox)["polygons"]),1)

    def test_geojson_and_geojson_clipping(self):
        data={"type":"FeatureCollection","features":[{"type":"Feature","geometry":{
          "type":"Polygon","coordinates":[self.coords]},"properties":{}}]}
        path=self.directory/"open_buildings.geojson"
        path.write_text(json.dumps(data),encoding="utf-8")
        self.assertEqual(len(load_polygons(path,bbox=self.bbox)["polygons"]),1)
        self.assertEqual(len(load_polygons(path,bbox=(109,1,110,2))["polygons"]),0)

    def test_google_wkt_csv_confidence_filter(self):
        path=self.directory/"google.csv.gz"
        polygon="POLYGON ((107 -6, 107.001 -6, 107.001 -6.001, 107 -6.001, 107 -6))"
        with gzip.open(path,"wt",encoding="utf-8",newline="") as file:
            writer=csv.DictWriter(file,fieldnames=["geometry","confidence"])
            writer.writeheader()
            writer.writerow({"geometry":polygon,"confidence":.88})
            writer.writerow({"geometry":polygon,"confidence":.61})
        rows=load_polygons(path,bbox=self.bbox,min_confidence=.70)
        self.assertEqual(len(rows["polygons"]),1)

    def test_merge_dedupe_iou(self):
        original={"roads":[],"buildings":[self.coords]}
        merged=merge_sources(original,kml=[self.coords],google=[self.coords])
        self.assertEqual(merged["footprint_total"],1)
        self.assertEqual(merged["footprint_duplicates"],2)
        self.assertEqual(merged["footprint_sources"]["OSM"],1)

    def test_google_fills_missing_osm(self):
        shifted=[(x+.003,y) for x,y in self.coords]
        merged=merge_sources({"roads":[],"buildings":[self.coords]},
                             google=[shifted])
        self.assertEqual(merged["footprint_total"],2)
        self.assertEqual(merged["footprint_sources"]["GOOGLE"],1)

    def test_titleblock_pdf_render(self):
        path=self.directory/"titleblock.pdf"
        c=pdfcanvas.Canvas(str(path),pagesize=(1191,842))
        draw_titleblock(c,992,18,163,804,"TEST PROJECT","Overview",0,5,
                        {"footprint_sources":{"OSM":12,"KML":3,"GOOGLE":25}})
        c.showPage()
        c.save()
        self.assertGreater(path.stat().st_size,6000)


if __name__=="__main__":
    unittest.main()
