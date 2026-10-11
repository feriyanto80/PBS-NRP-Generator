"""Adaptive desktop shell v1.0.10.

Three-pane desktop, two-pane laptop and single-pane small-screen layouts.
Independent mousewheel/+/- zoom and mouse-drag pan on map and sheet previews.
One OSM button also attempts size-safe Google Open Buildings enrichment.
"""
import math
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import app as base_app
from app import bounds, viewport
from adaptive_sheets import plan_sheets
from launcher import NRPApp
from osm_acquisition import fetch_osm
from google_auto import acquire_google


class ResponsiveNRP(NRPApp):
    def __init__(self, root):
        # Bypass inherited fixed-size App.__init__. Retain all import/export,
        # engineering preview, dedupe and titleblock functionality from NRPApp.
        self.root = root
        self._input_polygons = []
        self._google_polygons = []
        self._raw_osm = None
        self._revision = 0
        self._osm_loading = False
        self._footprint_loading = False
        self._google_status = "Belum diambil"
        self._planned_sheets = []
        self._sheet_report = {}
        self._planning = False
        self._running = False
        self._progress_percent = 0.0
        self._kml_audit = {}
        self._mode = None
        self._active_panel = "map"
        self._layout_pending = None
        self._draw_pending = None
        self._map_view = None
        self._sheet_view = None
        self._drag_start = {}
        self.lines = []
        self.points = []
        self.osm = None
        self.use_osm = tk.BooleanVar(value=True)
        self.path = tk.StringVar()
        self.converter = tk.StringVar()
        self.want_dwg = tk.BooleanVar()
        self.status = tk.StringVar(value="Import KML/KMZ untuk memulai")
        self.extra_counts = tk.StringVar(value="OSM 0 · KML 0 · Google 0")
        self.plan_label = tk.StringVar(value="Auto-layout: menunggu proyek")
        self.progress_text = tk.StringVar(value="Akuisisi belum dijalankan")
        self.progress_value = tk.DoubleVar(value=0.0)
        root.title("PBS Network Route Plan Generator v1.0.10")
        root.configure(bg="#eef2f6")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{max(620,min(sw-60,1550))}x{max(470,min(sh-95,920))}")
        root.minsize(620,470)
        self._make_widgets()
        root.bind("<Configure>",self._root_resize)
        root.bind_all("<MouseWheel>",self._route_scroll,add="+")
        self._layout()
        self.status.set("KML polygon bukan otomatis bangunan · OSM + Google Open Buildings siap.")

    def _make_widgets(self):
        root=self.root
        header=tk.Frame(root,bg="#164b82",height=53)
        header.pack(fill="x")
        tk.Label(header,text="PBS  Network Route Plan Generator   v1.0.10",
                 bg="#164b82",fg="white",font=("Segoe UI",15,"bold"),
                 anchor="w").pack(side="left",fill="x",expand=True,padx=16,pady=10)
        self.header_steps=tk.Frame(root,bg="#e4edf6")
        self.header_steps.pack(fill="x")
        for title in ("1 Import KML/KMZ","2 Basemap & Bangunan",
                      "3 Pemetaan","4 Layout & Sheet","5 Export"):
            tk.Label(self.header_steps,text=title,font=("Segoe UI",9,"bold"),
                     bg="#e4edf6",fg="#214562",padx=6,pady=8).pack(
                         side="left",expand=True,fill="x",padx=2)
        self.quicknav=tk.Frame(root,bg="#f3f6fa")
        self.quick_buttons={}
        for key,title in (("settings","Pengaturan"),("map","Map Preview"),("sheet","Preview Sheet")):
            button=tk.Button(self.quicknav,text=title,font=("Segoe UI",9),
                             command=lambda key=key:self.show_panel(key),bd=1)
            button.pack(side="left",fill="x",expand=True,padx=3,pady=3)
            self.quick_buttons[key]=button
        self.body=tk.Frame(root,bg="#d9e3ed")
        self.body.pack(fill="both",expand=True,padx=6,pady=5)
        self.body.grid_rowconfigure(0,weight=1)
        self.sidebar=tk.Frame(self.body,bg="white",bd=1,relief="solid")
        self.map_panel=tk.Frame(self.body,bg="white",bd=1,relief="solid")
        self.sheet_panel=tk.Frame(self.body,bg="white",bd=1,relief="solid")
        self._build_sidebar()
        self._build_map_panel()
        self._build_sheet_panel()
        bottom=tk.Frame(root,bg="#e2eaf3",height=26)
        bottom.pack(fill="x")
        tk.Label(bottom,textvariable=self.status,anchor="w",bg="#e2eaf3",
                 fg="#32495b",font=("Segoe UI",9)).pack(fill="x",padx=9,pady=3)

    def _section(self,area,title):
        tk.Label(area,text=title,bg="#e7edf5",fg="#173957",anchor="w",
                 padx=10,pady=7,font=("Segoe UI",9,"bold")).pack(fill="x",pady=(8,0))

    def _build_sidebar(self):
        wrap=tk.Frame(self.sidebar,bg="white")
        wrap.pack(fill="both",expand=True)
        self.sidebar_scroll=tk.Canvas(wrap,bg="white",bd=0,highlightthickness=0)
        vertical=ttk.Scrollbar(wrap,orient="vertical",command=self.sidebar_scroll.yview)
        vertical.pack(side="right",fill="y")
        self.sidebar_scroll.pack(side="left",fill="both",expand=True)
        self.sidebar_scroll.configure(yscrollcommand=vertical.set)
        panel=tk.Frame(self.sidebar_scroll,bg="white")
        handle=self.sidebar_scroll.create_window((0,0),window=panel,anchor="nw")
        self.sidebar_scroll.bind("<Configure>",lambda e:self.sidebar_scroll.itemconfigure(handle,width=e.width))
        panel.bind("<Configure>",lambda e:self.sidebar_scroll.configure(scrollregion=self.sidebar_scroll.bbox("all")))
        self.left_content=panel
        self._section(panel,"1. Import KML/KMZ")
        tk.Button(panel,text="Pilih file KML/KMZ...",command=self.open_kmz).pack(fill="x",padx=12,pady=6)
        tk.Label(panel,textvariable=self.path,wraplength=255,bg="white",
                 fg="#53616d",font=("Segoe UI",8)).pack(fill="x",padx=12)
        self.stats=tk.Label(panel,text="Belum ada data",justify="left",anchor="w",
                            bg="white",font=("Consolas",9))
        self.stats.pack(fill="x",padx=12,pady=11)
        self._section(panel,"2. Basemap & Area")
        tk.Checkbutton(panel,text="Aktifkan OSM jalan + bangunan",variable=self.use_osm,
                       bg="white",command=self.schedule_draw).pack(anchor="w",padx=8,pady=4)
        self.osm_button=tk.Button(panel,text="Ambil / gunakan cache OSM + Google",
                                  command=self.load_osm,wraplength=250)
        self.osm_button.pack(fill="x",padx=12,pady=4)
        self.acq_progress=ttk.Progressbar(panel,mode="determinate",
                                         maximum=100,variable=self.progress_value)
        self.acq_progress.pack(fill="x",padx=12,pady=(8,3))
        tk.Label(panel,textvariable=self.progress_text,bg="white",
                 fg="#244861",font=("Segoe UI",8,"bold"),
                 wraplength=254,justify="left").pack(fill="x",padx=12)
        self.progress_log=tk.Listbox(panel,height=5,activestyle="none",
                                     font=("Segoe UI",8),
                                     fg="#435466",bg="#f5f8fb",relief="flat",
                                     selectbackground="#d1e1f4")
        self.progress_log.pack(fill="x",padx=12,pady=(3,8))
        tk.Label(panel,text="Google Open Buildings otomatis jika tile aman; "
                 "tidak diperlukan impor manual.",bg="white",fg="#566476",
                 font=("Segoe UI",8),justify="left",wraplength=248).pack(fill="x",padx=12)
        tk.Label(panel,textvariable=self.extra_counts,bg="white",fg="#1f5279",
                 font=("Segoe UI",8,"bold"),justify="left",
                 wraplength=248).pack(fill="x",padx=12,pady=5)
        self.google_label=tk.StringVar(value="Google: belum diperiksa")
        tk.Label(panel,textvariable=self.google_label,bg="white",fg="#647484",
                 font=("Segoe UI",8),justify="left",
                 wraplength=248).pack(fill="x",padx=12)
        self._section(panel,"3. Pemetaan & Simbol")
        tk.Label(panel,text="Feeder merah · Subfeeder ungu\n"
                 "Distribusi magenta · Titik kuning",justify="left",
                 bg="white",font=("Segoe UI",9)).pack(fill="x",padx=10,pady=8)
        self._section(panel,"4. Layout & Sheet")
        tk.Label(panel,text="A3 Landscape · Double-Line Frame\n"
                 "Adaptive Network-Aware Auto Pagination",justify="left",
                 bg="white",font=("Segoe UI",9)).pack(fill="x",padx=10,pady=5)
        tk.Label(panel,textvariable=self.plan_label,wraplength=255,
                 justify="left",bg="white",fg="#1c5279",
                 font=("Segoe UI",8,"bold")).pack(fill="x",padx=12,pady=(0,9))
        self._section(panel,"5. Export")
        tk.Button(panel,text="Pilih ODA File Converter (opsional)",
                  command=self.pick_oda).pack(fill="x",padx=12,pady=7)
        tk.Checkbutton(panel,text="Konversi DWG (butuh ODA)",
                       variable=self.want_dwg,bg="white").pack(anchor="w",padx=8)
        self.generate_button=tk.Button(panel,text="▶ Generate PDF + DXF (+ DWG)",
                  bg="#17813e",fg="white",font=("Segoe UI",10,"bold"),
                  command=self.export)
        self.generate_button.pack(fill="x",padx=12,pady=11)
        tk.Label(panel,text="Zoom: scroll mouse / tombol + −. "
                 "Geser peta: drag mouse. Fit: tampilkan seluruh area.",
                 bg="white",fg="#627281",wraplength=245,
                 justify="left",font=("Segoe UI",8)).pack(fill="x",padx=12,pady=7)

    def _preview_toolbar(self,parent,title,kind):
        bar=tk.Frame(parent,bg="white")
        bar.pack(fill="x",padx=8,pady=5)
        tk.Label(bar,text=title,fg="#172d40",bg="white",
                 font=("Segoe UI",10,"bold")).pack(side="left",fill="x",expand=True)
        for label,callback in (
            ("+",lambda:self._zoom(kind,0.75)),
            ("−",lambda:self._zoom(kind,1.333333)),
            ("Fit",lambda:self._fit(kind))):
            tk.Button(bar,text=label,width=4,command=callback,
                      font=("Segoe UI",9,"bold")).pack(side="left",padx=2)
        return bar

    def _build_map_panel(self):
        self._preview_toolbar(self.map_panel,"Map Preview · jaringan + jalan", "map")
        self.map=tk.Canvas(self.map_panel,bg="#fafafa",
                           highlightthickness=0)
        self.map.pack(fill="both",expand=True,padx=5,pady=(0,5))
        self._bind_zoom(self.map,"map")

    def _build_sheet_panel(self):
        self._preview_toolbar(self.sheet_panel,"Preview Sheet · zoom independen","sheet")
        self.sheet=ttk.Combobox(self.sheet_panel,values=[
            "1 - Overview","2 - Barat Laut","3 - Timur Laut",
            "4 - Barat Daya","5 - Tenggara"],state="readonly")
        self.sheet.current(0)
        self.sheet.pack(fill="x",padx=9,pady=3)
        self.sheet.bind("<<ComboboxSelected>>",lambda e:self._selected_sheet())
        self.mini=tk.Canvas(self.sheet_panel,bg="white",highlightthickness=0)
        self.mini.pack(fill="both",expand=True,padx=7,pady=5)
        self._bind_zoom(self.mini,"sheet")
        legend=tk.Frame(self.sheet_panel,bg="#f6f8fb")
        legend.pack(fill="x",padx=7,pady=5)
        tk.Label(legend,text="Legenda:",bg="#f6f8fb",fg="#244b6b",
                 font=("Segoe UI",9,"bold")).pack(side="left",padx=(5,8))
        for title,color in (("Feeder","#e52328"),("Subfeeder","#9323b7"),
                            ("Distribusi","#ed269e"),("Titik","#e5b800")):
            tk.Label(legend,text="━ "+title,bg="#f6f8fb",fg=color,
                     font=("Segoe UI",8)).pack(side="left",padx=4)

    def _root_resize(self,event):
        if event.widget is self.root:
            if self._layout_pending is not None:
                self.root.after_cancel(self._layout_pending)
            self._layout_pending=self.root.after(100,self._layout)

    def _layout(self):
        self._layout_pending=None
        width=self.body.winfo_width() or self.root.winfo_width()
        mode="wide" if width>=1200 else "medium" if width>=850 else "small"
        if mode==self._mode:
            return
        self._mode=mode
        if mode=="small":
            self.header_steps.pack_forget()
        elif not self.header_steps.winfo_manager():
            before_widget=(self.quicknav if self.quicknav.winfo_manager() else self.body)
            self.header_steps.pack(fill="x",before=before_widget)
        for panel in (self.sidebar,self.map_panel,self.sheet_panel):
            panel.grid_forget()
        for col in range(3):
            self.body.grid_columnconfigure(col,weight=0,minsize=0)
        if mode=="wide":
            self.quicknav.pack_forget()
            self.body.grid_columnconfigure(0,weight=0,minsize=285)
            self.body.grid_columnconfigure(1,weight=5,minsize=310)
            self.body.grid_columnconfigure(2,weight=6,minsize=390)
            self.sidebar.grid(row=0,column=0,sticky="nsew",padx=2)
            self.map_panel.grid(row=0,column=1,sticky="nsew",padx=2)
            self.sheet_panel.grid(row=0,column=2,sticky="nsew",padx=2)
        elif mode=="medium":
            self.quicknav.pack(fill="x",before=self.body)
            self.body.grid_columnconfigure(0,weight=0,minsize=275)
            self.body.grid_columnconfigure(1,weight=1,minsize=400)
            self.sidebar.grid(row=0,column=0,sticky="nsew",padx=2)
            panel=self.sheet_panel if self._active_panel=="sheet" else self.map_panel
            panel.grid(row=0,column=1,sticky="nsew",padx=2)
        else:
            self.quicknav.pack(fill="x",before=self.body)
            self.body.grid_columnconfigure(0,weight=1,minsize=0)
            panel={"map":self.map_panel,"sheet":self.sheet_panel,
                   "settings":self.sidebar}[self._active_panel]
            panel.grid(row=0,column=0,sticky="nsew",padx=2)
        for key,button in self.quick_buttons.items():
            button.configure(relief="sunken" if key==self._active_panel else "raised")
        self.schedule_draw()

    def show_panel(self,key):
        self._active_panel=key
        self._mode=None
        self._layout()

    def _bind_zoom(self,canvas,kind):
        canvas.bind("<Configure>",lambda event:self.schedule_draw())
        canvas.bind("<MouseWheel>",lambda e:self._scroll_zoom(e,kind))
        canvas.bind("<Button-4>",lambda e:self._zoom(kind,.80,e.x,e.y))
        canvas.bind("<Button-5>",lambda e:self._zoom(kind,1.25,e.x,e.y))
        canvas.bind("<ButtonPress-1>",lambda e:self._begin_pan(kind,e.x,e.y))
        canvas.bind("<B1-Motion>",lambda e:self._drag_pan(kind,e.x,e.y))
        canvas.bind("<Double-Button-1>",lambda e:self._fit(kind))

    def _route_scroll(self,event):
        # Wheel on sidebar children should scroll sidebar, never zoom a map.
        if event.widget in (self.map,self.mini):
            return
        widget=event.widget
        while widget is not None:
            if widget is self.sidebar:
                self.sidebar_scroll.yview_scroll(-1 if event.delta>0 else 1,"units")
                return
            widget=getattr(widget,"master",None)

    def _scroll_zoom(self,event,kind):
        self._zoom(kind,.80 if event.delta>0 else 1.25,event.x,event.y)
        return "break"

    def _base_bbox(self,kind):
        if not self.lines and not self.points:
            return None
        project=bounds(self.lines,self.points)
        if kind=="sheet":
            index=max(0,self.sheet.current())
            available=self._planned_sheets or [("Overview",project)]
            return available[min(index,len(available)-1)][1]
        return project

    def _bbox(self,kind):
        return (self._map_view if kind=="map" else self._sheet_view) or self._base_bbox(kind)

    def _set_bbox(self,kind,bb):
        if kind=="map":
            self._map_view=bb
        else:
            self._sheet_view=bb

    def _fit(self,kind):
        self._set_bbox(kind,None)
        self.schedule_draw()

    @staticmethod
    def _scale(bb,w,h):
        lat=math.radians((bb[1]+bb[3])/2)
        factor=max(.01,math.cos(lat))
        dx=max((bb[2]-bb[0])*factor,1e-8)
        dy=max(bb[3]-bb[1],1e-8)
        scale=min((w-36)/dx,(h-36)/dy)
        return factor,scale

    def _canvas(self,kind):
        return self.map if kind=="map" else self.mini

    def _zoom(self,kind,multiplier,x=None,y=None):
        bb=self._bbox(kind)
        original=self._base_bbox(kind)
        if bb is None or original is None:
            return
        current=bb[2]-bb[0]
        minspan=(original[2]-original[0])/75
        maxspan=(original[2]-original[0])*3.5
        nextspan=min(max(current*multiplier,minspan),maxspan)
        multiplier=nextspan/max(current,1e-12)
        if abs(multiplier-1)<1e-8:
            return
        canvas=self._canvas(kind)
        w=max(canvas.winfo_width(),200)
        h=max(canvas.winfo_height(),200)
        x=w/2 if x is None else x
        y=h/2 if y is None else y
        factor,scale=self._scale(bb,w,h)
        cx,cy=(bb[0]+bb[2])/2,(bb[1]+bb[3])/2
        anchor_lon=cx+(x-w/2)/(factor*scale)
        anchor_lat=cy+(h/2-y)/scale
        newfactor,newscale=self._scale((
            cx-(bb[2]-bb[0])*multiplier/2,
            cy-(bb[3]-bb[1])*multiplier/2,
            cx+(bb[2]-bb[0])*multiplier/2,
            cy+(bb[3]-bb[1])*multiplier/2),w,h)
        newcx=anchor_lon-(x-w/2)/(newfactor*newscale)
        newcy=anchor_lat-(h/2-y)/newscale
        dx=(bb[2]-bb[0])*multiplier/2
        dy=(bb[3]-bb[1])*multiplier/2
        self._set_bbox(kind,(newcx-dx,newcy-dy,newcx+dx,newcy+dy))
        self.schedule_draw()

    def _begin_pan(self,kind,x,y):
        self._drag_start[kind]=(x,y,self._bbox(kind))

    def _drag_pan(self,kind,x,y):
        saved=self._drag_start.get(kind)
        if not saved or saved[2] is None:
            return
        initial_x,initial_y,bb=saved
        canvas=self._canvas(kind)
        factor,scale=self._scale(bb,max(200,canvas.winfo_width()),max(200,canvas.winfo_height()))
        dlon=-(x-initial_x)/(factor*scale)
        dlat=(y-initial_y)/scale
        self._set_bbox(kind,(bb[0]+dlon,bb[1]+dlat,bb[2]+dlon,bb[3]+dlat))
        self.schedule_draw()

    def _selected_sheet(self):
        self._sheet_view=None
        self.schedule_draw()

    def schedule_draw(self):
        if self._draw_pending is None:
            self._draw_pending=self.root.after(75,self.draw)

    def draw(self):
        self._draw_pending=None
        if not self.lines and not self.points:
            return
        try:
            self.draw_on(self.map,self._bbox("map"))
            self.draw_on(self.mini,self._bbox("sheet"))
        except tk.TclError:
            return

    def _record_progress(self, percent, message):
        """Live Tk progress; percentage tracks completed workflow stages."""
        percent=max(self._progress_percent,min(100.0,float(percent)))
        self._progress_percent=percent
        self.progress_value.set(percent)
        self.progress_text.set(f"{percent:.0f}% · {message}")
        self.status.set(message)
        self.progress_log.insert("end",f"{percent:3.0f}%  {message[:110]}")
        while self.progress_log.size()>25:
            self.progress_log.delete(0)
        self.progress_log.yview_moveto(1.0)

    def _rebuild_sheet_plan(self):
        if not self.lines and not self.points:
            self._planned_sheets=[]
            self._sheet_report={}
            self.plan_label.set("Auto-layout: menunggu KML/KMZ")
            return
        self._planning=True
        self._update_generate_button()
        try:
            bb=bounds(self.lines,self.points)
            sheets,report=plan_sheets(self.lines,self.points,bb)
            self._planned_sheets=sheets
            self._sheet_report=report
            self.sheet.configure(values=[
                f"{i+1:02d} - {entry[0]}" for i,entry in enumerate(sheets)
            ])
            self.sheet.current(0)
            self._sheet_view=None
            self.plan_label.set(
                f"{len(sheets)} sheet: 1 Overview + {report['details']} Detail\n"
                f"Network-density planning · overlap 7.5%\n"
                f"Target 230 titik / 300 ruas per sheet"
            )
            self.schedule_draw()
        finally:
            self._planning=False
            self._update_generate_button()

    def _update_generate_button(self):
        busy=self._running or self._osm_loading or self._footprint_loading or self._planning
        self.generate_button.configure(
            state="disabled" if busy else "normal",
            bg="#8d9aa5" if busy else "#17813e",
            text=("⏳ Akuisisi berjalan · Export terkunci"
                  if busy else "▶ Generate PDF + DXF (+ DWG)"))

    def open_kmz(self):
        if self._running or self._osm_loading or self._planning:
            messagebox.showwarning("Akuisisi berjalan",
                "Tunggu proses OSM + Google selesai sebelum mengganti proyek.")
            return
        previous_revision=self._revision
        super().open_kmz()
        if self._revision==previous_revision:
            return
        self._map_view=None
        self._sheet_view=None
        self._google_status="Belum diambil"
        self.google_label.set("Google: menunggu tombol Ambil/cache")
        self.progress_value.set(0.0)
        self._progress_percent=0.0
        self.progress_text.set("Proyek siap: klik Ambil / gunakan cache OSM + Google")
        self.progress_log.delete(0,"end")
        self._rebuild_sheet_plan()

    def _stage_percentage(self,message):
        if message.startswith("OSM tile"):
            match=re.search(r"tile\s+(\d+)\s*/\s*(\d+)",message)
            if match:
                done,total=map(int,match.groups())
                return 5+58*done/max(total,1)
            return 10
        if message.startswith("OSM"):
            return 8
        if message.startswith("Google Buildings"):
            if "fase 1/4" in message:return 66
            if "fase 2/4" in message:return 70
            if "tile ditemukan" in message or "batas aman" in message:return 73
            if "SKIP" in message:return 76
            if "fase 3/4" in message:return 80
            if "tile " in message:return 82
            if "fase 4/4" in message:return 88
            return 67
        return 5

    def _progress(self,message,revision):
        if revision!=self._revision or not self._running:
            return
        self._record_progress(self._stage_percentage(message),message)

    def load_osm(self):
        if not self.use_osm.get():
            self.status.set("Aktifkan checkbox OSM jalan & bangunan dahulu.")
            return
        if not self.lines and not self.points:
            messagebox.showwarning("OSM + Google",
                "Import file KML/KMZ terlebih dahulu.")
            return
        if self._running or self._footprint_loading or self._planning:
            self.status.set("Akuisisi sedang berjalan; lihat log progres.")
            return
        revision=self._revision
        bb=bounds(self.lines,self.points)
        self._running=True
        self._osm_loading=True
        self._progress_percent=0.0
        self.progress_log.delete(0,"end")
        self.osm_button.configure(state="disabled",text="Mengambil OSM + Google...")
        self._update_generate_button()
        self._record_progress(1,"Mulai akuisisi: OSM → Google → Merge → Sheet Planning")

        def progress(message):
            try:
                self.root.after(0,lambda msg=message:self._progress(msg,revision))
            except RuntimeError:
                pass

        def worker():
            osm=None
            osm_error=None
            google={"polygons":[],"status":"unavailable","reason":"belum dicoba"}
            try:
                progress("OSM: memeriksa cache tile dan server cadangan")
                osm=fetch_osm(bb,progress=progress)
                progress(f"OSM: {len(osm.get('roads',[]))} jalan, "
                         f"{len(osm.get('buildings',[]))} bangunan berhasil")
            except Exception as exc:
                osm_error=str(exc)
                progress("OSM: gagal setelah fallback, tetap memeriksa Google")
            try:
                google=acquire_google(bb,progress=progress)
            except Exception as exc:
                google={"polygons":[],"status":"unavailable","reason":str(exc)}
            try:
                self.root.after(0,lambda:self._acquisition_done(
                    revision,osm,google,osm_error))
            except RuntimeError:
                pass
        threading.Thread(target=worker,daemon=True).start()

    def _acquisition_done(self,revision,osm,google,osm_error):
        # Mark source workers finished before re-enabling any output action.
        self._running=False
        self._osm_loading=False
        self.osm_button.configure(state="normal",
                                  text="Ambil / gunakan cache OSM + Google")
        if revision!=self._revision:
            self._update_generate_button()
            return
        self._record_progress(91,"Akuisisi selesai; menggabungkan footprint dan deduplikasi")
        if osm is not None:
            self._raw_osm=osm
        self._google_polygons=google.get("polygons",[])
        self._google_status=google.get("status","unavailable")
        reason=google.get("reason") or ""
        self.google_label.set(
            f"Google: {self._google_status} · {reason[:160]}"
            if reason else f"Google: {self._google_status}"
        )
        self._apply_sources()
        self._record_progress(95,"Menghitung jumlah sheet dari kepadatan jaringan")
        self._rebuild_sheet_plan()
        roads=len(self.osm.get("roads",[]))
        buildings=len(self.osm.get("buildings",[]))
        detail=f"{len(self._planned_sheets)} sheet, {roads} jalan, {buildings} bangunan"
        if self._google_status=="skipped_large":
            detail+="; Google SKIPPED: tile > batas aman, bukan error proses"
        elif self._google_status!="ready":
            detail+=f"; Google {self._google_status}"
        if osm_error:
            detail+="; OSM gagal: "+osm_error[:75]
        # 100% is workflow completion, not proof of 100% Google coverage.
        self._record_progress(100,"Job selesai · "+detail)
        self._update_generate_button()
        if not roads and not buildings:
            messagebox.showwarning("Basemap belum lengkap",
                "Job selesai tanpa data jalan/bangunan. Data input KML/KMZ tetap tersedia.\n\n"
                +str(osm_error or reason)[:350]+
                "\n\nGenerate diaktifkan kembali; PDF akan memperingatkan jika basemap tidak lengkap.")

    def export(self):
        if self._running or self._osm_loading or self._footprint_loading or self._planning:
            messagebox.showwarning("Export terkunci",
                "Tunggu akuisisi OSM/Google dan perhitungan sheet selesai.")
            return
        if not self._planned_sheets and (self.lines or self.points):
            self._rebuild_sheet_plan()
        old_sheets=base_app.sheets_for
        try:
            # Existing cumulative PDF exporter calls app.sheets_for(bbox).
            base_app.sheets_for=lambda _bbox:list(self._planned_sheets)
            super().export()
        finally:
            base_app.sheets_for=old_sheets


if __name__=="__main__":
    root=tk.Tk()
    ResponsiveNRP(root)
    root.mainloop()
