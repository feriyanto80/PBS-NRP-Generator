"""Thread-safe PDF + DXF + optional DWG export job.

NO Tkinter API is used here. All rendering/conversion work runs in a worker
thread; progress events are forwarded by a Queue to Tk main-loop.
Cumulative from working PBS NRP v1.0.22.6; preserves original output naming,
CAD reference sheet layout, and ODA Invalid-RegApp recovery.
"""
import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.pagesizes import A3, landscape


@dataclass
class ExportResult:
    output_dir: str
    pdf: str = ""
    dxf: str = ""
    dwg: str = ""
    warning: str = ""
    log: str = ""
    files: list = field(default_factory=list)


def output_names(folder,title):
    stem="PBS_NRP_"+''.join(char if char.isalnum() else '_' for char in title)[:65]
    return (os.path.join(folder,stem+".pdf"),
            os.path.join(folder,stem+".dxf"),
            os.path.join(folder,stem+".dwg"),
            os.path.join(folder,stem+"_EXPORT_ERROR.log"))


def export_job(folder,title,lines,points,sheets,osm,want_dwg,converter,emit,
               pdf_renderer=None,dxf_renderer=None,dwg_converter=None):
    """Export using a worker-only callback emit(percent,stage,detail).

    The renderer callbacks communicate per-page and per-layout progress.
    Temporary names protect previously completed PDF/DXF against half-files.
    A failed DWG does not invalidate successfully generated PDF and DXF.
    """
    from engineering_render import draw_pdf,draw_dxf
    from dwg_conversion import convert_dwg
    pdf_renderer=pdf_renderer or draw_pdf
    dxf_renderer=dxf_renderer or draw_dxf
    dwg_converter=dwg_converter or convert_dwg
    target_pdf,target_dxf,target_dwg,log_path=output_names(folder,title)
    result=ExportResult(output_dir=folder,log=log_path)
    stage_pdf=target_pdf[:-4]+".exporting.pdf"
    stage_dxf=target_dxf[:-4]+".exporting.dxf"
    phase="Persiapan"
    os.makedirs(folder,exist_ok=True)
    for temporary in (stage_pdf,stage_dxf):
        if os.path.isfile(temporary):
            os.remove(temporary)
    try:
        emit(3,"Persiapan",f"{len(sheets)} sheet, {len(lines)} jalur, "
             f"{len(points)} titik, {len((osm or {}).get('buildings',[])):,} footprint")
        phase="PDF"
        emit(7,"PDF","Mulai rendering A3")
        def pdf_report(index,total,caption):
            emit(7+47*index/max(total,1),"PDF",
                 f"Halaman {index}/{total} — {caption}")
        pdf_renderer(stage_pdf,lines,points,None,*landscape(A3),
                     title,sheets,osm,progress=pdf_report)
        if not os.path.isfile(stage_pdf) or os.path.getsize(stage_pdf)<800:
            raise RuntimeError("PDF kosong atau belum selesai disimpan")
        os.replace(stage_pdf,target_pdf)
        result.pdf=target_pdf
        result.files.append(target_pdf)
        emit(55,"PDF",f"Selesai: {Path(target_pdf).name} "
             f"({os.path.getsize(target_pdf)/1024**2:.1f} MB)")

        phase="DXF"
        emit(58,"DXF","Menyusun geometri dan simbol CAD")
        def dxf_report(fraction,caption):
            emit(58+30*max(0.0,min(1.0,float(fraction))),"DXF",caption)
        dxf_renderer(stage_dxf,lines,points,sheets,osm,progress=dxf_report)
        if not os.path.isfile(stage_dxf) or os.path.getsize(stage_dxf)<800:
            raise RuntimeError("DXF kosong atau belum selesai disimpan")
        os.replace(stage_dxf,target_dxf)
        result.dxf=target_dxf
        result.files.append(target_dxf)
        emit(89,"DXF",f"Selesai: {Path(target_dxf).name} "
             f"({os.path.getsize(target_dxf)/1024**2:.1f} MB)")

        if want_dwg:
            phase="DWG"
            emit(91,"ODA → DWG","Mengonversi DXF ke AutoCAD 2018; menunggu ODA")
            try:
                converted=dwg_converter(target_dxf,converter)
                # The legacy callable sometimes returns None but creates DWG.
                destination=os.fspath(converted) if converted else target_dwg
                if not os.path.isfile(destination) or os.path.getsize(destination)<1024:
                    raise RuntimeError("ODA selesai tetapi DWG valid tidak ditemukan")
                result.dwg=destination
                result.files.append(destination)
                emit(98,"DWG",f"Selesai: {Path(destination).name}")
            except Exception as error:
                result.warning="DWG belum berhasil: "+str(error)
                emit(98,"DWG · PERINGATAN",result.warning)
        else:
            emit(98,"DWG","Tidak dipilih — selesai dengan PDF dan DXF.")
        emit(100,"Selesai" if not result.warning else "Selesai dengan peringatan",
             f"{len(result.files)} berkas berhasil dibuat.")
        return result
    except BaseException as error:
        # Preserve a real traceback even for windowed (--windowed) EXE.
        detail=f"Tahap: {phase}\nFolder: {folder}\n\n"+traceback.format_exc()
        try:
            Path(log_path).write_text(detail,encoding="utf-8")
        except OSError:
            pass
        raise RuntimeError(f"Ekspor {phase} gagal: {error}\nLog: {log_path}") from error
    finally:
        for temporary in (stage_pdf,stage_dxf):
            try:
                if os.path.isfile(temporary):
                    os.remove(temporary)
            except OSError:
                pass
