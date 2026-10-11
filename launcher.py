"""PBS NRP Generator v1.0.6: engineer-style drawings and OSM export guard."""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import app
from app import App, bounds
from kml_support import read_source
from osm_acquisition import fetch_osm
import engineering_render as engineering

# All PDF/DXF exports go through the engineering-style renderer.
app.draw_pdf = engineering.draw_pdf
app.draw_dxf = engineering.draw_dxf


class NRPApp(App):
    def __init__(self, root):
        super().__init__(root)
        self.root.title("PBS Network Route Plan Generator v1.0.6")
        self._osm_loading = False
        self._revision = 0
        self._replace_labels(root)
        self.status.set("KML/KMZ siap · ambil OSM untuk road edges & building footprint")

    def _replace_labels(self, widget):
        try:
            label=widget.cget("text")
            if isinstance(label, str):
                label=label.replace("v1.0.3","v1.0.6").replace("v1.0.4","v1.0.6").replace("v1.0.5","v1.0.6")
                if label != widget.cget("text"):
                    widget.configure(text=label)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._replace_labels(child)

    def open_kmz(self):
        path = filedialog.askopenfilename(
            title="Import Google Earth KML atau KMZ",
            filetypes=[("Google Earth KML/KMZ", "*.kml *.kmz"),
                       ("KML", "*.kml"), ("KMZ", "*.kmz")])
        if not path:
            return
        try:
            lines,points = read_source(path)
            self.lines,self.points = lines,points
            self.osm = None
            self._revision += 1
            self.path.set(path)
            self.stats.configure(text=(
                f"Jalur (LineString)  {len(lines):,}\n"
                f"Titik (Point)       {len(points):,}\n"
                f"Total geometri     {len(lines)+len(points):,}"))
            self.status.set("Data berhasil dibaca. Klik Ambil / gunakan cache OSM sebelum Export PDF.")
            self.draw()
        except (OSError,ValueError) as exc:
            messagebox.showerror("Import gagal",str(exc))

    def load_osm(self):
        if not self.use_osm.get():
            self.status.set("Aktifkan checkbox OSM sebelum mengambil data.")
            return
        if not self.lines and not self.points:
            messagebox.showwarning("OSM","Import KML/KMZ terlebih dahulu")
            return
        if self._osm_loading:
            self.status.set("OSM masih diproses, tunggu progres unduh.")
            return
        revision=self._revision
        bb=bounds(self.lines,self.points)
        self._osm_loading=True
        self.status.set("OSM: mengambil data jalan dan footprint bangunan...")

        def progress(text):
            self.root.after(0,lambda msg=text:self._progress(msg,revision))

        def worker():
            try:
                osm=fetch_osm(bb,progress=progress)
                self.root.after(0,lambda:self._ready(osm,revision))
            except Exception as exc:
                error=str(exc)
                self.root.after(0,lambda:self._failed(error,revision))
        threading.Thread(target=worker,daemon=True).start()

    def _progress(self,text,revision):
        if revision==self._revision:
            self.status.set(text)

    def _ready(self,osm,revision):
        self._osm_loading=False
        if revision!=self._revision:
            return
        self.osm_ready(osm)
        roads=len(osm.get("roads",[]))
        buildings=len(osm.get("buildings",[]))
        if osm.get("partial"):
            self.status.set(
                f"OSM PARSIAL: {roads} jalan / {buildings} bangunan; "
                f"{osm.get('failed_tiles',0)} tile gagal. Coba tombol OSM kembali.")
        else:
            self.status.set(
                f"OSM siap: {roads} jalan offset + {buildings} footprint bangunan. "
                "PDF & DXF engineering siap diekspor.")

    def _failed(self,error,revision):
        self._osm_loading=False
        if revision!=self._revision:
            return
        self.status.set("OSM gagal: "+error[:180])
        messagebox.showwarning(
            "OSM belum siap",
            "Akuisisi jalan/footprint OSM gagal setelah fallback.\n\n"+error[:500]+
            "\n\nExport tanpa OSM hanya tersedia dengan konfirmasi eksplisit.")

    def draw_on(self,canvas,bb):
        engineering.draw_preview(
            canvas,bb,self.lines,self.points,
            self.osm if self.use_osm.get() else None,
            canvas is self.map)

    def export(self):
        if not self.lines and not self.points:
            messagebox.showwarning("Data belum ada","Import file KML/KMZ terlebih dahulu.")
            return
        if self.use_osm.get():
            if self._osm_loading:
                messagebox.showwarning(
                    "OSM sedang berjalan",
                    "Pengambilan OSM belum selesai. Tunggu atau nonaktifkan OSM secara sadar sebelum ekspor.")
                return
            if self.osm is None:
                if not messagebox.askyesno(
                    "OSM belum tersedia",
                    "Jalan offset dan footprint bangunan BELUM ada.\n"
                    "PDF akan berbeda dari contoh drafter.\n\n"
                    "Tetap ekspor PDF/DXF TANPA OSM?"):
                    return
            elif self.osm.get("partial") or not self.osm.get("roads") or not self.osm.get("buildings"):
                if not messagebox.askyesno(
                    "OSM belum lengkap",
                    f"OSM jalan: {len(self.osm.get('roads',[]))}; "
                    f"bangunan: {len(self.osm.get('buildings',[]))}; "
                    f"data parsial: {bool(self.osm.get('partial'))}.\n"
                    "PDF bisa tidak memuat seluruh detail jalan/bangunan.\n\n"
                    "Tetap ekspor?"):
                    return
        super().export()


if __name__=="__main__":
    root=tk.Tk()
    NRPApp(root)
    root.mainloop()
