"""PBS Network Route Plan Generator v1.0.5 - OSM HTTP 500 recovery."""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from app import App, bounds
from kml_support import read_source
from osm_acquisition import fetch_osm


class NRPApp(App):
    def __init__(self, root):
        super().__init__(root)
        self.root.title("PBS Network Route Plan Generator v1.0.5")
        self._osm_loading = False
        self._revision = 0
        self._replace_labels(root)
        self.status.set("KML/KMZ siap · OSM cache + server cadangan aktif")

    def _replace_labels(self, widget):
        try:
            text = widget.cget("text")
            if isinstance(text, str):
                fixed = text.replace("v1.0.3", "v1.0.5").replace("v1.0.4", "v1.0.5")
                fixed = fixed.replace("KMZ", "KML/KMZ") if "KML/KMZ" not in fixed else fixed
                if text != fixed:
                    widget.configure(text=fixed)
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
            lines, points = read_source(path)
            self.lines, self.points = lines, points
            self.osm = None
            self._revision += 1
            self.path.set(path)
            self.stats.configure(text=(
                f"Jalur (LineString)  {len(lines):,}\n"
                f"Titik (Point)       {len(points):,}\n"
                f"Total geometri     {len(lines)+len(points):,}"))
            self.status.set(os.path.splitext(path)[1].lstrip(".").upper() + " berhasil dibaca")
            self.draw()
        except (ValueError, OSError) as exc:
            messagebox.showerror("Import gagal", str(exc))

    def load_osm(self):
        if not self.use_osm.get():
            self.status.set("Aktifkan checkbox OSM untuk mengambil data jalan dan bangunan.")
            return
        if not self.lines and not self.points:
            messagebox.showwarning("OSM", "Import file KML/KMZ terlebih dahulu")
            return
        if self._osm_loading:
            self.status.set("Proses OSM sedang berjalan, tunggu progress di bawah.")
            return
        revision = self._revision
        bb = bounds(self.lines, self.points)
        self._osm_loading = True
        self.status.set("OSM: memeriksa cache dan area tile...")

        def progress(text):
            self.root.after(0, lambda msg=text: self._progress(msg, revision))

        def worker():
            try:
                osm = fetch_osm(bb, progress=progress)
                self.root.after(0, lambda: self._ready(osm, revision))
            except Exception as exc:
                error = str(exc)
                self.root.after(0, lambda: self._failed(error, revision))
        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, text, revision):
        if revision == self._revision:
            self.status.set(text)

    def _ready(self, osm, revision):
        self._osm_loading = False
        if revision != self._revision:
            return
        self.osm_ready(osm)
        if osm.get("partial"):
            self.status.set(
                f"OSM PARSIAL: {len(osm['roads'])} jalan / {len(osm['buildings'])} bangunan, "
                f"{osm['failed_tiles']} tile gagal. Klik lagi untuk retry dari cache.")
        else:
            self.status.set(
                f"OSM berhasil: {len(osm['roads'])} jalan / {len(osm['buildings'])} bangunan, cache tersimpan.")

    def _failed(self, error, revision):
        self._osm_loading = False
        if revision != self._revision:
            return
        self.status.set("OSM gagal setelah retry: " + error[:175])
        messagebox.showwarning(
            "OSM gagal",
            "Server OSM tidak tersedia setelah mencoba beberapa server dan membagi area.\n\n"
            + error[:500] +
            "\n\nKML/KMZ tetap dapat dipreview dan PDF/DXF tetap dapat diekspor tanpa OSM.")


if __name__ == "__main__":
    root = tk.Tk()
    NRPApp(root)
    root.mainloop()
