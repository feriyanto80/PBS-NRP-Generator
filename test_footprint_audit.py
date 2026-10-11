"""v1.0.10 regression: KML parcel polygons must not be counted as buildings."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from footprint_classify import audit_main_kml
from building_sources import merge_sources
from google_auto import MANIFEST_URL

DATA="""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Placemark><name>Parsel 001</name><Polygon><outerBoundaryIs><LinearRing>
   <coordinates>107,-6 107.002,-6 107.002,-6.001 107,-6.001 107,-6</coordinates>
  </LinearRing></outerBoundaryIs></Polygon></Placemark>
  <Placemark><name>Bangunan rumah 02</name><Polygon><outerBoundaryIs><LinearRing>
   <coordinates>107.002,-6 107.0022,-6 107.0022,-6.0002 107.002,-6.0002 107.002,-6</coordinates>
  </LinearRing></outerBoundaryIs></Polygon></Placemark>
  <Placemark><name>Area Desa</name><Polygon><outerBoundaryIs><LinearRing>
   <coordinates>106.99,-6.01 107.03,-6.01 107.03,-5.99 106.99,-5.99 106.99,-6.01</coordinates>
  </LinearRing></outerBoundaryIs></Polygon></Placemark>
  <Placemark><name>New ODP</name><ExtendedData><Data name="building"><value>yes</value></Data></ExtendedData>
   <Polygon><outerBoundaryIs><LinearRing><coordinates>
    107.004,-6 107.0042,-6 107.0042,-6.0002 107.004,-6.0002 107.004,-6
  </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document></kml>""".encode()


class ClassifierTest(unittest.TestCase):
    def test_only_explicit_buildings_from_kml(self):
        with tempfile.TemporaryDirectory() as directory:
            kml=Path(directory)/"network.kml"
            kml.write_bytes(DATA)
            info=audit_main_kml(kml,(106.98,-6.02,107.05,-5.95))
            self.assertEqual(info["raw_polygons"],4)
            self.assertEqual(info["unclassified_polygons"],2)
            self.assertEqual(len(info["polygons"]),2)
            self.assertEqual(info["classification"],"EXPLICIT_BUILDING_ONLY")
            merged=merge_sources({"roads":[],"buildings":[]},kml=info["polygons"])
            self.assertEqual(merged["footprint_total"],2)

    def test_kmz_equivalent(self):
        with tempfile.TemporaryDirectory() as directory:
            kml=Path(directory)/"network.kml"
            kmz=Path(directory)/"network.kmz"
            kml.write_bytes(DATA)
            with zipfile.ZipFile(kmz,"w") as package:
                package.writestr("doc.kml",DATA)
            bbox=(106.98,-6.02,107.05,-5.95)
            self.assertEqual(
                audit_main_kml(kml,bbox)["polygons"],
                audit_main_kml(kmz,bbox)["polygons"])

    def test_google_catalog_source_not_broken_404_url(self):
        self.assertEqual(
            MANIFEST_URL,
            "https://openbuildings-public-dot-gweb-research.uw.r.appspot.com/public/tiles.geojson"
        )

    def test_unclassified_parcels_never_enter_building_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"parcels.kml"
            file.write_bytes(DATA.replace(b"Bangunan rumah 02",b"Parcel 02").
                                  replace(b'building"><value>yes',b'landuse"><value>residential'))
            r=audit_main_kml(file,(106.98,-6.02,107.05,-5.95))
            self.assertEqual(len(r["polygons"]),0)
            self.assertEqual(r["unclassified_polygons"],4)


if __name__=="__main__":
    unittest.main()
