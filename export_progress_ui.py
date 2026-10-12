"""Responsive tkinter export progress dialog, queue-driven and nonblocking.

Worker thread NEVER reads/writes Tk objects. The dialog remains responsive even
while reportlab, ezdxf and the separately installed ODA converter do heavy work.
"""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from export_worker import export_job


class ExportProgressDialog:
    def __init__(self,root,config,on_finish=None):
        self.root=root
        self.config=config
        self.on_finish=on_finish
        self.events=queue.Queue()
        self.started=time.monotonic()
        self.done=False
        self.last_percent=0.
        self.result=None
        self.error=None
        self.window=tk.Toplevel(root)
        self.window.title("PBS NRP · Detail Progress Generate PDF / DXF / DWG")
        self.window.resizable(True,True)
        self.window.minsize(570,395)
        self.window.geometry(self._center(700,485))
        self.window.transient(root)
        self.window.protocol("WM_DELETE_WINDOW",self._close)
        self._make_widgets()
        # Popup appears before heavy worker starts. Do not call root.update()
        # or add a nested GUI event loop.
        self.root.after(75,self._start)
        self.root.after(130,self._poll)

    def _center(self,w,h):
        self.root.update_idletasks()
        screen_w=self.root.winfo_screenwidth()
        screen_h=self.root.winfo_screenheight()
        x=max(0,(screen_w-w)//2)
        y=max(0,(screen_h-h)//2)
        return f"{w}x{h}+{x}+{y}"

    def _make_widgets(self):
        content=ttk.Frame(self.window,padding=16)
        content.pack(fill="both",expand=True)
        ttk.Label(content,text="Generate Network Route Plan",
                  font=("Segoe UI",14,"bold")).pack(anchor="w")
        ttk.Label(content,text=f"{len(self.config['sheets'])} sheet A3 · "
                  f"{len(self.config['lines']):,} jalur · "
                  f"{len(self.config['points']):,} titik · "
                  f"{len((self.config['osm'] or {}).get('buildings',[])):,} bangunan",
                  font=("Segoe UI",9)).pack(anchor="w",pady=(2,13))
        self.stage=tk.StringVar(value="Menyiapkan pekerjaan...")
        ttk.Label(content,textvariable=self.stage,
                  font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.pct=tk.DoubleVar(value=0)
        ttk.Progressbar(content,mode="determinate",maximum=100,
                        variable=self.pct).pack(fill="x",pady=(6,4))
        row=ttk.Frame(content)
        row.pack(fill="x",pady=(0,8))
        self.progress_text=tk.StringVar(value="0% · menunggu worker")
        self.elapsed_text=tk.StringVar(value="Waktu berjalan: 00:00")
        ttk.Label(row,textvariable=self.progress_text).pack(side="left")
        ttk.Label(row,textvariable=self.elapsed_text).pack(side="right")
        ttk.Label(content,text="Aktivitas ekspor (diperbarui otomatis)",
                  font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(7,3))
        logs=ttk.Frame(content)
        logs.pack(fill="both",expand=True)
        self.log=tk.Text(logs,height=11,state="disabled",wrap="word",
                         font=("Consolas",9),background="#f6f8fa")
        sc=ttk.Scrollbar(logs,command=self.log.yview,orient="vertical")
        self.log.configure(yscrollcommand=sc.set)
        sc.pack(side="right",fill="y")
        self.log.pack(side="left",fill="both",expand=True)
        self.tip=tk.StringVar(value="PDF → DXF → DWG. Jangan tutup aplikasi saat file dibuat.")
        ttk.Label(content,textvariable=self.tip,wraplength=660,
                  foreground="#506377").pack(anchor="w",pady=(9,6))
        buttons=ttk.Frame(content)
        buttons.pack(fill="x")
        self.open_button=ttk.Button(buttons,text="Buka Folder Output",
                                    command=self._open_folder,state="disabled")
        self.open_button.pack(side="left")
        self.close_button=ttk.Button(buttons,text="Tutup",command=self._close,
                                     state="disabled")
        self.close_button.pack(side="right")
        self._append("Job dibuat. GUI tetap aktif selama proses.")

    def _append(self,text):
        elapsed=int(time.monotonic()-self.started)
        line=f"[{elapsed//60:02d}:{elapsed%60:02d}] {text}\n"
        self.log.configure(state="normal")
        self.log.insert("end",line)
        # Retain a bounded log rather than allocating unlimited Tk text.
        if int(self.log.index("end-1c").split(".")[0])>350:
            self.log.delete("1.0","80.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start(self):
        if self.done or not self.window.winfo_exists():
            return
        def emit(percent,stage,detail):
            # Only Queue writes in background, never self.window or Tk vars.
            self.events.put(("progress",float(percent),str(stage),str(detail)))
        def runner():
            try:
                result=export_job(emit=emit,**self.config)
                self.events.put(("done",result))
            except BaseException as error:
                self.events.put(("error",str(error)))
        threading.Thread(target=runner,name="NRP-Export-Worker",daemon=True).start()

    def _poll(self):
        if not self.window.winfo_exists():
            return
        while True:
            try:
                event=self.events.get_nowait()
            except queue.Empty:
                break
            if event[0]=="progress":
                _,percent,stage,detail=event
                self.last_percent=max(self.last_percent,max(0,min(100,percent)))
                self.pct.set(self.last_percent)
                self.stage.set(stage)
                self.progress_text.set(f"{self.last_percent:.0f}% · {detail[:95]}")
                self._append(f"{self.last_percent:3.0f}% {stage} — {detail}")
            elif event[0]=="done":
                self._finish(event[1],None)
            elif event[0]=="error":
                self._finish(None,event[1])
        elapsed=int(time.monotonic()-self.started)
        self.elapsed_text.set(f"Waktu berjalan: {elapsed//60:02d}:{elapsed%60:02d}")
        if not self.done:
            # Pulse a live timestamp even when ODA does not emit progress.
            self.root.after(140,self._poll)

    def _finish(self,result,error):
        if self.done:
            return
        self.done=True
        self.result=result
        self.error=error
        self.open_button.configure(state="normal")
        self.close_button.configure(state="normal")
        if error:
            self.stage.set("Ekspor gagal — lihat log")
            self.tip.set("Sebagian file mungkin sudah selesai. Periksa folder dan log.")
            self._append("ERROR: "+error)
        elif result.warning:
            self.stage.set("Selesai dengan peringatan DWG")
            self.tip.set("PDF dan DXF berhasil. DWG gagal; periksa log ODA.")
            self._append("PERINGATAN: "+result.warning)
        else:
            self.stage.set("Selesai — semua file berhasil")
            self.tip.set("PDF/DXF/DWG selesai. File tersedia pada folder output.")
            self._append("SUKSES: "+", ".join(os.path.basename(p) for p in result.files))
        if self.on_finish:
            self.on_finish(result,error)

    def _open_folder(self):
        folder=self.config["folder"]
        try:
            os.startfile(folder)  # Windows only, called on GUI thread
        except (OSError,AttributeError):
            messagebox.showinfo("Folder Output",folder,parent=self.window)

    def _close(self):
        if not self.done:
            messagebox.showinfo(
                "Ekspor sedang berjalan",
                "Pekerjaan PDF/DXF/DWG masih berlangsung di background.\n"
                "Jendela ini akan dapat ditutup setelah proses selesai.",
                parent=self.window)
            return
        self.window.destroy()
