"""Reliable ODA File Converter CLI for PBS NRP CAD export.

The underlying v1.0.3 app calls app.convert_dwg from its inherited export.
This module is injected by launcher.py to replace its fragile six-argument
converter. No proprietary ODA executable, binaries, licenses or SDK are bundled.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dwg_provider import recognized_oda_executable


def _dwg_files(directory):
    """Include uppercase .DWG and ODA-version-dependent nested output paths."""
    return [p for p in Path(directory).rglob("*")
            if p.is_file() and p.suffix.lower() == ".dwg"]


def _valid_dwg(path):
    try:
        with open(path, "rb") as file:
            header=file.read(6)
        # AutoCAD 2018 native binary header is AC1032. An empty or
        # invalid file must never be reported as successful DWG export.
        return header == b"AC1032" and os.path.getsize(path) >= 1024
    except OSError:
        return False


def _write_failure_log(path, records):
    path=Path(path)
    log=path.with_name(path.stem + "_ODA_Conversion.log")
    try:
        log.write_text("\n".join(records), encoding="utf-8")
        return str(log)
    except OSError:
        return "(log tidak dapat disimpan)"


def convert_dwg(dxf_path, converter):
    """Convert an existing DXF to DWG 2018 and validate its binary header.

    ODA command shape: exe inputdir outputdir ACAD2018 DWG recursive audit
    input-filter. Older app omitted the input-filter, then assumed one flat
    output name; ODA may return only a directory string as console output.
    """
    source=Path(dxf_path).resolve()
    if not source.is_file() or source.suffix.lower()!=".dxf":
        raise ValueError("File DXF sumber tidak ditemukan atau bukan .dxf")
    if not recognized_oda_executable(converter):
        raise RuntimeError("ODAFileConverter.exe belum dipilih/terdeteksi.")
    exe=str(Path(converter).resolve())
    target=source.with_suffix(".dwg")
    diagnostic=[f"DXF sumber: {source.name}",f"ODA: {exe}",
                "Target: DWG AutoCAD 2018",f"File tujuan: {target}"]
    try:
        with tempfile.TemporaryDirectory(prefix="PBS_NRP_ODA_") as workspace:
            root=Path(workspace)
            folder_in=root/"input"
            folder_out=root/"output"
            folder_in.mkdir()
            folder_out.mkdir()
            # Stable ASCII filename avoids Unicode/long-path input trouble
            # in older ODA executables. Original name restored on success.
            temp_name="PBS_NRP_CONVERT.dxf"
            shutil.copy2(source,folder_in/temp_name)
            attempts=[]
            for audit in ("1","0"):
                command=[exe,str(folder_in),str(folder_out),
                         "ACAD2018","DWG","0",audit,"*.dxf"]
                diagnostic.append(f"CLI filter=*.dxf, recursive=0, audit={audit}")
                try:
                    run=subprocess.run(command,capture_output=True,
                                       text=True,encoding="utf-8",
                                       errors="replace",timeout=300)
                except subprocess.TimeoutExpired:
                    diagnostic.append("Timeout 300 detik, ODA mungkin menunggu dialog.")
                    break
                except OSError as exc:
                    diagnostic.append(f"ODA gagal dijalankan: {exc}")
                    break
                diagnostic.append(f"Exit code: {run.returncode}")
                diagnostic.append("stdout: "+(run.stdout or "")[-2000:])
                diagnostic.append("stderr: "+(run.stderr or "")[-2000:])
                attempts.append(audit)
                files=_dwg_files(folder_out)
                candidates=sorted(files,
                                  key=lambda p:(p.stem.lower() !=
                                      Path(temp_name).stem.lower(),-p.stat().st_size))
                valid=next((p for p in candidates if _valid_dwg(p)),None)
                if valid is not None:
                    shutil.copy2(valid,target)
                    if _valid_dwg(target):
                        return str(target)
                    diagnostic.append("DWG gagal disalin/divalidasi ke tujuan")
                    break
                diagnostic.append(
                    "Tidak ada DWG AC1032 valid; output="+
                    ", ".join(p.name for p in candidates[:12]))
                # Some ODA revisions cannot audit input with nested
                # objects; retry once without the repair pass.
            # Temporary output files are gone after return; diagnostic log
            # persisted beside DXF for reproducibility.
    except (OSError,ValueError) as exc:
        diagnostic.append(f"Kesalahan I/O: {exc}")
    logfile=_write_failure_log(source,diagnostic)
    raise RuntimeError(
        "ODA terpasang tetapi tidak menghasilkan DWG AutoCAD 2018 yang valid. "
        f"Log pemeriksaan: {logfile}. "
        "Buka DXF dengan ODA File Converter secara manual untuk "
        "memastikan DXF dapat dibaca oleh versi ODA terpasang.")
