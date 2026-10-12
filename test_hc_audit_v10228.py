"""v1.0.22.8 — Source-derived HC candidate annotations match Lemahabang text.

Kramatagung data itself stays private; these tests use a synthetic folder
structure with the same 99.AUDIT_DESIGN/HC hierarchy and RC number syntax.
"""
import tempfile
import unittest
from pathlib import Path

import ezdxf
from kml_support import parse_kml_bytes, TypedPointName
from drafter_annotations import prepare_points,plan_labels,plan_symbols
from template_symbols import canonical
from engineering_render import draw_dxf


def sample_kml():
    def item(name,lon,lat):
        return (f'<Placemark><name>{name}</name><Point><coordinates>'
                f'{lon},{lat},0</coordinates></Point></Placemark>')
    hc=''.join([
        item("RC_0000001",113.20000,-7.84000),
        item("RC_0000002",113.20045,-7.84000),
        item("RC_0000999",113.20090,-7.84000),
        item("RC_0001000",113.20135,-7.84000),
        item("RC_0002998",113.20180,-7.84000),
    ])
    # An audit 'Road' is not a feeder; an unverified T40 is not a T6.
    return (f'<kml><Document><Folder><name>Project</name>'
            f'<Folder><name>ODP</name>'
            f'{item("ODP 01",113.20000,-7.842)}'
            f'</Folder>'
            f'<Folder><name>99.AUDIT_DESIGN</name>'
            f'<Folder><name>HC</name>{hc}</Folder>'
            f'<Folder><name>Pole</name>{item("T40-00001",113.201,-7.8401)}</Folder>'
            f'<Folder><name>Sumber</name>{item("Stasiun Leces",113.202,-7.8402)}</Folder>'
            f'<Folder><name>Road</name><Placemark><name>OSM 4000</name>'
            f'<LineString><coordinates>113.20,-7.84 113.21,-7.84</coordinates>'
            f'</LineString></Placemark></Folder>'
            f'</Folder></Folder></Document></kml>').encode()


class HCAuditNumericSourceTests(unittest.TestCase):
    def test_only_hc_audit_items_enter_nrpdrafter(self):
        lines,points=parse_kml_bytes(sample_kml())
        self.assertEqual(lines,[]) # audit roads are not distribution cable
        self.assertEqual(len(points),6) # 5 candidates + 1 actual ODP
        hc=[name for name,_ in points if getattr(name,"nrp_source_role","")=="AUDIT_HC"]
        self.assertEqual([str(x) for x in hc],["001","002","999","1000","2998"])
        self.assertTrue(all(canonical(name)=="HP" for name in hc))
        self.assertEqual([name.nrp_source_id for name in hc],
                         ["RC_0000001","RC_0000002","RC_0000999",
                          "RC_0001000","RC_0002998"])
        self.assertTrue(all(name.nrp_verification=="RESIDENTIAL_CANDIDATE"
                            for name in hc))
        labels=[(kind,label) for _,_,kind,label in prepare_points(points)]
        self.assertEqual(labels,[("ODP","ODP 01"),("HP","001"),("HP","002"),
                                 ("HP","999"),("HP","1000"),("HP","2998")])
        self.assertFalse(any("T40" in label or "RC_" in label for _,label in labels))

    def test_no_numeric_relabeling_for_nested_lemahabang(self):
        kml=b'''<kml><Document><Folder><name>ODC</name>
        <Folder><name>W2_LMB_JKBN.MJI_001</name>
        <Folder><name>HP</name><Folder><name>HP ODP 01/01</name>
        <Placemark><name>001</name><Point><coordinates>107.1,-6.2</coordinates></Point></Placemark>
        </Folder></Folder></Folder></Folder></Document></kml>'''
        _,points=parse_kml_bytes(kml)
        self.assertEqual(prepare_points(points)[0][2:4],("HP","001"))

    def test_other_hc_location_does_not_authorize_rc(self):
        kml=b'''<kml><Folder><name>HC</name><Placemark>
        <name>RC_0000001</name><Point><coordinates>113.2,-7.84</coordinates>
        </Point></Placemark></Folder></kml>'''
        _,points=parse_kml_bytes(kml)
        self.assertEqual(prepare_points(points)[0][2],"UNKNOWN")

    def test_invalid_or_unverified_audit_classes_are_excluded(self):
        source=sample_kml().replace(b'RC_0000002',b'BAD_REFERENCE')
        _,points=parse_kml_bytes(source)
        self.assertEqual(len(points),5) # HC unknown excluded, not numbered

    def test_dxf_homepass_text_layer_not_discs(self):
        lines,points=parse_kml_bytes(sample_kml())
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"HC_sample.dxf"
            draw_dxf(str(output),lines,points,
                 [("Overview",(113.19,-7.85,113.21,-7.83))],
                 {"_cad_reference_style":False})
            doc=ezdxf.readfile(output)
            self.assertEqual(len(doc.audit().errors),0)
            labels=[e.dxf.text for e in doc.modelspace().query('TEXT[layer=="Homepass"]')]
            self.assertCountEqual(labels,["001","002","999","1000","2998"])
            self.assertFalse(any(e.dxf.text.startswith("RC_")
                for e in doc.modelspace().query("TEXT")))
            self.assertEqual(len(doc.modelspace().query('CIRCLE[layer=="POINTS"]')),0)

if __name__=="__main__":
    unittest.main()
