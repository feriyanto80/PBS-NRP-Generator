"""ODA 'Invalid RegApp' regression from real Lemahabang source DXF.

The private project data are not embedded. Synthesized native HATCH and
annotative TEXT preserve the same XDATA 1001 APPID patterns.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import subprocess
import ezdxf

from dxf_regapp_integrity import ensure_xdata_regapps,missing_xdata_regapps
from dwg_conversion import _sanitize_dxf,convert_dwg,_valid_dwg


def make_unregistered_dxf(path):
    doc=ezdxf.new("R2018")
    model=doc.modelspace()
    block=doc.blocks.new("NRP_NATIVE_TEST")
    hatch=block.add_hatch(color=2)
    hatch.paths.add_polyline_path([(0,0),(4,0),(4,4),(0,4)],is_closed=True)
    hatch.set_xdata("GradientColor1ACI",[(1070,5)])
    hatch.set_xdata("GradientColor2ACI",[(1070,2)])
    entity=model.add_text("ANNOTATIVE",dxfattribs={"height":2,"insert":(12,15)})
    entity.set_xdata("AcadAnnotative",[(1070,1)])
    model.add_blockref("NRP_NATIVE_TEST",(20,30))
    doc.saveas(path)


class ODARegappCompatibilityTests(unittest.TestCase):
    def test_registers_unlisted_xdata_without_changing_native_entities(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"bad.dxf"
            make_unregistered_dxf(p)
            doc=ezdxf.readfile(p)
            before=len(doc.entitydb)
            self.assertEqual(set(missing_xdata_regapps(doc)),
                {"GradientColor1ACI","GradientColor2ACI","AcadAnnotative"})
            count=ensure_xdata_regapps(doc)
            self.assertEqual(count,{"GradientColor1ACI":1,
                                    "GradientColor2ACI":1,"AcadAnnotative":1})
            self.assertFalse(missing_xdata_regapps(doc))
            self.assertEqual(len(doc.entitydb),before+3)
            self.assertEqual(ensure_xdata_regapps(doc),{})
            doc.saveas(p)
            loaded=ezdxf.readfile(p)
            self.assertFalse(missing_xdata_regapps(loaded))
            self.assertEqual(loaded.dxfversion,"AC1032")
            self.assertEqual(len(loaded.audit().errors),0)
            self.assertEqual(len(list(loaded.modelspace())),2)
            self.assertIn("NRP_NATIVE_TEST",loaded.blocks)
            self.assertTrue(any(e.dxftype()=="HATCH"
                for e in loaded.blocks.get("NRP_NATIVE_TEST")))

    def test_staged_repair_preserves_original_file(self):
        with tempfile.TemporaryDirectory() as td:
            original=Path(td)/"old.dxf"
            stage=Path(td)/"stage.dxf"
            make_unregistered_dxf(original)
            initial=original.read_bytes()
            log=[]
            _sanitize_dxf(original,stage,log)
            self.assertEqual(original.read_bytes(),initial)
            self.assertFalse(missing_xdata_regapps(ezdxf.readfile(stage)))
            self.assertTrue(any("Registered missing XDATA APPID" in x for x in log))

    def test_oda_six_arg_recovers_after_regapp_registration(self):
        with tempfile.TemporaryDirectory() as td:
            original=Path(td)/"project.dxf"
            make_unregistered_dxf(original)
            exe=Path(td)/"ODAFileConverter.exe"
            exe.write_bytes(b"MZtest")
            calls=[]
            def simulate_oda(cmd,**kwargs):
                calls.append(cmd)
                staged=list(Path(cmd[1]).glob("*.dxf"))[0]
                missing=missing_xdata_regapps(ezdxf.readfile(staged))
                output=Path(cmd[2])
                if missing:
                    (output/"project.dwg.err").write_text(
                        "OdError thrown during readFile: Invalid RegApp",
                        encoding="utf-8")
                else:
                    (output/"project.dwg").write_bytes(b"AC1032"+b"\0"*2048)
                return subprocess.CompletedProcess(cmd,0,"","")
            with patch("dwg_conversion.subprocess.run",side_effect=simulate_oda):
                result=convert_dwg(original,str(exe))
            self.assertTrue(_valid_dwg(result))
            self.assertEqual(len(calls),3)
            self.assertTrue(all(len(cmd)==7 for cmd in calls))
            self.assertTrue(missing_xdata_regapps(ezdxf.readfile(original)))

if __name__=="__main__":
    unittest.main()
