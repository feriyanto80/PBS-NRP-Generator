"""DWG conversion regression without bundling/running proprietary ODA binaries."""
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import dwg_conversion


class ODACLIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.converter=self.root/"Program Files"/"ODA"/"ODAFileConverter.exe"
        self.converter.parent.mkdir(parents=True)
        self.converter.write_bytes(b"MZfake")
        self.dxf=self.root/"PBS_NRP_ABD_St_Lemah_Abang.dxf"
        self.dxf.write_bytes(b"DXF 2018 mock fixture")

    def test_success_seven_arguments_unicode_safe_output(self):
        seen=[]
        def runner(cmd,**kwargs):
            seen.append(cmd)
            self.assertEqual(cmd[0],str(self.converter.resolve()))
            self.assertEqual(cmd[3:],
                             ["ACAD2018","DWG","0","1","*.dxf"])
            self.assertEqual(len(cmd),8)
            self.assertEqual(list(Path(cmd[1]).glob("*.dxf"))[0].name,
                             "PBS_NRP_CONVERT.dxf")
            nested=Path(cmd[2])/"nested_from_ODA"
            nested.mkdir()
            (nested/"PBS_NRP_CONVERT.DWG").write_bytes(
                b"AC1032"+b"\0"*2048)
            return subprocess.CompletedProcess(cmd,0,"","")
        with patch("dwg_conversion.subprocess.run",side_effect=runner):
            result=dwg_conversion.convert_dwg(
                self.dxf,str(self.converter))
        self.assertTrue(Path(result).samefile(self.dxf.with_suffix(".dwg")))
        # Windows temp paths may compare in short 8.3 vs long form.
        self.assertTrue(dwg_conversion._valid_dwg(result))
        self.assertEqual(len(seen),1)
        self.assertFalse(self.dxf.with_name(
            self.dxf.stem+"_ODA_Conversion.log").exists())

    def test_retry_without_audit_if_oda_does_not_produce_file(self):
        attempts=[]
        def runner(cmd,**kwargs):
            attempts.append(cmd[6])
            if cmd[6]=="0":
                (Path(cmd[2])/"PBS_NRP_CONVERT.dwg").write_bytes(
                    b"AC1032"+b"\0"*2048)
            return subprocess.CompletedProcess(cmd,0,"C:/Users/User/Desktop/DWG","")
        with patch("dwg_conversion.subprocess.run",side_effect=runner):
            result=dwg_conversion.convert_dwg(self.dxf,str(self.converter))
        self.assertEqual(attempts,["1","0"])
        self.assertTrue(Path(result).exists())

    def test_failure_reports_log_not_only_a_directory_name(self):
        def runner(cmd,**kwargs):
            return subprocess.CompletedProcess(
                cmd,1,"C:/Users/User/Desktop/DWG","")
        with patch("dwg_conversion.subprocess.run",side_effect=runner):
            with self.assertRaises(RuntimeError) as caught:
                dwg_conversion.convert_dwg(self.dxf,str(self.converter))
        self.assertIn("Lihat log lengkap:",str(caught.exception))
        log=self.dxf.with_name(self.dxf.stem+"_ODA_Conversion.log")
        self.assertTrue(log.exists())
        contents=log.read_text(encoding="utf-8")
        self.assertIn("stdout: C:/Users/User/Desktop/DWG",contents)
        self.assertIn("filter=*.dxf",contents)
        self.assertIn("Exit code: 1",contents)
        self.assertEqual(contents.count("Exit code: 1"),7)
        self.assertIn("CONTROL PROBE: FAILED",contents)


    def test_default_filter_fallback(self):
        calls=[]
        def runner(cmd,**kwargs):
            calls.append(cmd)
            if len(cmd)==7 and Path(cmd[1]).name=="input":
                (Path(cmd[2])/"PBS_NRP_CONVERT.dwg").write_bytes(
                    b"AC1032"+b"\0"*2048)
            return subprocess.CompletedProcess(cmd,0,"","")
        with patch("dwg_conversion.subprocess.run",side_effect=runner):
            result=dwg_conversion.convert_dwg(self.dxf,str(self.converter))
        self.assertTrue(dwg_conversion._valid_dwg(result))
        self.assertEqual([len(cmd) for cmd in calls],[8,8,8,7])

    def test_cad_auditor_sanitizes_dxf_without_changing_original(self):
        import ezdxf
        sample=self.root/"unsanitized.dxf"
        doc=ezdxf.new("R2018")
        doc.modelspace().add_line((10,10),(20,20),
                                  dxfattribs={"linetype":"dashed2"})
        doc.saveas(sample)
        original=sample.read_bytes()
        staged=self.root/"staged.dxf"
        log=[]
        dwg_conversion._sanitize_dxf(sample,staged,log)
        self.assertEqual(sample.read_bytes(),original)
        check=ezdxf.readfile(staged).audit()
        self.assertEqual(len(check.errors),0)
        self.assertEqual(len(check.fixes),0)

    def test_reject_non_dwg_output_header(self):
        def runner(cmd,**kwargs):
            (Path(cmd[2])/"PBS_NRP_CONVERT.dwg").write_bytes(
                b"NOTDWG"+b"\0"*2048)
            return subprocess.CompletedProcess(cmd,0,"","")
        with patch("dwg_conversion.subprocess.run",side_effect=runner):
            with self.assertRaises(RuntimeError):
                dwg_conversion.convert_dwg(self.dxf,str(self.converter))
        self.assertFalse(self.dxf.with_suffix(".dwg").exists())

if __name__=="__main__":
    unittest.main()
