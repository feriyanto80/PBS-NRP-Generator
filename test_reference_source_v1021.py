"""Release v1.0.21: actual HP parent authority and safe native CAD registration."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ezdxf
from kml_support import parse_kml_bytes
from reference_basemap import (register_source,basemap_from_reference,
                               mercator,unmercator,_source)
from reference_sheets import reference_sheet_extents
from template_symbols import canonical


class LemahAbangHPAuthority(unittest.TestCase):
    def test_hp_odp_numerical_ids_are_homepasses(self):
        kml=b'''<kml xmlns="http://www.opengis.net/kml/2.2">
        <Document><Folder><name>ODC</name><Folder><name>W2_LMB_JKBN.MJI_003</name>
        <Folder><name>HP</name><Folder><name>HP ODP 02/03</name>
        <Placemark><name>079</name><Point><coordinates>107.17,-6.27</coordinates></Point></Placemark>
        <Placemark><name>080</name><Point><coordinates>107.171,-6.271</coordinates></Point></Placemark>
        </Folder></Folder></Folder></Folder></Document></kml>'''
        _lines,points=parse_kml_bytes(kml)
        self.assertEqual([canonical(name) for name,_ in points],["HP","HP"])
        self.assertEqual([name for name,_ in points],["HP 079","HP 080"])

    def test_explicit_extendeddata_device_still_overrides_hp_folder(self):
        kml=b'''<kml><Document><Folder><name>HP</name><Placemark>
        <name>001</name><ExtendedData><Data name="device_type"><value>ODP</value></Data></ExtendedData>
        <Point><coordinates>107.17,-6.27</coordinates></Point></Placemark>
        </Folder></Document></kml>'''
        _lines,points=parse_kml_bytes(kml)
        self.assertEqual(canonical(points[0][0]),"ODP")


class NativeGeoRegistration(unittest.TestCase):
    def test_affine_anchors_and_native_basemap(self):
        with tempfile.TemporaryDirectory() as tmp:
            dxf=Path(tmp)/"native.dxf"
            doc=ezdxf.new("R2018")
            model=doc.modelspace()
            points=[]
            for i in range(1,161):
                x=20+(i%16)*11.3
                y=50+(i//16)*15.4
                n=f"{i:03d}"
                model.add_text(n,dxfattribs={
                    "insert":(x,y),"layer":"Homepass","height":2})
                wx=11931450+x*1.005+y*.007
                wy=-700255-x*.011+y*.998
                points.append(("HP "+n,unmercator((wx,wy))))
                model.add_lwpolyline(
                    [(x-2,y-2),(x+2,y-2),(x+2,y+2),(x-2,y+2)],
                    close=True,dxfattribs={"layer":"Basic Map"})
            # Regression: actual 2018 Basic Map/Jalan include LINE entities.
            # ezdxf.acc.vector.Vec3 DOES NOT accept [:2] slices.
            model.add_line((10,20),(260,145),dxfattribs={"layer":"Basic Map"})
            model.add_line((22,35),(245,175),dxfattribs={"layer":"Jalan"})
            doc.saveas(dxf)
            _source.cache_clear()
            with patch("exact_template.find_reference",return_value=str(dxf)):
                registered=register_source(points)
                self.assertIsNotNone(registered)
                self.assertGreaterEqual(registered[2]["anchors"],160)
                self.assertLess(registered[2]["median_error_m"],.05)
                geo=basemap_from_reference(points)
                self.assertIsNotNone(geo)
                self.assertEqual(len(geo["reference_paths"]),161)
                self.assertEqual(len(geo["reference_roads"]),1)
                self.assertEqual(len(geo["reference_roads"][0]),2)
                self.assertTrue(geo["_reference_basemap"])

    def test_unrelated_project_does_not_use_2018_map(self):
        with patch("exact_template.find_reference",return_value=None):
            self.assertIsNone(basemap_from_reference(
                [(f"HP {i:03d}",(109.+i*.00001,-7.0))
                 for i in range(1,160)]))


if __name__=="__main__":
    unittest.main()
