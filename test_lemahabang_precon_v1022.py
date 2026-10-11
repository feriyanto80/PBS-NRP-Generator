"""Regression for authentic Lemahabang KMZ: HP under PRECON TO DC.

No customer dataset is embedded in the public repository.
"""
import unittest
from kml_support import parse_kml_bytes, TypedPointName
from template_symbols import canonical
from drafter_annotations import prepare_points


def _sample(folder,number):
    return f"""<Folder><name>{folder}</name>
    <Placemark><name>{number}</name><Point><coordinates>
    107.105,-6.207,0</coordinates></Point></Placemark></Folder>"""


class HomepassReferenceAuthority(unittest.TestCase):
    def test_289_320_in_precon_to_dc_are_hp_not_odc(self):
        numbers=list(range(289,321))
        pieces=[]
        for n in numbers:
            pieces.append(_sample("ODP010_L"+str(1+(n-289)//8),f"{n:03d}"))
        xml=("<kml><Document><Folder><name>ODC</name>"
             "<Folder><name>W2_LMB_JKBN.MJI_010</name>"
             "<Folder><name>PRECON TO DC</name>"
             +"".join(pieces)+"</Folder></Folder></Folder></Document></kml>")
        _,points=parse_kml_bytes(xml.encode())
        self.assertEqual(len(points),32)
        self.assertEqual([canonical(name) for name,_ in points],["HP"]*32)
        labels=[label for _,_,kind,label in prepare_points(points)]
        self.assertEqual(labels,[f"{n:03d}" for n in numbers])
        self.assertNotIn("ODC 290", labels)

    def test_named_devices_keep_original_drafter_label(self):
        xml=b"""<kml><Document><Folder><name>ODC</name>
           <Folder><name>W2_LMB_JKBN.MJI_001</name>
           <Folder><name>ODP</name><Placemark>
           <name>W2_LMB_JKBN.MJI_001_L1</name>
           <Point><coordinates>107.10,-6.21</coordinates></Point>
           </Placemark></Folder>
           <Folder><name>ODC</name><Placemark>
           <name>W2_LMB_JKBN.MJI_001</name>
           <Point><coordinates>107.11,-6.22</coordinates></Point>
           </Placemark></Folder>
           </Folder></Folder></Document></kml>"""
        _,pts=parse_kml_bytes(xml)
        self.assertEqual([canonical(n) for n,_ in pts],["ODP","ODC"])
        self.assertEqual([str(n) for n,_ in pts],
                         ["W2_LMB_JKBN.MJI_001_L1","W2_LMB_JKBN.MJI_001"])
        self.assertTrue(all(isinstance(n,TypedPointName) for n,_ in pts))

    def test_explicit_device_metadata_can_override_numeric_hp(self):
        xml=b"""<kml><Document><Folder><name>PRECON TO DC</name><Placemark>
        <name>289</name><ExtendedData><Data name="device_type">
        <value>ODP</value></Data></ExtendedData>
        <Point><coordinates>107.1,-6.2</coordinates></Point>
        </Placemark></Folder></Document></kml>"""
        _,pts=parse_kml_bytes(xml)
        self.assertEqual(canonical(pts[0][0]),"ODP")


if __name__=="__main__":
    unittest.main()
