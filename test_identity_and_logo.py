"""Windows regression for PBS ID native JSON RPC and original STARLITE template.

Server is mocked. Never submit real username/password or session tokens in CI.
Tests verify fail-closed behavior, client ID isolation, device hash and Windows
DPAPI storage; no bypass/preview mode is installed in production.
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pbs_identity import (
    IdentityClient, IdentityRejected, IdentityNetworkError,
    CLIENT_ID,API_URL,load_session,save_session,clear_session
)
from starlite_logo import LIGHT,NAVY
from cad_sheet_layout import _build_tab
import ezdxf


class FakeResponse:
    def __init__(self,body):
        self.value=json.dumps(body).encode("utf-8")
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,*args):return self.value


class PBSIDTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.remote={}
        def opener(request,timeout=20):
            self.assertEqual(request.full_url,API_URL)
            self.assertEqual(request.get_method(),"POST")
            body=json.loads(request.data)
            self.calls.append(body)
            action=body["action"]
            return FakeResponse(self.remote.get(action,{"ok":False,
                                        "message":"NRP entitlement not registered"}))
        self.client=IdentityClient(opener=opener)

    def test_credential_contract_and_device_fingerprint(self):
        self.remote["login"]={"ok":True,"token":"unit-test-session",
            "expires_at":"2099-01-01T00:00:00Z",
            "user":{"username":"test_account","role":"USER","status":"ACTIVE"}}
        self.remote["session_validate"]={"ok":True,
            "user":{"username":"test_account","role":"USER","status":"ACTIVE"},
            "expires_at":"2099-01-01T00:00:00Z"}
        with tempfile.TemporaryDirectory() as location,patch.dict(os.environ,{"LOCALAPPDATA":location}):
            session=self.client.login(" test_account ","example-only-fake-password")
            self.assertEqual(self.calls[0]["action"],"login")
            self.assertEqual(self.calls[0]["client_id"],"PBS_NRP_DESKTOP")
            self.assertEqual(self.calls[0]["username"],"test_account")
            self.assertEqual(self.calls[0]["device_hash"],self.client.device_hash)
            self.assertEqual(self.calls[0]["device_name"],self.client.device_name)
            self.assertEqual(self.client.validate(session)["user"]["role"],"USER")
            self.assertEqual(self.calls[1]["action"],"session_validate")
            if os.name=="nt":
                save_session(session)
                data=(Path(location)/"PBS_NRP_Generator"/"identity"/"session.dpapi").read_bytes()
                self.assertNotIn(b"unit-test-session",data)
                self.assertEqual(load_session()["token"],"unit-test-session")
                clear_session()
                self.assertIsNone(load_session())

    def test_reject_wrong_server_grant_and_inactive_user(self):
        with self.assertRaises(IdentityRejected):
            self.client.login("user","fake-password")
        self.remote["login"]={"ok":True,"token":"x",
            "user":{"username":"user","role":"USER","status":"DISABLED"}}
        with self.assertRaises(IdentityRejected):
            self.client.login("user","fake-password")

    def test_login_cannot_reuse_pole40_client_identity(self):
        self.assertNotEqual(CLIENT_ID,"PBS_POLE40_DESKTOP")
        self.assertEqual(CLIENT_ID,"PBS_NRP_DESKTOP")


class OriginalLogoTests(unittest.TestCase):
    def test_distinct_original_blue_shapes(self):
        self.assertGreater(len(LIGHT),10)
        self.assertGreater(len(NAVY),7)
        self.assertNotEqual(LIGHT,NAVY)

    def test_editable_colored_logo_vector_in_cad_paper_space(self):
        doc=ezdxf.new("R2018")
        for layer in ("NRP_TB_LOGO","NRP_TB_FRAME","NRP_TB_TEXT",
                      "NRP_TB_SYMBOL","NRP_TB_CABLE","NRP_TB_COMPASS"):
            doc.layers.new(layer)
        layout=doc.layouts.new("NRP_SAMPLE")
        _build_tab(layout,"PBS NRP TEMPLATE","Overview",0,2,{})
        solids=[ent for ent in layout.query("SOLID")
                if ent.dxf.layer=="NRP_TB_LOGO"]
        self.assertGreater(len(solids),4)
        self.assertGreater(len({ent.dxf.true_color for ent in solids}),1)
        text=[ent.dxf.text for ent in layout.query("TEXT")]
        self.assertTrue(any("S T A R L I T E" in value for value in text))


if __name__=="__main__":
    unittest.main()
