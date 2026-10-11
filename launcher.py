"""PBS Network Route Plan Generator v1.0.7 — Multi-source building footprints."""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import app
from app import App, bounds
from kml_support import read_source
from osm_acquisition import fetch_osm
from building_sources import load_polygons, merge_sources
import engineering_render as engineering
import drafter_titleblock as drafter

# Keep cumulative double-road-line PDF/DXF renderers while replacing titleblock.
engineering._draw_titleblock = drafter.draw_titleblock
app.draw_pdf = engineering.draw_pdf
app.draw_dxf = engineering.draw_dxf


class NRPApp(App):
    def __init__(self, root):
        self._input_polygons = []
        self._google_polygons = []
        self._raw_osm = None
        self._revision = 0
        self._osm_loading = False
        self._footprint_loading = False
        super().__init__(root)
        self.root.title("PBS Network Route Plan Generator v1.0.7")
        self._rename_labels(root)
        self._insert_source_controls()
        self.status.set("KML/KMZ, OSM dan footprint tambahan siap · v1.0.7")

    def _rename_labels(self,widget):
        try:
            current=widget.cget("text")
            if isinstance(current,str):
                adjusted=current.replace("v1.0.3","v1.0.7").replace("v1.0.4","v1.0.7").replace("v1.0.5","v1.0.7").replace("v1.0.6","v1.0.7")
                if "KML/KMZ" not in adjusted:
                    adjusted=adjusted.replace("Import KMZ","Import KML/KMZ").replace("Pilih file KMZ","Pilih file KML/KMZ").replace("geometri KMZ","geometri KML/KMZ")
                if adjusted != current:
                    widget.configure(text=adjusted)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._rename_labels(child)

    def _insert_source_controls(self):
        parent=self.stats.master
        before=None
        for child in parent.winfo_children():
            try:
                if "Pemetaan & Simbol" in child.cget("text"):
                    before=child
                    break
            except tk.TclError:
                pass
        self.extra_counts=tk.StringVar(value="Footprint: OSM 0 | KML 0 | Google 0")
        options={"before":before} if before is not None else {}
        tk.Label(parent,text="Pelengkap Bangunan · OSM + KML + Google",
                 font=("Segoe UI",9,"bold"),bg="#e7edf5",
                 fg="#173957",anchor="w",padx=10).pack(fill="x",**options)
        tk.Button(parent,text="Import Google Buildings / GeoJSON / KML / CSV",
                  command=self.import_buildings).pack(fill="x",padx=12,pady=3,**options)
        tk.Label(parent,textvariable=self.extra_counts,
                 bg="white",fg="#52616c",
                 font=("Segoe UI",8),wraplength=278,
                 justify="left").pack(fill="x",padx=12,**options)
        tk.Label(parent,text="Google: file ekspor Open Buildings (WKT/GeoJSON),\n"
                  "confidence >= 0.70, deduplikasi otomatis.",
                 bg="white",fg="#666666",
                 justify="left",font=("Segoe UI",8)).pack(fill="x",padx=12,pady=(0,2),**options)

    def open_kmz(self):
        path=filedialog.askopenfilename(
            title="Pilih jaringan KML / KMZ",
            filetypes=[("Google Earth KML / KMZ","*.kml *.kmz"),
                       ("KML","*.kml"),("KMZ","*.kmz")])
        if not path:
            return
        try:
            lines,points=read_source(path)
            bb=bounds(lines,points)
            kml=load_polygons(path,bbox=bb)
            self.lines,self.points=lines,points
            self._input_polygons=kml["polygons"]
            self._raw_osm=None
            self._google_polygons=[]
            self._revision+=1
            self.path.set(path)
            self.stats.config(text=(
                f"Jalur (LineString)  {len(lines):,}\n"
                f"Titik (Point)       {len(points):,}\n"
                f"Poligon KML        {len(self._input_polygons):,}\n"
                f"Total jaringan     {len(lines)+len(points):,}"))
            self._apply_sources()
            if not self._input_polygons:
                self.status.set("KML/KMZ berisi 0 footprint poligon; ambil OSM / import Google Open Buildings.")
            else:
                self.status.set(f"Berhasil: {len(self._input_polygons)} polygon jaringan telah terbaca.")
        except Exception as exc:
            messagebox.showerror("Import jaringan gagal",str(exc))

    def import_buildings(self):
        if not self.lines and not self.points:
            messagebox.showwarning("Import jaringan dahulu",
                "Pilih jaringan KML/KMZ sebelum mengimpor footprint tambahan.")
            return
        if self._footprint_loading:
            return
        path=filedialog.askopenfilename(title="Import Google Open Buildings / footprint pelengkap",
           filetypes=[("GeoJSON / KML / KMZ / CSV","*.geojson *.json *.kml *.kmz *.csv *.gz"),
                      ("GeoJSON","*.geojson *.json"),("Google Open Buildings CSV","*.csv *.gz"),
                      ("Google Earth","*.kml *.kmz")])
        if not path:
            return
        if os.path.getsize(path)>500*1024*1024 and not messagebox.askyesno(
            "File sangat besar",
            "File lebih dari 500 MB. Untuk efisiensi, sebaiknya ekspor footprint area desa dahulu.\n\n"
            "Tetap proses dengan batas 150.000 baris?"):
            return
        revision=self._revision
        bb=bounds(self.lines,self.points)
        self._footprint_loading=True
        self.status.set("Membaca & clipping footprint: "+os.path.basename(path))

        def worker():
            try:
                polygons=load_polygons(path,bbox=bb,min_confidence=.70)
                self.root.after(0,lambda:self._supplement_ready(polygons,revision))
            except Exception as exc:
                err=str(exc)
                self.root.after(0,lambda:self._supplement_fail(err,revision))
        threading.Thread(target=worker,daemon=True).start()

    def _supplement_ready(self,result,revision):
        self._footprint_loading=False
        if revision!=self._revision:
            return
        self._google_polygons=result["polygons"]
        self._apply_sources()
        self.status.set(f"{result['file']}: {len(self._google_polygons):,} bangunan dalam wilayah. "
                        f"Deduplikasi {self.osm.get('footprint_duplicates',0):,} geometri.")

    def _supplement_fail(self,error,revision):
        self._footprint_loading=False
        if revision==self._revision:
            self.status.set("Import footprint gagal: "+error[:120])
            messagebox.showerror("Footprint tidak terbaca",error)

    def _apply_sources(self):
        self.osm=merge_sources(self._raw_osm,self._input_polygons,self._google_polygons)
        stats=self.osm["footprint_sources"]
        self.extra_counts.set(
            f"OSM {stats['OSM']:,}  |  KML {stats['KML']:,}  |  Google/eksternal {stats['GOOGLE']:,}\n"
            f"Total unik: {self.osm['footprint_total']:,}  ·  duplikat: {self.osm['footprint_duplicates']:,}")
        self.draw()

    def load_osm(self):
        if not self.use_osm.get():
            self.status.set("Aktifkan OSM jalan & bangunan dahulu.")
            return
        if not self.lines and not self.points:
            messagebox.showwarning("OSM","Import KML/KMZ terlebih dahulu.")
            return
        if self._osm_loading:
            return
        revision=self._revision
        bb=bounds(self.lines,self.points)
        self._osm_loading=True
        self.status.set("OSM: fetch tile/cache + server cadangan berjalan...")

        def progress(txt):
            self.root.after(0,lambda msg=txt:self._progress(msg,revision))
        def worker():
            try:
                result=fetch_osm(bb,progress=progress)
                self.root.after(0,lambda:self._osm_ready(result,revision))
            except Exception as exc:
                err=str(exc)
                self.root.after(0,lambda:self._osm_failed(err,revision))
        threading.Thread(target=worker,daemon=True).start()

    def _progress(self,txt,revision):
        if revision==self._revision:
            self.status.set(txt)

    def _osm_ready(self,result,revision):
        self._osm_loading=False
        if revision!=self._revision:
            return
        self._raw_osm=result
        self._apply_sources()
        partial="parsial" if result.get("partial") else "lengkap"
        self.status.set(
            f"OSM {partial}: {len(result.get('roads',[])):,} jalan, "
            f"{len(result.get('buildings',[])):,} polygon OSM; "
            f"{self.osm['footprint_total']:,} footprint gabungan unik.")

    def _osm_failed(self,error,revision):
        self._osm_loading=False
        if revision==self._revision:
            self.status.set("OSM gagal; footprint KML/Google yang telah diimpor tetap tersedia. "+error[:115])
            messagebox.showwarning("OSM gagal",
                error[:400]+"\n\nFootprint tambahan tetap bisa digunakan, ekspor akan memberi peringatan.")

    def draw_on(self,canvas,bb):
        engineering.draw_preview(canvas,bb,self.lines,self.points,
                                 self.osm if self.use_osm.get() else None,
                                 canvas is self.map)
        if canvas is self.mini:
            w=max(canvas.winfo_width(),200)
            h=max(canvas.winfo_height(),200)
            sx=w*.845
            canvas.create_rectangle(sx,4,w-4,h-4,fill="white",outline="#222")
            canvas.create_text((sx+w)/2,14,text="AS BUILT DRAWING",font=("Segoe UI",7))
            legend=[("NEW POLE","#d1a300"),("NEW ODP","#c40013"),
                    ("NEW CLOSURE","#ea2027"),("CABLE TYPE","#204c96"),
                    ("FEEDER 96C","#f11"),("DISTRIBUTION","#ed269e"),
                    ("REVISION","#222"),("PROJECT NAME","#222"),
                    ("DRAWING SIGN","#222"),("SCALE N.T.S.","#222")]
            step=(h-50)/len(legend)
            for i,(label,color) in enumerate(legend):
                yy=26+i*step
                canvas.create_line(sx+4,yy+6,w-9,yy+6,fill="#aaa")
                canvas.create_text(sx+6,yy,text=label,anchor="nw",
                                   fill=color,font=("Segoe UI",6))
            canvas.create_text((sx+w)/2,h-16,text="SHEET / 5",
                               font=("Segoe UI",7,"bold"))

    def export(self):
        if not self.lines and not self.points:
            messagebox.showwarning("Belum ada data","Import jaringan dahulu.")
            return
        if self._osm_loading or self._footprint_loading:
            messagebox.showwarning("Masih memproses",
                "Tunggu pengambilan OSM / footprint tambahan selesai sebelum ekspor.")
            return
        if self.use_osm.get():
            roads=len(self.osm.get("roads",[]))
            buildings=len(self.osm.get("buildings",[]))
            if roads==0 or buildings==0 or self.osm.get("partial"):
                if not messagebox.askyesno("Data basemap belum lengkap",
                    f"Jalan OSM: {roads:,}\n"
                    f"Footprint gabungan: {buildings:,}\n"
                    f"OSM parsial: {bool(self.osm.get('partial'))}\n\n"
                    "Lanjut ekspor dengan data yang tersedia?"):
                    return
        super().export()


if __name__=="__main__":
    root=tk.Tk()
    NRPApp(root)
    root.mainloop()
