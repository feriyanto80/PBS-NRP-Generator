"""Regression coverage for responsive PBS NRP background export v1.0.22.7.

Does not require installed ODA, Google/OSM connectivity, or private CAD
templates: renderer dependencies are injected/mocked.
"""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from export_worker import export_job,output_names


class ExportWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=self.tmp.name
        self.lines=[("R","DISTRIBUSI",[(107.0,-6.0),(107.001,-6.001)])]
        self.points=[("HP 001",(107.001,-6.001))]
        self.sheets=[("Overview",(106.9,-6.1,107.1,-5.9)),
                     ("Detail 01",(107.0,-6.02,107.02,-6.0))]
        self.osm={"roads":[[(107.0,-6.0),(107.001,-6.0)]],
                  "buildings":[[(107.0,-6.0),(107.001,-6.0),(107.0,-6.001)]]}
        self.events=[]
        self.workers=[]

    def _pdf(self,path,*args,progress=None):
        self.workers.append(threading.current_thread().name)
        if progress:
            progress(1,2,"Overview")
            progress(2,2,"Detail 01")
        Path(path).write_bytes(b"%PDF-1.7\n"+b" "*4096)

    def _dxf(self,path,*args,progress=None):
        self.workers.append(threading.current_thread().name)
        if progress:
            progress(.2,"Road+Footprint")
            progress(.8,"PaperSpace A3 2/2")
            progress(1,"DXF complete")
        Path(path).write_bytes(b"  0\nSECTION\n"+b" "*4096)

    def _config(self,want_dwg=False,dwg_converter=None):
        return {
            "folder":self.folder,"title":"Kramatagung_Design_SND",
            "lines":self.lines,"points":self.points,"sheets":self.sheets,
            "osm":self.osm,"want_dwg":want_dwg,"converter":"ODAFileConverter.exe",
            "emit":lambda *fields:self.events.append(fields),
            "pdf_renderer":self._pdf,"dxf_renderer":self._dxf,
            "dwg_converter":dwg_converter}

    def test_pdf_dxf_progress_pages_and_atomic_outputs(self):
        result=export_job(**self._config())
        self.assertEqual(len(result.files),2)
        self.assertFalse(result.warning)
        self.assertTrue(Path(result.pdf).exists())
        self.assertTrue(Path(result.dxf).exists())
        self.assertTrue(any("Halaman 1/2" in event[2] for event in self.events))
        self.assertTrue(any("Halaman 2/2" in event[2] for event in self.events))
        self.assertEqual(self.events[-1][0],100)
        self.assertFalse(Path(result.pdf[:-4]+".exporting.pdf").exists())
        self.assertFalse(Path(result.dxf[:-4]+".exporting.dxf").exists())
        self.assertNotIn("Tk",self.workers)

    def test_work_done_on_worker_thread_not_gui_thread(self):
        holder={}
        thread=threading.Thread(target=lambda:holder.setdefault(
            "result",export_job(**self._config())),name="NRP-Export-Worker")
        thread.start()
        thread.join(timeout=4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.workers,["NRP-Export-Worker"]*2)
        self.assertEqual(len(holder["result"].files),2)

    def test_dwg_success_retains_oda_export_semantics(self):
        def convert(dxf_path,oda):
            self.assertEqual(oda,"ODAFileConverter.exe")
            self.assertTrue(Path(dxf_path).is_file())
            destination=Path(dxf_path).with_suffix(".dwg")
            destination.write_bytes(b"AC1032"+b"\x00"*4096)
            return str(destination)
        result=export_job(**self._config(True,convert))
        self.assertEqual(len(result.files),3)
        self.assertEqual(Path(result.dwg).read_bytes()[:6],b"AC1032")
        self.assertFalse(result.warning)

    def test_dwg_failure_keeps_pdf_dxf_and_reports_warning(self):
        def fail(*args):
            raise RuntimeError("Invalid RegApp from ODA")
        result=export_job(**self._config(True,fail))
        self.assertEqual(len(result.files),2)
        self.assertIn("Invalid RegApp",result.warning)
        self.assertEqual(self.events[-1][0],100)
        self.assertIn("peringatan",self.events[-1][1].lower())

    def test_pdf_failure_keeps_existing_final_pdf_and_writes_error_log(self):
        pdf,_,_,log=output_names(self.folder,"Kramatagung_Design_SND")
        Path(pdf).write_bytes(b"original pdf saved")
        def fail(path,*args,progress=None):
            Path(path).write_bytes(b"partial")
            raise ValueError("boom PDF")
        cfg=self._config()
        cfg["pdf_renderer"]=fail
        with self.assertRaisesRegex(RuntimeError,"Ekspor PDF gagal"):
            export_job(**cfg)
        self.assertEqual(Path(pdf).read_bytes(),b"original pdf saved")
        self.assertTrue(Path(log).is_file())
        self.assertIn("Traceback",Path(log).read_text(encoding="utf8"))
        self.assertFalse(Path(pdf[:-4]+".exporting.pdf").exists())


if __name__=="__main__":
    unittest.main()
