"""Login and sign-up screen: branded panel on the left, form on the right."""
import sqlite3
import tkinter as tk
from tkinter import ttk

from . import ui_kit as ui
from .config import APP_NAME, CURRENCIES, resource_path
from .security import SessionStore

_logos = {}


def logo_image(root, subsample):
    """Cached, scaled logo PhotoImage, or None if the icon file is missing."""
    if subsample not in _logos:
        try:
            img = tk.PhotoImage(master=root, file=resource_path("assets", "icon.png"))
            _logos[subsample] = img.subsample(subsample) if subsample > 1 else img
        except tk.TclError:
            _logos[subsample] = None
    return _logos[subsample]


class AuthView(tk.Frame):
    def __init__(self, root, db, on_login):
        super().__init__(root, bg=ui.C["bg"])
        self.db = db
        self.on_login = on_login
        self.pack(fill="both", expand=True)
        self.show_login()

    # ---- layout shell shared by both screens
    def _shell(self):
        for w in self.winfo_children():
            w.destroy()
        brand = tk.Frame(self, bg=ui.C["side"], width=380)
        brand.pack(side="left", fill="y")
        brand.pack_propagate(False)
        inner = tk.Frame(brand, bg=ui.C["side"])
        inner.place(relx=0.5, rely=0.46, anchor="center")
        logo = logo_image(self, 4)
        if logo:
            tk.Label(inner, image=logo, bg=ui.C["side"], bd=0).pack()
        tk.Label(inner, text="FST", font=ui.font(30, True), bg=ui.C["side"],
                 fg=ui.C["side_title"]).pack(pady=(12, 0))
        tk.Label(inner, text="Finance Management", font=ui.font(12),
                 bg=ui.C["side"], fg=ui.C["side_fg"]).pack()
        for line in ("Sales & purchase invoices", "Customers and suppliers",
                     "Inventory with low-stock alerts", "Quotations and reports"):
            tk.Label(inner, text="●  " + line, font=ui.font(10), bg=ui.C["side"],
                     fg=ui.C["side_fg"]).pack(anchor="w", pady=3, padx=30)
        form_side = tk.Frame(self, bg=ui.C["bg"])
        form_side.pack(side="left", fill="both", expand=True)
        self.card = ui.card(form_side, pad=34)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        return self.card

    # ---- login
    def show_login(self):
        card = self._shell()
        tk.Label(card, text="Welcome back", font=ui.font(18, True), bg=ui.C["card"],
                 fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(card, text="Sign in to manage your business", font=ui.font(10),
                 bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(2, 18))

        wrap, self.email = ui.field(card, "Email", width=36)
        wrap.pack(fill="x", pady=6)

        pw_wrap = tk.Frame(card, bg=ui.C["card"])
        pw_wrap.pack(fill="x", pady=6)
        tk.Label(pw_wrap, text="Password", font=ui.font(9), bg=ui.C["card"],
                 fg=ui.C["muted"], anchor="w").pack(fill="x")
        row = tk.Frame(pw_wrap, bg=ui.C["card"])
        row.pack(fill="x")
        self.password = tk.Entry(row, show="•", font=ui.font(10), bg=ui.C["entry"],
                                 fg=ui.C["fg"], insertbackground=ui.C["fg"], relief="flat",
                                 highlightthickness=1, highlightbackground=ui.C["border"],
                                 highlightcolor=ui.C["accent"], width=30)
        self.password.pack(side="left", fill="x", expand=True, ipady=6)
        self.show_pw = tk.BooleanVar(value=False)
        tk.Checkbutton(row, text="Show", variable=self.show_pw, bg=ui.C["card"], fg=ui.C["muted"],
                       selectcolor=ui.C["card"], activebackground=ui.C["card"],
                       command=lambda: self.password.configure(show="" if self.show_pw.get() else "•")
                       ).pack(side="left", padx=(8, 0))

        self.remember = tk.BooleanVar(value=False)
        tk.Checkbutton(card, text="Remember password on this computer", variable=self.remember,
                       bg=ui.C["card"], fg=ui.C["fg"], selectcolor=ui.C["entry"],
                       activebackground=ui.C["card"], font=ui.font(9)
                       ).pack(anchor="w", pady=(12, 16))

        ui.Button(card, "Sign in", self.do_login, "primary", bg=ui.C["card"]).pack(fill="x", pady=4)
        ui.Button(card, "Create a new account", self.show_signup, "secondary",
                  bg=ui.C["card"]).pack(fill="x", pady=4)

        saved = SessionStore.load()
        if saved:
            ui.set_entry(self.email, saved[0])
            ui.set_entry(self.password, saved[1])
            self.remember.set(True)
        self.password.bind("<Return>", lambda e: self.do_login())
        self.email.bind("<Return>", lambda e: self.do_login())
        self.email.focus_set()

    def do_login(self):
        email, pw = self.email.get().strip(), self.password.get()
        if not email or not pw:
            ui.error("Please enter both email and password.")
            return
        user = self.db.authenticate(email, pw)
        if not user:
            ui.error("Invalid email or password.")
            return
        if self.remember.get():
            SessionStore.save(email, pw)
        else:
            SessionStore.clear()
        self.on_login(user)

    # ---- sign up
    def show_signup(self):
        card = self._shell()
        tk.Label(card, text="Create your account", font=ui.font(18, True), bg=ui.C["card"],
                 fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(card, text="Fields marked * are required", font=ui.font(10),
                 bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(2, 14))

        grid = tk.Frame(card, bg=ui.C["card"])
        grid.pack()
        self.su = {}
        specs = [
            ("first_name", "First name *", None), ("last_name", "Last name (optional)", None),
            ("business_name", "Business name *", None), ("email", "Email *", None),
            ("phone", "Phone number", None), ("currency", "Currency *", None),
            ("password", "Password *", "•"), ("confirm", "Confirm password *", "•"),
        ]
        for i, (key, label, show) in enumerate(specs):
            r, c = divmod(i, 2)
            if key == "currency":
                box = tk.Frame(grid, bg=ui.C["card"])
                tk.Label(box, text=label, font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"],
                         anchor="w").pack(fill="x")
                cb = ttk.Combobox(box, values=CURRENCIES, state="readonly", width=32, font=ui.font(10))
                cb.set("PKR")
                cb.pack(fill="x", ipady=4)
                self.su[key] = cb
            else:
                box, entry = ui.field(grid, label, width=34, show=show)
                self.su[key] = entry
            box.grid(row=r, column=c, padx=10, pady=6, sticky="ew")

        btns = tk.Frame(card, bg=ui.C["card"])
        btns.pack(fill="x", pady=(18, 0))
        ui.Button(btns, "Back to sign in", self.show_login, "ghost", bg=ui.C["card"]).pack(side="left")
        ui.Button(btns, "Create account", self.do_signup, "primary", bg=ui.C["card"]).pack(side="right")

    def do_signup(self):
        v = {k: w.get().strip() for k, w in self.su.items()}
        if not all([v["first_name"], v["business_name"], v["email"], v["currency"],
                    v["password"], v["confirm"]]):
            ui.error("Please fill in all required fields (marked *).")
            return
        if "@" not in v["email"] or "." not in v["email"].split("@")[-1]:
            ui.error("Please enter a valid email address.")
            return
        if len(v["password"]) < 6:
            ui.error("Password must be at least 6 characters.")
            return
        if v["password"] != v["confirm"]:
            ui.error("Passwords do not match.")
            return
        try:
            self.db.create_user(v)
        except sqlite3.IntegrityError:
            ui.error("An account with this email already exists.")
            return
        ui.info("Account created. Please sign in.")
        self.show_login()
        ui.set_entry(self.email, v["email"])
