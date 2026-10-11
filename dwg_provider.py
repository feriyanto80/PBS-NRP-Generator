"""ODA File Converter discovery/installation helpers for PBS NRP v1.0.14.

NO ODA executable, SDK, or untrusted online conversion service is bundled.
ODA's free sample is restricted to non-commercial use by non-members.
Commercial projects must obtain appropriate rights separately.

GitHub/Microsoft winget entry installs from an ODA-hosted MSI; requires an
explicit opt-in user action and may trigger operating system approval.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile

ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"
ODA_LICENSE_URL = "https://www.opendesign.com/faq/question/what-are-oda-viewer-and-oda-file-converter"
WINGET_PACKAGE_ID = "ODA.ODAFileConverter"
EXECUTABLE_NAME = "ODAFileConverter.exe"


def settings_location(env=None):
    env = env if env is not None else os.environ
    base = env.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".pbs_nrp")
    return os.path.join(base, "PBS_NRP_Generator", "dwg_provider.json")


def recognized_oda_executable(path):
    """Only vendor-named executables accepted by this integration."""
    if not path:
        return False
    path = os.path.normpath(os.path.abspath(os.fspath(path)))
    return (os.path.basename(path).casefold() == EXECUTABLE_NAME.casefold()
            and os.path.isfile(path))


def load_last_converter(config_path=None):
    path=config_path or settings_location()
    try:
        with open(path, encoding="utf-8") as reader:
            saved = json.load(reader)
        candidate = saved.get("oda_path", "")
        return candidate if recognized_oda_executable(candidate) else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def save_last_converter(path, config_path=None):
    """Persist only a local path; no credentials, SDK, or converter binary."""
    if not recognized_oda_executable(path):
        raise ValueError("Harus memilih ODAFileConverter.exe yang telah terpasang")
    config_path = config_path or settings_location()
    folder = os.path.dirname(config_path)
    os.makedirs(folder, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".dwg_", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump({"oda_path": os.path.abspath(path)}, out)
        os.replace(temp, config_path)
    finally:
        if os.path.isfile(temp):
            os.remove(temp)
    return os.path.abspath(path)


def _registry_locations():
    """Read registered ODA installations, when winreg exists."""
    try:
        import winreg
    except ImportError:
        return
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ):
            try:
                handle = winreg.OpenKey(root, subkey)
            except OSError:
                continue
            with handle:
                try:
                    total = winreg.QueryInfoKey(handle)[0]
                except OSError:
                    continue
                for i in range(total):
                    try:
                        child = winreg.OpenKey(handle, winreg.EnumKey(handle, i))
                        with child:
                            name = str(winreg.QueryValueEx(child, "DisplayName")[0]).lower()
                            if "oda" not in name or "file converter" not in name:
                                continue
                            installed = winreg.QueryValueEx(child, "InstallLocation")[0]
                            if installed:
                                yield os.path.join(str(installed), EXECUTABLE_NAME)
                    except OSError:
                        continue


def locate_oda(preferred=None, config_path=None, env=None, roots=None,
               scan_registry=True):
    """Try saved selection, limited vendor paths, PATH and installation registry."""
    env = env if env is not None else os.environ
    probes = []
    if preferred:
        probes.append(preferred)
    if config_path is not False:
        saved = load_last_converter(config_path)
        if saved:
            probes.append(saved)
    which = shutil.which(EXECUTABLE_NAME, path=env.get("PATH"))
    if which:
        probes.append(which)
    vendor_roots = list(roots) if roots is not None else [
        env.get("ProgramFiles", r"C:\Program Files"),
        env.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        env.get("LOCALAPPDATA", ""),
    ]
    for root in vendor_roots:
        if not root:
            continue
        probes.append(os.path.join(root, "ODA", "ODAFileConverter", EXECUTABLE_NAME))
        probes.extend(glob.glob(os.path.join(root, "ODA", "ODAFileConverter *", EXECUTABLE_NAME)))
        probes.extend(glob.glob(os.path.join(root, "ODAFileConverter*", EXECUTABLE_NAME)))
    if scan_registry:
        probes.extend(_registry_locations())
    seen = set()
    for candidate in probes:
        if not candidate:
            continue
        candidate = os.path.normpath(os.path.abspath(os.path.expandvars(str(candidate))))
        key = os.path.normcase(candidate)
        if key in seen:
            continue
        seen.add(key)
        if recognized_oda_executable(candidate):
            return candidate
    return None


def winget_executable():
    return shutil.which("winget.exe") or shutil.which("winget")


def winget_command(executable=None):
    """Use the published package ID, not an unverified installer binary."""
    winget = executable or winget_executable()
    if not winget:
        raise RuntimeError("Windows Package Manager (winget) tidak tersedia")
    return [
        winget, "install", "--id", WINGET_PACKAGE_ID,
        "--exact", "--source", "winget", "--interactive",
    ]


def install_by_winget(timeout=900, runner=None):
    """Run only following explicit user consent in the desktop UI."""
    runner = runner or subprocess.run
    cmd = winget_command()
    result = runner(cmd, capture_output=True, text=True, timeout=timeout,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        detail = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()[-650:]
        raise RuntimeError("Pemasangan resmi ODA gagal: " + detail)
    return locate_oda()


def converter_status(path):
    if recognized_oda_executable(path):
        return "TERDETEKSI · " + path
    return "BELUM ADA · PDF/DXF tetap bisa dibuat tanpa converter"
