"""PBS NRP v1.0.20 login gate. No UI or exports before server authorization.

Derived from supplied Pole40 native PBS ID source protocol, not from HTML
scraping. Session validated online before app starts and every 10 minutes.
On validation failure, hide protected interface and request fresh credentials.
"""
import threading
import tkinter as tk
from tkinter import ttk,messagebox

from pbs_identity import (
    IdentityClient, IdentityError, clear_session, load_session,
    save_session, last_username, REVALIDATE_MINUTES
)


class LoginGate:
    def __init__(self,root,app_type,client=None):
        self.root=root
        self.app_type=app_type
        self.client=client or IdentityClient()
        self.session=None
        self.app=None
        self.working=False
        self.signed_out=False
        self.dialog=None
        self._check_timer=None
        root.withdraw()
        self._dialog()
        self.dialog.after(100,self._try_saved_session)

    def _dialog(self):
        if self.dialog is not None:
            try:
                self.dialog.destroy()
            except tk.TclError:
                pass
        window=tk.Toplevel(self.root)
        window.title("PBS NRP Generator | PBS Central ID")
        # Center over the primary desktop work area (also for laptops/DPI).
        login_w,login_h=520,420
        screen_w,screen_h=window.winfo_screenwidth(),window.winfo_screenheight()
        left=max(0,(screen_w-login_w)//2)
        top=max(0,(screen_h-login_h)//2)
        window.geometry(f"{login_w}x{login_h}+{left}+{top}")
        window.resizable(False,False)
        window.protocol("WM_DELETE_WINDOW",self.root.destroy)
        window.configure(bg="#f0f5fa")
        self.dialog=window
        self.username=tk.StringVar(value=last_username())
        self.password=tk.StringVar()
        self.status=tk.StringVar(value="Username dan password dari id.pbsgroup.id")
        self.remember=tk.BooleanVar(value=True)
        panel=tk.Frame(window,bg="white",padx=25,pady=25)
        panel.pack(fill="both",expand=True,padx=16,pady=16)
        tk.Label(panel,text="PBS NETWORK ROUTE PLAN",font=("Segoe UI",16,"bold"),
                 bg="white",fg="#194c81").pack(anchor="w")
        tk.Label(panel,text="Central Identity · Native Online Authentication",
                 bg="white",fg="#526879").pack(anchor="w",pady=(0,22))
        tk.Label(panel,text="Username",bg="white").pack(anchor="w")
        self.user_entry=ttk.Entry(panel,textvariable=self.username)
        self.user_entry.pack(fill="x",pady=(2,13))
        tk.Label(panel,text="Password",bg="white").pack(anchor="w")
        self.pass_entry=ttk.Entry(panel,textvariable=self.password,show="*")
        self.pass_entry.pack(fill="x",pady=(2,12))
        self.pass_entry.bind("<Return>",lambda _event:self.login())
        ttk.Checkbutton(panel,text="Ingat sesi terenkripsi pada perangkat ini",
                        variable=self.remember).pack(anchor="w",pady=(0,12))
        self.button=ttk.Button(panel,text="LOGIN PBS ID",command=self.login)
        self.button.pack(fill="x",ipady=5)
        tk.Label(panel,textvariable=self.status,bg="white",fg="#a34820",
                 wraplength=450,justify="left").pack(fill="x",pady=(12,0))
        tk.Label(panel,text="Authority: https://id.pbsgroup.id/api\n"
                 "App ID: PBS_NRP_DESKTOP · Memerlukan entitlement NRP",
                 bg="white",fg="#657481",justify="left",
                 font=("Segoe UI",8)).pack(anchor="w",pady=(12,0))
        self.dialog.grab_set()
        self.user_entry.focus_set()

    def _try_saved_session(self):
        saved=load_session()
        if not saved:
            return
        self.status.set("Sesi tersimpan ditemukan · verifikasi online...")
        self._run(lambda:self.client.validate(saved),self._on_verified,
                  "Validasi sesi gagal. Silakan login kembali.")

    def _run(self,action,success,description):
        if self.working:
            return
        self.working=True
        self.button.configure(state="disabled")
        def background():
            try:
                value=action()
                error=None
            except Exception as exc:
                value=None
                error=str(exc)
            try:
                self.root.after(0,lambda:self._finish(value,error,success,description))
            except RuntimeError:
                pass
        threading.Thread(target=background,daemon=True).start()

    def _finish(self,value,error,success,description):
        self.working=False
        if not self.dialog or not self.dialog.winfo_exists():
            return
        self.button.configure(state="normal")
        if error:
            clear_session()
            self.password.set("")
            self.status.set(f"{description}\n{error[:250]}")
            return
        success(value)

    def login(self):
        user=self.username.get().strip()
        password=self.password.get()
        if not user or not password:
            self.status.set("Username dan password wajib diisi.")
            return
        self.status.set("Memverifikasi username, perangkat, dan hak aplikasi...")
        self._run(lambda:self.client.login(user,password),
                  self._on_verified,"Login PBS Central ditolak.")
        # Clear visible field after request is queued. Worker captures its own copy.
        self.password.set("")

    def _on_verified(self,session):
        self.session=session
        if self.remember.get():
            try:
                save_session(session)
            except (OSError,RuntimeError):
                self.status.set("Login berhasil, tetapi sesi tidak tersimpan.")
        else:
            clear_session()
        self._close_dialog()
        if self.app is None:
            self.app=self.app_type(self.root)
        self.root.deiconify()
        # Windows 'zoomed' is true OS maximize (not a guessed geometry).
        # Defer until the responsive widgets finish receiving Configure events.
        self.root.after_idle(self._maximize_main)
        self._install_logout()
        self._schedule_validation()

    def _maximize_main(self):
        try:
            self.root.state("zoomed")
        except tk.TclError:
            try:
                self.root.attributes("-zoomed",True)
            except tk.TclError:
                # Non-Windows Tk: retain usable, centered non-maximized frame.
                self.root.update_idletasks()
                w,h=self.root.winfo_width(),self.root.winfo_height()
                sw,sh=self.root.winfo_screenwidth(),self.root.winfo_screenheight()
                self.root.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}")

    def _install_logout(self):
        if getattr(self.app,"pbs_auth_bar",None) is not None:
            return
        nav=tk.Frame(self.root,bg="#dceaf7")
        nav.pack(fill="x",before=self.app.body if hasattr(self.app,"body") else None)
        name=str(self.session.get("user",{}).get("username",""))[:36]
        tk.Label(nav,text="PBS ID · "+name,bg="#dceaf7",fg="#244c69",
                 font=("Segoe UI",9,"bold")).pack(side="left",padx=12,pady=2)
        tk.Button(nav,text="Logout",command=self.logout,bg="#b84040",
                  fg="white",bd=0,padx=10).pack(side="right",padx=8,pady=2)
        self.app.pbs_auth_bar=nav
        self.app._pbs_auth_gate=self

    def _close_dialog(self):
        if self.dialog:
            try:self.dialog.grab_release()
            except tk.TclError:pass
            self.dialog.destroy()
            self.dialog=None

    def _schedule_validation(self):
        if self._check_timer:
            self.root.after_cancel(self._check_timer)
        self._check_timer=self.root.after(
            REVALIDATE_MINUTES*60*1000,self._revalidate)

    def _revalidate(self):
        if not self.session:
            return
        session=dict(self.session)
        def work():
            try:
                new=self.client.validate(session)
                self.root.after(0,lambda:self._refresh_ok(new))
            except Exception as exc:
                self.root.after(0,lambda:self._lock(str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def _refresh_ok(self,session):
        self.session=session
        try:save_session(session)
        except OSError:pass
        self._schedule_validation()

    def _lock(self,error):
        # Fail closed on network loss / revocation / session expiry.
        self.session=None
        clear_session()
        self.root.withdraw()
        if self.app and hasattr(self.app,"status"):
            self.app.status.set("PBS ID session invalid · application locked")
        self._dialog()
        self.status.set("Sesi perlu diverifikasi lagi: "+str(error)[:220])

    def logout(self):
        if not messagebox.askyesno("Logout PBS ID","Keluar dari sesi PBS NRP Generator?"):
            return
        old=self.session
        self.session=None
        self.root.withdraw()
        clear_session()
        self._dialog()
        self.status.set("Keluar dari PBS ID · silakan login.")
        threading.Thread(target=lambda:self.client.logout(old),daemon=True).start()


def start_gated(root,app_type):
    gate=LoginGate(root,app_type)
    # Keep a strong reference during modal authentication.
    root._pbs_auth_gate=gate
    return gate
