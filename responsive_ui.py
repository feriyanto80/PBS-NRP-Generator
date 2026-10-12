"""Adaptive desktop shell v1.0.22.6.

Three-pane desktop, two-pane laptop and single-pane small-screen layouts.
Independent mousewheel/+/- zoom and mouse-drag pan on map and sheet previews.
One OSM button includes full Google tile downloads with disk cache and resume.
"""
import math
import os
import json
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import app as base_app
from app import bounds, viewport
from adaptive_sheets import plan_sheets
from launcher import NRPApp
from osm_acquisition import fetch_osm
from google_auto import acquire_google
from google_stream import default_cache
from drawing_settings import apply_presentation
from dwg_ui import DWGAutoMixin
from exact_template import has_exact_template, find_reference


class ResponsiveNRP(DWGAutoMixin, NRPApp):
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
        self._google_cache_dir = default_cache()
        self._cache_settings = os.path.join(os.path.dirname(default_cache()), "settings.json")
        try:
            with open(self._cache_settings,encoding="utf-8") as source:
                config=json.load(source)
            selected=config.get("google_cache_dir","")
            if selected and os.path.isabs(selected):
                self._google_cache_dir=selected
        except (OSError,ValueError,TypeError):
            pass
        self.cache_dir_text = tk.StringVar(value="Cache Google: "+self._google_cache_dir)
        self._planned_sheets = []
        self._sheet_report = {}
        self._planning = False
        self._running = False
        self._progress_percent = 0.0
        self._last_download_logged = -1
        self._kml_audit = {}
        self._mode = None
        self._active_panel = "map"
        self._layout_pending = None
        self._draw_pending = None
        self._map_view = None
        self._sheet_view = None
        self._drag_start = {}
        self._section_targets = {}
        self._section_panels = {}
        self._section_buttons = []
        self.lines = []
        self.points = []
        self.osm = None
        self.use_osm = tk.BooleanVar(value=True)
        self.path = tk.StringVar()
        self.converter = tk.StringVar()
        self.want_dwg = tk.BooleanVar()
        self.initialize_dwg_support()
        self.status = tk.StringVar(value="Import KML/KMZ untuk memulai")
        self.extra_counts = tk.StringVar(value="OSM 0 · KML 0 · Google 0")
        self.plan_label = tk.StringVar(value="Auto-layout: menunggu proyek")
        self.progress_text = tk.StringVar(value="Akuisisi belum dijalankan")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.use_reference_cad = tk.BooleanVar(value=True)
        self.layer_flags = {name:tk.BooleanVar(value=True) for name in (
            "feeder","subfeeder","distribution","points","roads","buildings")}
        self.show_point_labels = tk.BooleanVar(value=True)
        self.point_size = tk.DoubleVar(value=2.0)
        self.target_points = tk.IntVar(value=230)
        self.target_routes = tk.IntVar(value=300)
        self.max_detail_sheets = tk.IntVar(value=24)
        self.sheet_overlap_pct = tk.DoubleVar(value=7.5)
        self.layout_preset = tk.StringVar(value="Normal")
        self.cad_reference_style = tk.BooleanVar(value=True)
        self.google_download_value = tk.DoubleVar(value=0.0)
        self.google_download_stage = tk.StringVar(value="Google Buildings · menunggu unduhan")
        self.google_download_detail = tk.StringVar(value="Belum ada file yang sedang diunduh")
        self.overall_progress_label = tk.StringVar(value="PROGRES PEKERJAAN · 0%")
        root.title("PBS Network Route Plan Generator v1.0.22.6")
        root.configure(bg="#eef2f6")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        dw=max(620,min(sw-60,1550))
        dh=max(470,min(sh-95,920))
        root.geometry(f"{dw}x{dh}+{max(0,(sw-dw)//2)}+{max(0,(sh-dh)//2)}")
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
        tk.Label(header,text="PBS  Network Route Plan Generator   v1.0.22.6",
                 bg="#164b82",fg="white",font=("Segoe UI",15,"bold"),
                 anchor="w").pack(side="left",fill="x",expand=True,padx=16,pady=10)
        self.header_steps=tk.Frame(root,bg="#e4edf6")
        self.header_steps.pack(fill="x")
        self.progress_banner=tk.Frame(root,bg="#eef5ff",bd=1,relief="solid")
        self.progress_banner.pack_forget()
        header=tk.Frame(self.progress_banner,bg="#eef5ff")
        header.pack(fill="x",padx=12,pady=(5,0))
        tk.Label(header,text="LIVE JOB PROGRESS",bg="#eef5ff",fg="#19486f",
                 font=("Segoe UI",10,"bold")).pack(side="left")
        tk.Label(header,text="Workflow dan unduhan Google ditampilkan TERPISAH",
                 bg="#eef5ff",fg="#506b82",font=("Segoe UI",8)).pack(side="right")
        overall_line=tk.Frame(self.progress_banner,bg="#eef5ff")
        overall_line.pack(fill="x",padx=12,pady=(4,1))
        tk.Label(overall_line,textvariable=self.overall_progress_label,width=32,
                 bg="#eef5ff",fg="#24516b",anchor="w",
                 font=("Segoe UI",9,"bold")).pack(side="left")
        self.banner_overall=ttk.Progressbar(overall_line,maximum=100,
                 variable=self.progress_value,mode="determinate")
        self.banner_overall.pack(side="left",fill="x",expand=True,padx=(6,0))
        google_line=tk.Frame(self.progress_banner,bg="#eef5ff")
        google_line.pack(fill="x",padx=12,pady=(1,1))
        tk.Label(google_line,textvariable=self.google_download_stage,width=32,
                 bg="#eef5ff",fg="#24516b",anchor="w",
                 font=("Segoe UI",9,"bold")).pack(side="left")
        self.banner_download=ttk.Progressbar(google_line,maximum=100,
                 variable=self.google_download_value,mode="determinate")
        self.banner_download.pack(side="left",fill="x",expand=True,padx=(6,0))
        tk.Label(self.progress_banner,textvariable=self.google_download_detail,
                 bg="#eef5ff",fg="#15364e",anchor="w",
                 font=("Consolas",9,"bold")).pack(fill="x",padx=12,pady=(2,6))
        for i,title in enumerate(("1 Import KML/KMZ","2 Basemap & Bangunan",
                      "3 Pemetaan","4 Layout & Sheet","5 Export"),1):
            tk.Button(self.header_steps,text=title,font=("Segoe UI",9,"bold"),
                     bg="#e4edf6",fg="#214562",bd=0,
                     activebackground="#d0e1f1",cursor="hand2",
                     command=lambda section=str(i):self._jump_to_section(section),
                     padx=6,pady=8).pack(
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
        """Every section is independently collapsible while its header stays visible."""
        number=title.split(".",1)[0].strip()
        heading=tk.StringVar(value="▾  "+title)
        label=tk.Button(
            area,textvariable=heading,bg="#e7edf5",fg="#173957",
            activebackground="#d1e2f3",activeforeground="#173957",
            relief="flat",bd=0,anchor="w",cursor="hand2",
            padx=9,pady=7,font=("Segoe UI",9,"bold"),
            command=lambda number=number:self._toggle_section(number))
        label.pack(fill="x",pady=(8,0))
        if number.isdigit():
            self._section_targets[number]=label
            self._section_buttons.append((number,label,heading,title))
        return label

    def _init_collapsible_sections(self):
        """Record child widget packing so restore never reorders unrelated sections."""
        siblings=self.left_content.winfo_children()
        for number,label,heading,title in self._section_buttons:
            start=siblings.index(label)
            following=None
            for other_number,other_label,_,_ in self._section_buttons:
                if siblings.index(other_label)>start:
                    following=other_label
                    break
            end=siblings.index(following) if following else len(siblings)
            contents=[]
            for widget in siblings[start+1:end]:
                options=dict(widget.pack_info())
                options.pop("in",None)
                contents.append((widget,options))
            self._section_panels[number]={
                "header":label,"caption":heading,"title":title,
                "widgets":contents,"next":following,"expanded":True
            }

    def _set_section_expanded(self,number,expanded):
        item=self._section_panels.get(str(number))
        if item is None or item["expanded"]==bool(expanded):
            return
        if not expanded:
            for widget,_ in item["widgets"]:
                widget.pack_forget()
        else:
            for widget,options in item["widgets"]:
                args=dict(options)
                if item["next"] is not None:
                    args["before"]=item["next"]
                widget.pack(**args)
        item["expanded"]=bool(expanded)
        item["caption"].set(("▾  " if expanded else "▸  ")+item["title"])
        self.root.update_idletasks()
        self.sidebar_scroll.configure(scrollregion=self.sidebar_scroll.bbox("all"))

    def _toggle_section(self,number):
        item=self._section_panels.get(str(number))
        if item:
            self._set_section_expanded(number,not item["expanded"])

    def _set_all_sections(self,expanded):
        for number,_,_,_ in self._section_buttons:
            self._set_section_expanded(number,expanded)

    def _jump_to_section(self,section):
        if self._mode=="small":
            self.show_panel("settings")
        self._set_section_expanded(section,True)
        target=self._section_targets.get(section)
        if not target:
            return
        def scroll():
            try:
                total=max(1,self.left_content.winfo_height())
                self.sidebar_scroll.yview_moveto(min(.99,max(0,target.winfo_y()/total)))
            except tk.TclError:
                return
        self.root.after(60,scroll)

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
        controls=tk.Frame(panel,bg="white")
        controls.pack(fill="x",padx=9,pady=(6,0))
        tk.Button(controls,text="▸ Collapse All",
                  command=lambda:self._set_all_sections(False),
                  font=("Segoe UI",8),bg="#f0f5fa").pack(side="left",fill="x",expand=True,padx=(0,3))
        tk.Button(controls,text="▾ Expand All",
                  command=lambda:self._set_all_sections(True),
                  font=("Segoe UI",8),bg="#f0f5fa").pack(side="left",fill="x",expand=True,padx=(3,0))
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
        tk.Button(panel,text="Folder Cache Google (pilih disk penyimpanan)",
                  command=self.choose_google_cache).pack(fill="x",padx=12,pady=(3,2))
        tk.Label(panel,textvariable=self.cache_dir_text,bg="white",fg="#647484",
                 font=("Segoe UI",8),justify="left",wraplength=252).pack(fill="x",padx=12,pady=(0,3))
        self.acq_progress=ttk.Progressbar(panel,mode="determinate",
                                         maximum=100,variable=self.progress_value)
        self.acq_progress.pack(fill="x",padx=12,pady=(8,3))
        tk.Label(panel,textvariable=self.progress_text,bg="white",
                 fg="#244861",font=("Segoe UI",8,"bold"),
                 wraplength=254,justify="left").pack(fill="x",padx=12)
        self.progress_log=tk.Listbox(panel,height=7,activestyle="none",
                                     font=("Segoe UI",8),
                                     fg="#435466",bg="#f5f8fb",relief="flat",
                                     selectbackground="#d1e1f4")
        self.progress_log.pack(fill="x",padx=12,pady=(3,8))
        tk.Label(panel,text="Google Open Buildings seluruh tile area, unduh/resume cache; "
                 "butuh ruang disk hingga beberapa GB.",bg="white",fg="#566476",
                 font=("Segoe UI",8),justify="left",wraplength=248).pack(fill="x",padx=12)
        tk.Label(panel,textvariable=self.extra_counts,bg="white",fg="#1f5279",
                 font=("Segoe UI",8,"bold"),justify="left",
                 wraplength=248).pack(fill="x",padx=12,pady=5)
        self.google_label=tk.StringVar(value="Google: belum diperiksa")
        tk.Label(panel,textvariable=self.google_label,bg="white",fg="#647484",
                 font=("Segoe UI",8),justify="left",
                 wraplength=248).pack(fill="x",padx=12)
        self._section(panel,"3. Pemetaan & Simbol")
        tk.Checkbutton(panel,text="Standar CAD DXF 2018 Lemah Abang",
                       variable=self.use_reference_cad,bg="white",
                       font=("Segoe UI",8,"bold"),
                       command=self.schedule_draw).pack(fill="x",padx=10,pady=(5,3))
        tk.Label(panel,text="Layer asli: Jalan, buildings, FO 12–288 CORE, "
                 "ODP/ODC, Homepass, pole T6/T7/T9. PaperSpace A3.",
                 bg="white",fg="#607487",font=("Segoe UI",8),
                 justify="left",wraplength=250).pack(fill="x",padx=12,pady=(0,4))
        tk.Label(panel,text="Atur layer yang muncul pada preview, PDF dan DXF",
                 bg="white",fg="#526a7b",anchor="w",
                 font=("Segoe UI",8),wraplength=255).pack(fill="x",padx=12,pady=3)
        for key,label in (
            ("feeder","FEEDER (merah)"),
            ("subfeeder","SUBFEEDER (ungu)"),
            ("distribution","DISTRIBUSI (magenta)"),
            ("points","Titik perangkat (kuning)"),
            ("roads","Tepi jalan OSM (abu-abu)"),
            ("buildings","Footprint bangunan"),
        ):
            tk.Checkbutton(panel,text=label,bg="white",anchor="w",
                           variable=self.layer_flags[key],
                           command=self.schedule_draw).pack(fill="x",padx=10)
        tk.Checkbutton(panel,text="Tampilkan label titik pada detail PDF/DXF",
                       bg="white",anchor="w",variable=self.show_point_labels,
                       command=self.schedule_draw).pack(fill="x",padx=10,pady=(4,0))
        tk.Label(panel,text="Ukuran simbol CAD sesuai legenda (1–5 pt)",bg="white",
                 anchor="w",font=("Segoe UI",8)).pack(fill="x",padx=12)
        tk.Scale(panel,from_=1,to=5,resolution=.5,orient="horizontal",
                 variable=self.point_size,bg="white",highlightthickness=0,
                 command=lambda v:self.schedule_draw()).pack(fill="x",padx=12)
        self._section(panel,"4. Layout & Sheet")
        tk.Label(panel,text="A3 Landscape · Double-Line Frame · Adaptive NRP",
                 bg="white",fg="#536878",font=("Segoe UI",8),
                 wraplength=250,justify="left").pack(fill="x",padx=12,pady=4)
        tk.Checkbutton(panel,text="Format CAD Referensi Lemah Abang 2018",
                       variable=self.cad_reference_style,bg="white",
                       font=("Segoe UI",8,"bold")).pack(fill="x",padx=10,pady=(1,2))
        exact=has_exact_template()
        self.template_status = tk.StringVar(value=(
            "TEMPLATE ASLI AKTIF · PDF + DXF Lemah Abang ditemukan."
            if exact else
            "TEMPLATE ASLI TIDAK ADA · gunakan ZIP kumulatif agar bentuk font/logo persis."
        ))
        tk.Label(panel,textvariable=self.template_status,
                 bg="white",fg=("#116439" if exact else "#ad5a20"),
                 wraplength=250,justify="left",
                 font=("Segoe UI",8,"bold")).pack(fill="x",padx=12,pady=(0,4))
        tk.Label(panel,text="Mode template asli memakai garis/teks/simbol dari DXF 2018 "
                 "dan bagian legenda PDF asli tanpa membawa nama proyek lama.",
                 bg="white",fg="#526a7b",wraplength=250,justify="left",
                 font=("Segoe UI",8)).pack(fill="x",padx=12,pady=(0,5))
        preset_line=tk.Frame(panel,bg="white")
        preset_line.pack(fill="x",padx=12,pady=3)
        tk.Label(preset_line,text="Preset kepadatan:",bg="white",
                 font=("Segoe UI",8)).pack(side="left")
        presets=ttk.Combobox(preset_line,state="readonly",width=12,
                             textvariable=self.layout_preset,
                             values=("Ringkas","Normal","Detail"))
        presets.pack(side="right")
        presets.bind("<<ComboboxSelected>>",self._preset_changed)
        for caption,var,start,end in (
            ("Maksimum titik / sheet",self.target_points,30,2500),
            ("Maksimum ruas / sheet",self.target_routes,30,2500),
            ("Maksimum sheet detail",self.max_detail_sheets,1,100),
        ):
            row=tk.Frame(panel,bg="white")
            row.pack(fill="x",padx=12,pady=3)
            tk.Label(row,text=caption,bg="white",font=("Segoe UI",8),
                     anchor="w").pack(side="left",fill="x",expand=True)
            tk.Spinbox(row,from_=start,to=end,textvariable=var,
                       width=7,justify="right").pack(side="right")
        row=tk.Frame(panel,bg="white")
        row.pack(fill="x",padx=12,pady=3)
        tk.Label(row,text="Overlap antarsheet (%)",bg="white",
                 font=("Segoe UI",8)).pack(side="left",fill="x",expand=True)
        tk.Spinbox(row,from_=0,to=20,increment=.5,textvariable=self.sheet_overlap_pct,
                   width=7,justify="right").pack(side="right")
        tk.Button(panel,text="↻ Hitung Ulang Auto-Layout",
                  command=self._recalculate_layout,bg="#e3eff9",
                  fg="#194f7a").pack(fill="x",padx=12,pady=(7,4))
        tk.Label(panel,textvariable=self.plan_label,wraplength=255,
                 justify="left",bg="white",fg="#1c5279",
                 font=("Segoe UI",8,"bold")).pack(fill="x",padx=12,pady=(0,9))
        self._section(panel,"5. Export")
        self.build_dwg_controls(panel)
        self.generate_button=tk.Button(panel,text="▶ Generate PDF + DXF (+ DWG)",
                  bg="#17813e",fg="white",font=("Segoe UI",10,"bold"),
                  command=self.export)
        self.generate_button.pack(fill="x",padx=12,pady=11)
        tk.Label(panel,text="Zoom: scroll mouse / tombol + −. "
                 "Geser peta: drag mouse. Fit: tampilkan seluruh area.",
                 bg="white",fg="#627281",wraplength=245,
                 justify="left",font=("Segoe UI",8)).pack(fill="x",padx=12,pady=7)
        self._init_collapsible_sections()

    def _preset_changed(self,event=None):
        choices={"Ringkas":(420,520),"Normal":(230,300),"Detail":(110,160)}
        p,l=choices.get(self.layout_preset.get(),(230,300))
        self.target_points.set(p)
        self.target_routes.set(l)
        self._recalculate_layout()

    def _recalculate_layout(self):
        if self._running or self._osm_loading:
            messagebox.showwarning("Akuisisi berjalan",
                "Pengaturan sheet baru dapat dihitung ulang setelah pekerjaan OSM/Google selesai.")
            return
        self._rebuild_sheet_plan()

    def _layer_options(self):
        choices={key:value.get() for key,value in self.layer_flags.items()}
        choices["point_labels"]=self.show_point_labels.get()
        choices["point_size"]=self.point_size.get()
        return choices

    def draw_on(self,canvas,bb):
        """Non-destructive layer settings used in both preview canvases."""
        original=(self.lines,self.points,self.osm)
        self.lines,self.points,self.osm=apply_presentation(*original,self._layer_options())
        try:
            return super().draw_on(canvas,bb)
        finally:
            self.lines,self.points,self.osm=original

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
        self.overall_progress_label.set(f"WORKFLOW · {percent:.0f}% selesai")
        self.progress_text.set(f"{percent:.0f}% · {message}")
        self._update_google_download_display(message)
        self.status.set(message)
        add_log=True
        if "| DOWNLOAD |" in message:
            match=re.search(r"\(([0-9.]+)%\)",message)
            if match:
                bucket=int(float(match.group(1))//5)
                add_log=bucket!=self._last_download_logged
                if add_log:
                    self._last_download_logged=bucket
        if add_log:
            self.progress_log.insert("end",f"{percent:3.0f}%  {message[:150]}")
            while self.progress_log.size()>35:
                self.progress_log.delete(0)
            self.progress_log.yview_moveto(1.0)

    def _show_progress_banner(self):
        if not self.progress_banner.winfo_manager():
            target=self.quicknav if self.quicknav.winfo_manager() else self.body
            self.progress_banner.pack(fill="x",before=target)

    def _update_google_download_display(self,message):
        """Parse exact GB progress independently from weighted workflow %."""
        if "| DOWNLOAD |" in message:
            match=re.search(
                r"([0-9.]+)\s*GB\s*/\s*([0-9.]+)\s*GB\s*\(([0-9.]+)%\)",
                message)
            if match:
                downloaded,total,pct=map(float,match.groups())
                self.google_download_value.set(max(0,min(100,pct)))
                speed=re.search(r"([0-9.]+)\s*MB/s",message)
                eta=re.search(r"ETA\s+([0-9]+m\s*[0-9]+s)",message)
                tile=re.search(r"TILE\s+([0-9]+/[0-9]+)",message)
                label=tile.group(1) if tile else "1/1"
                self.google_download_stage.set(
                    f"GOOGLE TILE {label} · {pct:.1f}%")
                fields=[f"{downloaded:.3f} / {total:.3f} GB"]
                if speed:fields.append(f"{speed.group(1)} MB/s")
                if eta:fields.append(f"ETA {eta.group(1).replace(' ','')}")
                self.google_download_detail.set("    |    ".join(fields))
                return
        if "| EXTRACT |" in message:
            pct=re.search(r"([0-9.]+)% file",message)
            self.google_download_stage.set(
                "GOOGLE · ekstraksi footprint "
                +(pct.group(1)+"%" if pct else "berjalan"))
            self.google_download_detail.set(message.split("| EXTRACT |",1)[-1].strip()[:130])
        elif "| CACHE HIT |" in message:
            self.google_download_value.set(100)
            self.google_download_stage.set("GOOGLE · cache ditemukan")
            self.google_download_detail.set(message.split("| CACHE HIT |",1)[-1].strip()[:130])
        elif "| CACHE SAVED |" in message:
            self.google_download_value.set(100)
            self.google_download_stage.set("GOOGLE · unduhan tersimpan")
            self.google_download_detail.set(message.split("| CACHE SAVED |",1)[-1].strip()[:130])
        elif "GOOGLE" in message.upper() and "| CONNECT " in message:
            self.google_download_stage.set("GOOGLE · menyambungkan ke server")
        elif "Google Buildings | fase" in message:
            self.google_download_stage.set("GOOGLE · "+message.split(":",1)[0].replace("Google Buildings |","").strip())
        elif "Google Buildings | tile " in message and "DONE" in message:
            self.google_download_value.set(100)
            self.google_download_stage.set("GOOGLE · tile selesai")

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
            try:
                point_limit=max(30,min(2500,int(self.target_points.get())))
                route_limit=max(30,min(2500,int(self.target_routes.get())))
                detail_limit=max(1,min(100,int(self.max_detail_sheets.get())))
                overlap=max(0,min(20,float(self.sheet_overlap_pct.get())))/100.0
            except (ValueError,tk.TclError):
                messagebox.showerror("Pengaturan sheet tidak valid",
                                     "Periksa nilai target titik, ruas, maksimum sheet, dan overlap.")
                return
            # Source-authoritative plotting only when HP georegistration
            # proves this KML actually belongs to the supplied CAD template.
            from reference_sheets import reference_sheet_extents
            exact=(reference_sheet_extents(self.points,bb)
                   if self.cad_reference_style.get() else None)
            if exact:
                sheets=exact
                report={"details":4,"method":"CAD_SOURCE_2018_5_SHEET",
                        "sheet_workload":[],"warnings":[]}
            else:
                sheets,report=plan_sheets(
                    self.lines,self.points,bb,max_details=detail_limit,
                    target_points=point_limit,target_lines=route_limit,
                    overlap=overlap)
            self._planned_sheets=sheets
            self._sheet_report=report
            self.sheet.configure(values=[
                f"{i+1:02d} - {entry[0]}" for i,entry in enumerate(sheets)
            ])
            self.sheet.current(0)
            self._sheet_view=None
            self.plan_label.set(
                f"{len(sheets)} sheet: 1 Overview + {report['details']} Detail\n"
                f"{'CAD Source · 5 lembar' if exact else 'Network-aware'} · overlap {overlap*100:.1f}%\n"
                f"Target {point_limit} titik / {route_limit} ruas · maks. {detail_limit} detail"
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
        """Stage-based weighted progress, with actual byte fraction for Google tiles."""
        if message.startswith("OSM tile"):
            match=re.search(r"tile\s+(\d+)\s*/\s*(\d+)",message)
            if match:
                done,total=map(int,match.groups())
                return 5+58*done/max(total,1)
            return 10
        if message.startswith("OSM"):
            return 8
        if message.startswith("Google Buildings"):
            tile=re.search(r"TILE\s+(\d+)\s*/\s*(\d+)",message)
            current,total=(int(tile.group(1)),int(tile.group(2))) if tile else (1,1)
            current=max(1,min(current,total))
            if "| DOWNLOAD |" in message:
                pct=re.search(r"\((\d+(?:\.\d+)?)%\)",message)
                fraction=float(pct.group(1))/100 if pct else 0.0
                return 74+19*((current-1+.75*fraction)/max(1,total))
            if "| CONNECT " in message or "| RETRY " in message:
                return 74+19*(current-1)/max(1,total)
            if "| CACHE HIT |" in message or "| CACHE SAVED |" in message:
                return 74+19*(current-1+.75)/max(1,total)
            if "| EXTRACT " in message or "| EXTRACT |" in message:
                pct=re.search(r"(\d+(?:\.\d+)?)% file",message)
                fraction=float(pct.group(1))/100 if pct else 0
                return 74+19*((current-1+.75+.25*fraction)/max(1,total))
            if "| EXTRACT DONE |" in message or ("DONE" in message and "tile " in message):
                return 74+19*current/max(1,total)
            if "fase 1/4" in message:return 66
            if "fase 2/4" in message:return 70
            if "fase 3/4" in message:return 74
            if "fase 4/4" in message:return 93
            return 72
        return 5

    def _progress(self,message,revision):
        if revision!=self._revision or not self._running:
            return
        self._record_progress(self._stage_percentage(message),message)

    def choose_google_cache(self):
        """Choose persistent cache drive before a potentially multi-GB download."""
        if self._running or self._osm_loading:
            messagebox.showwarning("Cache sedang dipakai",
                                   "Tunggu pekerjaan selesai sebelum pindah folder cache.")
            return
        chosen=filedialog.askdirectory(
            title="Pilih folder Google Open Buildings Cache (butuh ruang beberapa GB)",
            initialdir=self._google_cache_dir if os.path.isdir(self._google_cache_dir) else os.path.expanduser("~"))
        if not chosen:
            return
        try:
            os.makedirs(chosen,exist_ok=True)
            self._google_cache_dir=os.path.abspath(chosen)
            self.cache_dir_text.set("Cache Google: "+self._google_cache_dir)
            os.makedirs(os.path.dirname(self._cache_settings),exist_ok=True)
            with open(self._cache_settings,"w",encoding="utf-8") as output:
                json.dump({"google_cache_dir":self._google_cache_dir},output)
            self.status.set("Lokasi Google cache disimpan: "+self._google_cache_dir)
        except OSError as exc:
            messagebox.showerror("Folder Cache",str(exc))

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
        self._last_download_logged=-1
        self.progress_log.delete(0,"end")
        self.google_download_value.set(0)
        self.google_download_stage.set("GOOGLE · menunggu OSM selesai")
        self.google_download_detail.set("0.000 GB diunduh · menunggu katalog")
        self._show_progress_banner()
        self.osm_button.configure(state="disabled",text="Mengambil OSM + Google...")
        self._update_generate_button()
        self._record_progress(1,"Mulai OSM → Google (disk cache + resume) → Merge → Sheet Planning. Generate terkunci.")

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
                self.root.after(0,lambda data=osm:self._osm_intermediate(revision,data))
            except Exception as exc:
                osm_error=str(exc)
                progress("OSM: gagal setelah fallback, tetap memeriksa Google")
            try:
                google=acquire_google(bb,progress=progress,cache_dir=self._google_cache_dir)
            except Exception as exc:
                google={"polygons":[],"status":"unavailable","reason":str(exc)}
            try:
                self.root.after(0,lambda:self._acquisition_done(
                    revision,osm,google,osm_error))
            except RuntimeError:
                pass
        threading.Thread(target=worker,daemon=True).start()

    def _osm_intermediate(self,revision,osm):
        """Show acquired roads/OSM buildings while Google downloads gigabytes."""
        if revision!=self._revision or not self._running:
            return
        self._raw_osm=osm
        self._apply_sources()
        self.progress_text.set(
            "OSM siap: {} jalan, {} bangunan. Google masih mengunduh/scan cache. Generate terkunci.".format(
                len(osm.get("roads",[])),len(osm.get("buildings",[]))))

    def _acquisition_done(self,revision,osm,google,osm_error):
        # Mark source workers finished before re-enabling any output action.
        # Keep export disabled until merge and auto-pagination reach 100%.
        self._osm_loading=False
        if revision!=self._revision:
            self._running=False
            self.osm_button.configure(state="normal",
                                      text="Ambil / gunakan cache OSM + Google")
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
        if self._google_status!="ready":
            detail+=f"; Google {self._google_status}"
        if osm_error:
            detail+="; OSM gagal: "+osm_error[:75]
        # 100% is workflow completion, not proof of 100% Google coverage.
        self._record_progress(100,"Job selesai · "+detail)
        if google.get("status")=="ready":
            self.google_download_value.set(100)
            self.google_download_stage.set("GOOGLE · footprint diproses")
            self.google_download_detail.set(
                f"{len(google.get('polygons',[])):,} footprint Google · tile tersimpan di cache")
        elif google.get("status")=="partial":
            self.google_download_stage.set("GOOGLE · parsial, cek log")
        else:
            self.google_download_stage.set("GOOGLE · tidak lengkap")
            self.google_download_detail.set((google.get("reason") or "Tidak ada footprint Google")[:130])
        self._running=False
        self.osm_button.configure(state="normal",
                                  text="Ambil / gunakan cache OSM + Google")
        self._update_generate_button()
        if not roads and not buildings:
            messagebox.showwarning("Basemap belum lengkap",
                "Job selesai tanpa data jalan/bangunan. Data input KML/KMZ tetap tersedia.\n\n"
                +str(osm_error or reason)[:350]+
                "\n\nGenerate diaktifkan kembali; PDF akan memperingatkan jika basemap tidak lengkap.")

    def export(self):
        gate=getattr(self.root,"_pbs_auth_gate",None)
        if gate is not None and not gate.session:
            messagebox.showerror("PBS ID", "Sesi PBS Central tidak aktif. Login diperlukan.")
            return
        if self._running or self._osm_loading or self._footprint_loading or self._planning:
            messagebox.showwarning("Export terkunci",
                "Tunggu akuisisi OSM/Google dan perhitungan sheet selesai.")
            return
        if self.cad_reference_style.get() and not has_exact_template():
            messagebox.showerror(
                "Template CAD asli tidak lengkap",
                "Mode CAD Reference membutuhkan kedua file sumber di folder "
                "template, di sebelah PBS_NRP_Generator.exe:\n\n"
                "ABD St.Lemah Abang Phase 1 Simpangan.dxf\n"
                "ABD St.Lemah Abang Phase 1 Simpangan.pdf\n\n"
                "Ekspor dihentikan supaya simbol asli tidak diam-diam "
                "diganti bentuk rekonstruksi. Ekstrak ZIP portable lengkap.")
            return
        proceed,restore_dwg=self.dwg_preflight()
        if not proceed:
            return
        if not self._planned_sheets and (self.lines or self.points):
            self._rebuild_sheet_plan()
        old_sheets=base_app.sheets_for
        original=(self.lines,self.points,self.osm)
        self.lines,self.points,self.osm=apply_presentation(*original,self._layer_options())
        # Metadata only, never modify the imported KML/Google records.
        self.osm["_project_title"]=os.path.splitext(
            os.path.basename(self.path.get() or "PBS NETWORK ROUTE PLAN"))[0]
        self.osm["_cad_reference_style"]=bool(self.cad_reference_style.get())
        try:
            # Same layer settings on preview, PDF and DXF.
            base_app.sheets_for=lambda _bbox:list(self._planned_sheets)
            super().export()
        finally:
            base_app.sheets_for=old_sheets
            self.lines,self.points,self.osm=original
            if restore_dwg:
                self.want_dwg.set(True)


if __name__=="__main__":
    from pbs_login_gate import start_gated
    root=tk.Tk()
    start_gated(root,ResponsiveNRP)
    root.mainloop()
