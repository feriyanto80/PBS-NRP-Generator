"""PBS NRP gated startup and nonblocking Central Identity login dialog.

No offline bypass and no hard-coded accounts. Credentials only go to
https://id.pbsgroup.id/api over Python's standard TLS-verifying HTTPS stack.
"""
import threading
import tkinter as tk
from tkinter import ttk,messagebox
from pbs_identity import (
    IdentityClient,IdentityError,IdentityRejected,IdentityNetworkError,
    save_session,load_session,clear_session,last_username,
    REVALIDATE_MINUTES,APP_CODE,
)


class LoginGate(tk.Toplevel):
    def __init__(self,root):
        super().__init__(root)
        self.root=root
        self.client=IdentityClient()
        self.result=None
        self.pending=False
        self.title("PBS NRP Generator — PBS Central Identity")
        self.geometry("480x355")
        self.resizable(False,False)
        self.protocol("WM_DELETE_WINDOW",self._cancel)
        self.username=tk.StringVar(value=last_username())
        self.password=tk.StringVar()
        self.remember=tk.BooleanVar(value=True)
        self.feedback=tk.StringVar(value="Masukkan username dan password PBS ID.")
        self._build()
        self.grab_set()
        self.after(160,self._try_saved)

    def _build(self):
        self.configure(bg="#f5f9fe")
        area=ttk.Frame(self,padding=27)
        area.pack(fill="both",expand=True)
        ttk.Label(area,text="PBS Network Route Plan Generator",
                  font=("Segoe UI",16,"bold")).pack(anchor="w")
        ttk.Label(area,text="PBS Central Identity · id.pbsgroup.id",
                  foreground="#536c81").pack(anchor="w",pady=(3,18))
        ttk.Label(area,text="Username").pack(anchor="w")
        name=ttk.Entry(area,textvariable=self.username)
        name.pack(fill="x",pady=(3,10))
        ttk.Label(area,text="Password").pack(anchor="w")
        secret=ttk.Entry(area,textvariable=self.password,show="●")
        secret.pack(fill="x",pady=(3,8))
        secret.bind("<Return>",lambda e:self._login())
        ttk.Checkbutton(area,text="Ingat sesi pada perangkat ini (Windows DPAPI)",
                        variable=self.remember).pack(anchor="w",pady=(0,10))
        self.button=ttk.Button(area,text="LOGIN PBS ID",command=self._login)
        self.button.pack(fill="x",ipady=4)
        ttk.Label(area,textvariable=self.feedback,wraplength=415,
                  foreground="#31516e").pack(anchor="w",pady=(12,0))
        ttk.Label(area,text="Client: PBS_NRP_DESKTOP · Online authentication required",
                  foreground="#657789",font=("Segoe UI",8)).pack(anchor="w",pady=(8,0))
        if name.get():
            secret.focus_set()
        else:
            name.focus_set()

    def _busy(self,busy,text):
        self.pending=busy
        self.button.configure(state="disabled" if busy else "normal")
        self.feedback.set(text)

    def _start(self,task,reason):
        if self.pending:
            return
        self._busy(True,reason)
        def worker():
            value=None
            error=None
            try:
                value=task()
            except IdentityError as exc:
                error=str(exc)
            except Exception as exc:
                error="Autentikasi gagal: "+type(exc).__name__
            try:
                self.after(0,lambda:self._finish(value,error))
            except (tk.TclError,RuntimeError):
                pass
        threading.Thread(target=worker,daemon=True).start()

    def _try_saved(self):
        existing=load_session()
        if existing:
            self._start(lambda:self.client.validate(existing),
                        "Memvalidasi sesi PBS ID secara online...")

    def _login(self):
        username=self.username.get().strip()
        password=self.password.get()
        if not username or not password:
            messagebox.showwarning("PBS ID","Username dan password wajib diisi",parent=self)
            return
        self._start(lambda:self.client.login(username,password),
                    "Menghubungkan PBS Central Identity...")
        # Do not retain password in widget following submission.
        self.password.set("")

    def _finish(self,session,error):
        if not self.winfo_exists():
            return
        self._busy(False,"Masukkan username dan password PBS ID.")
        if error:
            clear_session()
            self.feedback.set("PBS ID: "+error[:200])
            return
        self.result=session
        if self.remember.get():
            try:
                save_session(session)
            except (OSError,RuntimeError) as exc:
                self.feedback.set("Sesi aktif tanpa disimpan: "+str(exc)[:180])
        else:
            clear_session()
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result=None
        self.grab_release()
        self.destroy()


def authenticate(root):
    """Blocking UI, with all networking in background worker threads."""
    root.withdraw()
    dialog=LoginGate(root)
    root.wait_window(dialog)
    return dialog.result
