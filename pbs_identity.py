"""PBS Central Identity client for NRP - derived from user-supplied Pole40 v1.0.1.7.1.

Source protocol: POST https://id.pbsgroup.id/api JSON with 'action' values
login, session_validate, logout; client_id, app_version, device_hash/name.
No credentials, privileged application tokens or passwords are embedded.
Fail closed: only online-validated sessions grant access. Encrypted Windows
DPAPI persistence (CurrentUser context), never plaintext token storage.

App registration is a SERVER-SIDE requirement: PBS_NRP_DESKTOP must be
authorized by PBS ID server. We do NOT impersonate the Pole40 client ID.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import time
import urllib.error
import urllib.request
import uuid

API_URL="https://id.pbsgroup.id/api"
CLIENT_ID="PBS_NRP_DESKTOP"
APP_CODE="PBS_NRP_GENERATOR"
APP_VERSION="1.0.17"
TIMEOUT_SECONDS=20
REVALIDATE_MINUTES=10


def _directory():
    root=os.environ.get("LOCALAPPDATA") or str(Path.home()/".pbs_nrp")
    folder=Path(root)/"PBS_NRP_Generator"/"identity"
    folder.mkdir(parents=True,exist_ok=True)
    return folder


def _device_fingerprint():
    parts=[platform.system(),platform.machine(),platform.node()]
    if os.name=="nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography") as key:
                parts.append(str(winreg.QueryValueEx(key,"MachineGuid")[0]))
        except OSError:
            parts.append(str(uuid.getnode()))
    else:
        parts.append(str(uuid.getnode()))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class IdentityError(RuntimeError):
    pass


class IdentityRejected(IdentityError):
    pass


class IdentityNetworkError(IdentityError):
    pass


class _DATA_BLOB(ctypes.Structure):
    _fields_=[("cbData",wintypes.DWORD),
              ("pbData",ctypes.POINTER(ctypes.c_byte))]


def _blob(contents):
    buffer=ctypes.create_string_buffer(contents)
    return _DATA_BLOB(len(contents),
        ctypes.cast(buffer,ctypes.POINTER(ctypes.c_byte))),buffer


def _dpapi(data,encrypt=True):
    if os.name!="nt":
        raise RuntimeError("Session persistence memerlukan Windows DPAPI")
    inp,buf=_blob(data)
    out=_DATA_BLOB()
    crypto=ctypes.windll.crypt32
    command=crypto.CryptProtectData if encrypt else crypto.CryptUnprotectData
    command.argtypes=([ctypes.POINTER(_DATA_BLOB),ctypes.c_wchar_p,ctypes.c_void_p,
                       ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,
                       ctypes.POINTER(_DATA_BLOB)])
    command.restype=wintypes.BOOL
    if not command(ctypes.byref(inp),"PBS NRP ID session" if encrypt else None,
                   None,None,None,1,ctypes.byref(out)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out.pbData,out.cbData)
    finally:
        local_free=ctypes.windll.kernel32.LocalFree
        local_free.argtypes=[ctypes.c_void_p]
        local_free.restype=ctypes.c_void_p
        local_free(ctypes.cast(out.pbData,ctypes.c_void_p))


def save_session(data):
    path=_directory()/"session.dpapi"
    encrypted=_dpapi(json.dumps(data,separators=(",",":")).encode("utf-8"))
    temp=path.with_suffix(".writing")
    temp.write_bytes(encrypted)
    os.replace(temp,path)


def load_session():
    path=_directory()/"session.dpapi"
    if not path.is_file():
        return None
    try:
        obj=json.loads(_dpapi(path.read_bytes(),False).decode("utf-8"))
        if (not isinstance(obj,dict) or
                obj.get("device_hash")!=_device_fingerprint()):
            return None
        return obj
    except (OSError,ValueError,RuntimeError):
        return None


def clear_session():
    path=_directory()/"session.dpapi"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _remember_username(username):
    path=_directory()/"settings.json"
    safe={"username":str(username or "").strip()[:128]}
    path.write_text(json.dumps(safe),encoding="utf-8")


def last_username():
    try:
        data=json.loads((_directory()/"settings.json").read_text(encoding="utf-8"))
        return str(data.get("username") or "")[:128]
    except (OSError,ValueError,TypeError,AttributeError):
        return ""


def _parse_expiry(value):
    if isinstance(value,(float,int)):
        return float(value)
    if isinstance(value,str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z","+00:00")).timestamp()
        except ValueError:
            return None
    return None


class IdentityClient:
    def __init__(self,opener=None,api_url=API_URL,client_id=CLIENT_ID):
        # Disallow arbitrary untrusted URLs for password submission.
        if api_url!=API_URL:
            raise ValueError("Endpoint PBS Central Identity tidak dikenali")
        self.url=api_url
        self.client_id=str(client_id)
        self.opener=opener or urllib.request.urlopen
        self.device_hash=_device_fingerprint()
        self.device_name=socket.gethostname()[:120]

    def _post(self,action,fields=None,timeout=TIMEOUT_SECONDS):
        payload={
            "action":action,
            "client_id":self.client_id,
            "app_version":APP_VERSION,
            "device_hash":self.device_hash,
            "device_name":self.device_name,
        }
        payload.update(fields or {})
        request=urllib.request.Request(
            self.url,data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json","Accept":"application/json",
                     "User-Agent":"PBS-NRP/"+APP_VERSION},method="POST")
        try:
            with self.opener(request,timeout=timeout) as response:
                raw=response.read(512*1024)
        except urllib.error.HTTPError as exc:
            try:
                data=json.loads(exc.read(8192).decode("utf-8","replace"))
                detail=data.get("message") or data.get("error") or str(exc.reason)
            except (ValueError,TypeError,AttributeError):
                detail=str(exc.reason)
            raise IdentityRejected("PBS ID HTTP "+str(exc.code)+": "+str(detail)[:240]) from exc
        except (urllib.error.URLError,TimeoutError,OSError) as exc:
            raise IdentityNetworkError("PBS ID tidak dapat dijangkau: "+str(exc)[:180]) from exc
        try:
            data=json.loads(raw)
        except (ValueError,TypeError):
            raise IdentityRejected("PBS ID mengembalikan respons non-JSON")
        if not isinstance(data,dict) or data.get("ok") is not True:
            reason=(data.get("message") or data.get("error") or "Login ditolak"
                    if isinstance(data,dict) else "Respons server tidak valid")
            raise IdentityRejected(str(reason)[:250])
        return data

    @staticmethod
    def _check_user(data):
        user=data.get("user")
        if not isinstance(user,dict):
            raise IdentityRejected("PBS ID tidak mengembalikan profil pengguna")
        if not str(user.get("username") or "").strip():
            raise IdentityRejected("Profil PBS ID tidak memiliki username")
        if str(user.get("status") or "ACTIVE").upper()!="ACTIVE":
            raise IdentityRejected("Akun PBS ID tidak aktif")
        if str(user.get("role") or "").upper() not in ("ADMIN","USER"):
            raise IdentityRejected("Role PBS ID tidak diizinkan")
        return user

    def login(self,username,password):
        if not username.strip() or not password:
            raise IdentityRejected("Username dan password wajib diisi")
        data=self._post("login",{"username":username.strip(),"password":password})
        user=self._check_user(data)
        token=str(data.get("token") or "")
        if not token:
            raise IdentityRejected("Token sesi tidak diberikan oleh server")
        _remember_username(username)
        result={"token":token,"user":user,"device_hash":self.device_hash,
                "verified_at":time.time(),"expires_at":_parse_expiry(data.get("expires_at"))}
        return result

    def validate(self,session):
        if not isinstance(session,dict):
            raise IdentityRejected("Session PBS ID kosong")
        if session.get("device_hash")!=self.device_hash:
            raise IdentityRejected("Perangkat ini berbeda dari perangkat login")
        token=str(session.get("token") or "")
        if not token:
            raise IdentityRejected("Token sesi kosong")
        data=self._post("session_validate",{"token":token})
        user=self._check_user(data)
        expiry=_parse_expiry(data.get("expires_at"))
        if expiry is not None and expiry <= time.time():
            raise IdentityRejected("Sesi PBS ID sudah kedaluwarsa")
        return dict(session,user=user,expires_at=expiry,verified_at=time.time())

    def logout(self,session):
        token=str((session or {}).get("token") or "")
        try:
            if token:
                self._post("logout",{"token":token},timeout=5)
        except IdentityError:
            pass
        clear_session()
