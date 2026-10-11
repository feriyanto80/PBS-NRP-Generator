"""ODA 27.9-compatible DXF to DWG conversion with accountable verification.

Preserve source DXF, sanitize a temporary working copy, try documented input
filter variants, then run a tiny independent DWG conversion probe if all fail.
The probe helps distinguish ODA CLI/filter failure from malformed source CAD.
No ODA binaries or restricted SDKs are distributed in this release.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dwg_provider import recognized_oda_executable

_DWG_HEADER=b"AC1032"
_ODAFILTERS=((True,"*.dxf","1"),
             (True,"*.dxf","0"),
             (True,"*.DXF","0"),
             (False,None,"0"),
             (True,"*.DWG;*.DXF","0"))


def _dwg_files(directory):
    return [p for p in Path(directory).rglob("*")
            if p.is_file() and p.suffix.lower()==".dwg"]


def _valid_dwg(path):
    try:
        with open(path,"rb") as reader:
            header=reader.read(6)
        return header==_DWG_HEADER and os.path.getsize(path)>=1024
    except OSError:
        return False


def _write_failure_log(path,records):
    output=Path(path).with_name(Path(path).stem+"_ODA_Conversion.log")
    try:
        output.write_text("\n".join(records)+"\n",encoding="utf-8")
        return str(output)
    except OSError:
        return "(log tidak dapat disimpan)"


def _sanitize_dxf(source,dest,log):
    """Clean invalid DXF references without changing the exported original."""
    shutil.copy2(source,dest)
    try:
        import ezdxf
        doc=ezdxf.readfile(str(dest))
        auditor=doc.audit()
        log.append(f"Source DXF: {source.stat().st_size} bytes, {doc.dxfversion}")
        log.append(f"DXF auditor: {len(auditor.errors)} errors, "
                   f"{len(auditor.fixes)} fixes")
        for item in auditor.fixes[:15]:
            log.append(f"  DXF fix {item.code}: {item.message}")
        if auditor.errors:
            for item in auditor.errors[:10]:
                log.append(f"  DXF error {item.code}: {item.message}")
            # Keep a copy of the source for ODA to inspect even if repair
            # cannot be completed. Do not overwrite the original PDF/DXF.
            return
        if auditor.fixes:
            doc.saveas(str(dest))
        log.append("Staged DXF: "+str(dest.stat().st_size)+" bytes")
    except Exception as error:
        log.append("DXF preflight skipped (original staged): "+repr(error))


def _launch(command,log,stage,timeout=120):
    log.append("Command: "+subprocess.list2cmdline(command))
    try:
        result=subprocess.run(command,capture_output=True,text=True,
                              encoding="utf-8",errors="replace",
                              timeout=timeout)
        log.append("Exit code: "+str(result.returncode))
        log.append("stdout: "+(result.stdout or "")[-2000:])
        log.append("stderr: "+(result.stderr or "")[-2000:])
    except subprocess.TimeoutExpired:
        log.append(f"TIMEOUT: no completion in {timeout} seconds")
        return None
    except OSError as error:
        log.append("ODA execution error: "+repr(error))
        return None
    results=_dwg_files(stage)
    log.append("DWG discovered: "+str(len(results)))
    for p in results[:12]:
        log.append(f"  {p}: size={p.stat().st_size} "
                   f"header={p.read_bytes()[:6]!r}")
    return results


def _find_valid_in(*folders):
    for path in folders:
        for p in _dwg_files(path):
            if _valid_dwg(p):
                return p
    return None


def _oda_probe(exe,workspace,log):
    """Test installed ODA with a tiny, valid R2018 DXF control drawing.

    A failed probe means we cannot blame real project CAD; the converter may
    be ignoring CLI/filter flags or not writing to the expected directory.
    """
    inp=workspace/"probe_input"
    out=workspace/"probe_output"
    inp.mkdir()
    out.mkdir()
    try:
        import ezdxf
        control=ezdxf.new("R2018")
        control.modelspace().add_circle((100,100),3)
        control.saveas(str(inp/"ODA_PROBE.DXF"))
    except Exception as error:
        log.append("Probe cannot be constructed: "+repr(error))
        return "unavailable"
    log.append("Control DXF exists: "+str((inp/"ODA_PROBE.DXF").stat().st_size))
    for form in (False,True):
        args=[exe,str(inp),str(out),"ACAD2018","DWG","0","0"]
        if form:
            args.append("*.DWG;*.DXF")
        _launch(args,log,out,timeout=75)
        if _find_valid_in(out,inp):
            log.append("CONTROL PROBE: SUCCESS. ODA CLI handles simple DXF; "
                       "real project drawing may be incompatible.")
            return "success"
    log.append("CONTROL PROBE: FAILED. ODA did not convert even a minimal "
               "valid DXF through the tested CLI invocations.")
    return "failed"


def convert_dwg(dxf_path,converter):
    source=Path(dxf_path).resolve()
    if not source.is_file() or source.suffix.lower()!=".dxf":
        raise ValueError("File sumber DXF tidak ditemukan")
    if not recognized_oda_executable(converter):
        raise RuntimeError("ODAFileConverter.exe belum dipilih atau tidak tersedia")

    exe=str(Path(converter).resolve())
    target=source.with_suffix(".dwg")
    log=[
        "PBS NRP Generator · ODA Converter Diagnostic v1.0.22.3",
        f"DXF sumber: {source.name}",f"ODA: {exe}",
        f"File tujuan: {target}","Target: DWG AutoCAD 2018 (AC1032)",
        "Note: exit code 0 does NOT guarantee a converted DWG.",
    ]

    try:
        with tempfile.TemporaryDirectory(prefix="PBS_NRP_ODA_") as temp:
            work=Path(temp)
            inp=work/"input"
            out=work/"output"
            inp.mkdir()
            out.mkdir()
            staged=inp/"PBS_NRP_CONVERT.dxf"
            _sanitize_dxf(source,staged,log)
            log.append("Input listing: "+", ".join(p.name for p in inp.iterdir()))
            for iteration,(has_filter,filter_value,audit) in enumerate(_ODAFILTERS,1):
                cmd=[exe,str(inp),str(out),"ACAD2018","DWG","0",audit]
                if has_filter:
                    cmd.append(filter_value)
                log.append(f"Attempt {iteration}/{len(_ODAFILTERS)}: "
                           f"filter={filter_value or '[ODA default]'} audit={audit}")
                _launch(cmd,log,out)
                result=_find_valid_in(out,inp)
                if result is not None:
                    shutil.copy2(result,target)
                    if _valid_dwg(target):
                        return str(target)
                    log.append("Copied DWG did not pass AC1032 verification.")
            probe=_oda_probe(exe,work,log)
    except (OSError,ValueError) as error:
        log.append("Filesystem error: "+repr(error))
        probe="unavailable"

    diagnostic=_write_failure_log(source,log)
    advice=("Konversi CLI gagal bahkan untuk file DXF uji sederhana. "
            if probe=="failed" else
            "ODA berhasil membaca file DXF uji tetapi tidak membuat DWG "
            "untuk gambar jaringan ini. " if probe=="success" else
            "Penyebab belum dapat ditentukan. ")
    raise RuntimeError(
        advice+"Lihat log lengkap: "+diagnostic+
        ". Untuk memastikan, uji satu file DXF hasil PBS di GUI ODA "
        "dengan folder input dan output berbeda.")
