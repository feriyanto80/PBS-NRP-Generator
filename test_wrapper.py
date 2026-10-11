import tempfile
import unittest
import zipfile
from pathlib import Path
from kml_support import read_source, parse_kml_bytes

KML=b'''<?xml version="1.0" encoding="utf-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>FEEDER 96C</name><LineString><coordinates>107.1,-6.1,0 107.2,-6.2,0</coordinates></LineString></Placemark>
<Placemark><name>ODP 01</name><Point><coordinates>107.1,-6.1,0</coordinates></Point></Placemark>
<Placemark><name>SUBFEEDER</name><MultiGeometry><LineString><coordinates>107.2,-6.2 107.3,-6.3</coordinates></LineString></MultiGeometry></Placemark>
</Document></kml>'''


class KmlKmzTests(unittest.TestCase):
    def test_kml_and_kmz_equivalent(self):
        with tempfile.TemporaryDirectory() as folder:
            kml = Path(folder)/'example.KML'
            kmz = Path(folder)/'example.kmz'
            kml.write_bytes(KML)
            with zipfile.ZipFile(kmz, 'w') as z:
                z.writestr('doc.kml', KML)
            parsed_kml = read_source(kml)
            self.assertEqual(parsed_kml, read_source(kmz))
            self.assertEqual((len(parsed_kml[0]),len(parsed_kml[1])), (2,1))
            self.assertEqual(parsed_kml[0][0][1], 'FEEDER')
            self.assertEqual(parsed_kml[0][1][1], 'SUBFEEDER')

    def test_missing_geometries(self):
        with self.assertRaises(ValueError):
            parse_kml_bytes(b'<kml><Document /></kml>')

    def test_malformed_kml(self):
        with self.assertRaises(ValueError):
            parse_kml_bytes(b'<kml>')

    def test_reject_other_extension(self):
        with self.assertRaises(ValueError):
            read_source('input.csv')


if __name__=='__main__':
    unittest.main()
