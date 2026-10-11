"""v1.0.14 DWG provider tests without downloading proprietary ODA binaries."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from dwg_provider import (
    locate_oda, save_last_converter, load_last_converter,
    recognized_oda_executable, winget_command, converter_status,
    WINGET_PACKAGE_ID,
)
from dwg_ui import DWGAutoMixin


class OdaDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.exe=self.base/"ODA"/"ODAFileConverter"/"ODAFileConverter.exe"
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b"MZ"+"stub".encode())
        self.config=str(self.base/"settings"/"dwg_provider.json")

    def test_detect_installed_default_path(self):
        found=locate_oda(env={"PATH":""},roots=[str(self.base)],
                         scan_registry=False,config_path=False)
        self.assertEqual(Path(found),self.exe)

    def test_store_and_reuse_installed_path(self):
        save_last_converter(str(self.exe),config_path=self.config)
        self.assertEqual(load_last_converter(self.config),str(self.exe))
        found=locate_oda(env={"PATH":""},roots=[],
                         scan_registry=False,config_path=self.config)
        self.assertEqual(found,str(self.exe))

    def test_reject_wrong_executable_and_deleted_path(self):
        fake=self.base/"not_a_converter.exe"
        fake.write_bytes(b"MZ")
        self.assertFalse(recognized_oda_executable(str(fake)))
        with self.assertRaises(ValueError):
            save_last_converter(str(fake),config_path=self.config)
        save_last_converter(str(self.exe),config_path=self.config)
        self.exe.unlink()
        self.assertIsNone(load_last_converter(self.config))

    def test_package_manager_command_needs_explicit_call(self):
        command=winget_command("winget.exe")
        self.assertEqual(command[0],"winget.exe")
        self.assertIn(WINGET_PACKAGE_ID,command)
        self.assertIn("--interactive",command)
        self.assertNotIn("--silent",command)

    def test_pdf_dxf_can_proceed_if_oda_absent(self):
        ui=DWGAutoMixin()
        ui.want_dwg=MagicMock()
        ui.want_dwg.get.return_value=True
        ui.converter=MagicMock()
        ui.converter.get.return_value=""
        ui.detect_dwg_converter=MagicMock()
        ui._oda_license_ack=False
        with patch("dwg_ui.messagebox.askyesno",return_value=True):
            allowed,restore=ui.dwg_preflight()
        self.assertTrue(allowed)
        self.assertTrue(restore)
        ui.want_dwg.set.assert_called_once_with(False)

    def test_commercial_rights_are_not_automatically_assumed(self):
        ui=DWGAutoMixin()
        ui.want_dwg=MagicMock()
        ui.want_dwg.get.return_value=True
        ui.converter=MagicMock()
        ui.converter.get.return_value=str(self.exe)
        ui._oda_license_ack=False
        with patch("dwg_ui.messagebox.askyesno",return_value=True) as prompt:
            allowed,restore=ui.dwg_preflight()
        self.assertTrue(allowed)
        self.assertFalse(restore)
        self.assertEqual(prompt.call_count,1)
        self.assertTrue(ui._oda_license_ack)


if __name__=="__main__":
    unittest.main()
