"""PBS NRP Generator v1.0.14: optional automatic ODA integration UI.

No ODA executable, proprietary SDK or external online upload service is bundled.
The official free ODA File Converter is not a commercial license for non-members.
"""
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser

from dwg_provider import (locate_oda, recognized_oda_executable,
                          save_last_converter, converter_status,
                          ODA_DOWNLOAD_URL, ODA_LICENSE_URL,
                          winget_executable, install_by_winget)


class DWGAutoMixin:
    def initialize_dwg_support(self):
        candidate=locate_oda()
        self.converter.set(candidate or "")
        self.oda_status=tk.StringVar(value=converter_status(candidate))
        self._oda_installing=False
        self._oda_license_ack=False

    def build_dwg_controls(self,panel):
        tk.Label(panel,text="DWG Converter · Auto Detection",
                 bg="white",fg="#174a73",anchor="w",
                 font=("Segoe UI",9,"bold")).pack(fill="x",padx=12,pady=(7,2))
        tk.Label(panel,textvariable=self.oda_status,bg="white",
                 fg="#506b7f",justify="left",wraplength=250,
                 font=("Segoe UI",8)).pack(fill="x",padx=12,pady=(0,5))
        tk.Button(panel,text="Deteksi Otomatis ODA Terpasang",
                  command=self.detect_dwg_converter).pack(fill="x",padx=12,pady=(0,3))
        tk.Button(panel,text="Instalasi Resmi via Windows Package Manager",
                  command=self.install_oda_interactive).pack(fill="x",padx=12,pady=3)
        tk.Button(panel,text="Situs Resmi ODA / Lisensi",
                  command=self.open_oda_website).pack(fill="x",padx=12,pady=3)
        tk.Button(panel,text="Pilih EXE ODA alternatif (opsional)",
                  command=self.pick_oda).pack(fill="x",padx=12,pady=3)
        tk.Label(panel,text="Unduhan gratis ODA bagi non-anggota hanya untuk "
                 "nonkomersial. Komersial membutuhkan hak penggunaan yang sesuai.",
                 bg="white",fg="#7c5324",wraplength=250,justify="left",
                 font=("Segoe UI",8)).pack(fill="x",padx=12,pady=(4,5))
        tk.Checkbutton(panel,text="Buat DWG jika converter tersedia",
                       variable=self.want_dwg,bg="white").pack(anchor="w",padx=8)

    def detect_dwg_converter(self):
        candidate=locate_oda(preferred=self.converter.get())
        self.converter.set(candidate or "")
        self.oda_status.set(converter_status(candidate))
        if candidate:
            try:
                save_last_converter(candidate)
            except OSError:
                pass
            self.status.set("ODA terdeteksi otomatis. Periksa hak penggunaan komersial sebelum ekspor DWG.")
        else:
            self.status.set("ODA belum ditemukan. PDF dan DXF tetap tersedia.")

    def pick_oda(self):
        path=filedialog.askopenfilename(
            title="Pilih ODAFileConverter.exe dari pemasangan resmi",
            filetypes=[("ODA File Converter","ODAFileConverter.exe"),
                       ("Executable Windows","*.exe")])
        if not path:
            return
        if not recognized_oda_executable(path):
            messagebox.showerror("Converter tidak sesuai",
                "Pilih ODAFileConverter.exe dari pemasangan resmi.")
            return
        self.converter.set(path)
        self.oda_status.set(converter_status(path))
        try:
            save_last_converter(path)
            self.status.set("Lokasi ODA disimpan untuk penggunaan berikutnya.")
        except OSError as error:
            self.status.set("ODA ditemukan tetapi lokasi gagal disimpan: "+str(error)[:110])

    def open_oda_website(self):
        webbrowser.open(ODA_DOWNLOAD_URL)

    def install_oda_interactive(self):
        """Only user-click can trigger installation. No silent downloads."""
        if getattr(self,"_running",False) or getattr(self,"_osm_loading",False):
            messagebox.showwarning("Akuisisi berjalan",
                "Selesaikan akuisisi Google/OSM sebelum memasang converter.")
            return
        if self._oda_installing:
            return
        if not winget_executable():
            messagebox.showinfo("winget tidak tersedia",
                "Windows Package Manager tidak tersedia. Saya akan membuka "
                "situs resmi ODA. Hak penggunaan tetap harus dipastikan.")
            self.open_oda_website()
            return
        approved=messagebox.askyesno("Persetujuan pemasangan ODA",
            "Windows Package Manager akan memasang ODA File Converter dari sumber resminya. "
            "Pemasangan mungkin meminta persetujuan Windows/UAC.\n\n"
            "Unduhan ODA gratis untuk non-anggota hanya boleh dipakai nonkomersial. "
            "Untuk proyek PBS, pastikan hak penggunaan komersial telah diperoleh.\n\n"
            "Lanjutkan pemasangan?")
        if not approved:
            return
        self._oda_installing=True
        self.oda_status.set("Pemasangan ODA melalui winget sedang berjalan...")
        def worker():
            candidate=None
            error=None
            try:
                candidate=install_by_winget()
            except Exception as exc:
                error=str(exc)
            try:
                self.root.after(0,lambda:self._oda_install_done(candidate,error))
            except RuntimeError:
                pass
        threading.Thread(target=worker,daemon=True).start()

    def _oda_install_done(self,candidate,error):
        self._oda_installing=False
        if error:
            self.oda_status.set("Pemasangan belum selesai · "+error[:125])
            messagebox.showwarning("ODA belum siap",
                error[:430]+"\n\nAnda dapat menggunakan unduhan resmi.")
            return
        self.detect_dwg_converter()
        if not self.converter.get():
            messagebox.showwarning("Converter tidak ditemukan",
                "Installer selesai tetapi ODAFileConverter.exe belum ditemukan "
                "di lokasi Windows standar. Gunakan Pilih EXE alternatif sekali.")
        else:
            messagebox.showinfo("ODA terdeteksi",
                "Converter telah ditemukan otomatis. Penggunaan komersial "
                "tetap mensyaratkan hak penggunaan yang sesuai.")

    def dwg_preflight(self):
        """Returns (proceed, restore_original_dwg_checkbox)."""
        if not self.want_dwg.get():
            return True,False
        if not recognized_oda_executable(self.converter.get()):
            self.detect_dwg_converter()
        if not recognized_oda_executable(self.converter.get()):
            if not messagebox.askyesno("ODA belum tersedia",
                "ODA File Converter belum ditemukan. PDF dan DXF tetap dapat dibuat.\n\n"
                "Lanjut ekspor PDF + DXF saja?"):
                return False,False
            self.want_dwg.set(False)
            return True,True
        if not self._oda_license_ack:
            permitted=messagebox.askyesno("Hak penggunaan ODA",
                "ODA File Converter gratis dibatasi nonkomersial bagi non-anggota.\n"
                "Untuk pekerjaan PBS komersial, hak penggunaan harus sesuai.\n\n"
                "Apakah Anda sudah memiliki hak penggunaan untuk menghasilkan DWG proyek ini?")
            if permitted:
                self._oda_license_ack=True
            else:
                if not messagebox.askyesno("Ekspor tanpa DWG",
                    "Lanjut membuat PDF dan DXF saja?"):
                    return False,False
                self.want_dwg.set(False)
                return True,True
        return True,False
