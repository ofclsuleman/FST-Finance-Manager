"""Sign-in, sign-up and forgot-password screens.

* Passwords are a 4-digit PIN, for example 4821.
* "Keep me signed in" stores a random session token on this computer, so the
  app opens straight to the dashboard next time. Signing out ends the session.
* Forgot password: answer the recovery question you chose at sign-up, then set
  a new PIN. This needs no email server and works offline.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk

from . import ui_kit as ui
from .config import CURRENCIES, resource_path
from .security import PIN_LENGTH, SECURITY_QUESTIONS, SessionFile, is_valid_pin

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


PIN_HINT = f"{PIN_LENGTH} digits, for example 4821"


class AuthView(tk.Frame):
    def __init__(self, root, db, on_login):
        super().__init__(root, bg=ui.C["bg"])
        self.db = db
        self.on_login = on_login
        self.pack(fill="both", expand=True)
        self.show_login()

    # ------------------------------------------------------------ layout
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
        tk.Label(inner, text="FST", font=ui.font(30, True), bg=ui.C["side"], fg=ui.C["side_title"]).pack(pady=(12, 0))
        tk.Label(inner, text="Finance Management", font=ui.font(12), bg=ui.C["side"], fg=ui.C["side_fg"]).pack()
        for line in ("Sales & purchase invoices", "Customers and suppliers", "Double-entry ledger",
                     "Inventory with low-stock alerts", "Financial statements"):
            tk.Label(inner, text="●  " + line, font=ui.font(10), bg=ui.C["side"], fg=ui.C["side_fg"]).pack(
                anchor="w", pady=3, padx=30)
        side = tk.Frame(self, bg=ui.C["bg"])
        side.pack(side="left", fill="both", expand=True)
        self.card = ui.card(side, pad=34)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        return self.card

    def _pin_field(self, parent, label, bg):
        wrap = tk.Frame(parent, bg=bg)
        tk.Label(wrap, text=label, font=ui.font(9), bg=bg, fg=ui.C["muted"], anchor="w").pack(fill="x")
        row = tk.Frame(wrap, bg=bg)
        row.pack(fill="x")
        check = row.register(lambda new: new == "" or (new.isdigit() and new.isascii() and len(new) <= PIN_LENGTH))
        entry = tk.Entry(row, show="•", font=ui.font(12), bg=ui.C["entry"], fg=ui.C["fg"],
                         insertbackground=ui.C["fg"], relief="flat", highlightthickness=1,
                         highlightbackground=ui.C["border"], highlightcolor=ui.C["accent"], width=12,
                         justify="center", validate="key", validatecommand=(check, "%P"))
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        show = tk.BooleanVar(value=False)
        tk.Checkbutton(row, text="Show", variable=show, bg=bg, fg=ui.C["muted"], selectcolor=bg,
                       activebackground=bg, command=lambda: entry.configure(show="" if show.get() else "•")
                       ).pack(side="left", padx=(8, 0))
        return wrap, entry

    # ------------------------------------------------------------ sign in
    def show_login(self):
        card = self._shell()
        bg = ui.C["card"]
        tk.Label(card, text="Welcome back", font=ui.font(18, True), bg=bg, fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(card, text="Sign in to manage your business", font=ui.font(10), bg=bg, fg=ui.C["muted"]
                 ).pack(anchor="w", pady=(2, 18))
        wrap, self.email = ui.field(card, "Email", width=34, bg=bg)
        wrap.pack(fill="x", pady=6)
        pw_wrap, self.pin = self._pin_field(card, f"Password ({PIN_LENGTH} digits)", bg)
        pw_wrap.pack(fill="x", pady=6)
        self.keep = tk.BooleanVar(value=True)
        tk.Checkbutton(card, text="Keep me signed in on this computer", variable=self.keep, bg=bg, fg=ui.C["fg"],
                       selectcolor=ui.C["entry"], activebackground=bg, font=ui.font(9)
                       ).pack(anchor="w", pady=(12, 14))
        ui.Button(card, "Sign in", self.do_login, "primary", bg=bg).pack(fill="x", pady=4)
        ui.Button(card, "Create a new account", self.show_signup, "secondary", bg=bg).pack(fill="x", pady=4)
        links = tk.Frame(card, bg=bg)
        links.pack(fill="x", pady=(10, 0))
        ui.Button(links, "Forgot password?", self.show_forgot, "ghost", bg=bg).pack(side="right")
        self.email.bind("<Return>", lambda e: self.do_login())
        self.pin.bind("<Return>", lambda e: self.do_login())
        self.email.focus_set()

    def do_login(self):
        email, pin = self.email.get().strip(), self.pin.get().strip()
        if not email or not pin:
            ui.error("Please enter your email and password.")
            return
        user = self.db.authenticate(email, pin)
        if not user:
            ui.error("Invalid email or password.")
            return
        if self.keep.get():
            SessionFile.save(self.db.create_session(user["id"]))
        else:
            SessionFile.clear()
        self.on_login(user)

    # ------------------------------------------------------------ sign up
    def show_signup(self):
        card = self._shell()
        bg = ui.C["card"]
        tk.Label(card, text="Create your account", font=ui.font(18, True), bg=bg, fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(card, text="Fields marked * are required", font=ui.font(10), bg=bg, fg=ui.C["muted"]
                 ).pack(anchor="w", pady=(2, 14))
        grid = tk.Frame(card, bg=bg)
        grid.pack()
        self.su = {}
        specs = [("first_name", "First name *"), ("last_name", "Last name (optional)"),
                 ("business_name", "Business name *"), ("email", "Email *"),
                 ("phone", "Phone number"), ("currency", "Currency *")]
        for i, (key, label) in enumerate(specs):
            r, c = divmod(i, 2)
            if key == "currency":
                box = tk.Frame(grid, bg=bg)
                tk.Label(box, text=label, font=ui.font(9), bg=bg, fg=ui.C["muted"], anchor="w").pack(fill="x")
                cb = ttk.Combobox(box, values=CURRENCIES, state="readonly", width=32, font=ui.font(10))
                cb.set("PKR")
                cb.pack(fill="x", ipady=4)
                self.su[key] = cb
            else:
                box, entry = ui.field(grid, label, width=34, bg=bg)
                self.su[key] = entry
            box.grid(row=r, column=c, padx=10, pady=6, sticky="ew")
        pin_box, self.su["pin"] = self._pin_field(grid, f"Password * ({PIN_HINT})", bg)
        pin_box.grid(row=3, column=0, padx=10, pady=6, sticky="ew")
        conf_box, self.su["confirm"] = self._pin_field(grid, "Confirm password *", bg)
        conf_box.grid(row=3, column=1, padx=10, pady=6, sticky="ew")

        q_box = tk.Frame(grid, bg=bg)
        tk.Label(q_box, text="Recovery question * (used for Forgot password)", font=ui.font(9), bg=bg,
                 fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.su["question"] = ttk.Combobox(q_box, values=SECURITY_QUESTIONS, state="readonly", width=32, font=ui.font(10))
        self.su["question"].set(SECURITY_QUESTIONS[0])
        self.su["question"].pack(fill="x", ipady=4)
        q_box.grid(row=4, column=0, padx=10, pady=6, sticky="ew")
        ans_box, self.su["answer"] = ui.field(grid, "Answer *", width=34, bg=bg)
        ans_box.grid(row=4, column=1, padx=10, pady=6, sticky="ew")

        btns = tk.Frame(card, bg=bg)
        btns.pack(fill="x", pady=(18, 0))
        ui.Button(btns, "Back to sign in", self.show_login, "ghost", bg=bg).pack(side="left")
        ui.Button(btns, "Create account", self.do_signup, "primary", bg=bg).pack(side="right")

    def do_signup(self):
        v = {k: w.get().strip() for k, w in self.su.items()}
        required = ["first_name", "business_name", "email", "currency", "pin", "confirm", "answer"]
        if not all(v[k] for k in required):
            ui.error("Please fill in all required fields (marked *).")
            return
        if "@" not in v["email"] or "." not in v["email"].split("@")[-1]:
            ui.error("Please enter a valid email address.")
            return
        if not is_valid_pin(v["pin"]):
            ui.error(f"Password must be exactly {PIN_LENGTH} digits, for example 4821.")
            return
        if v["pin"] != v["confirm"]:
            ui.error("The two passwords do not match.")
            return
        try:
            self.db.create_user({**v, "password": v["pin"], "question": v["question"], "answer": v["answer"]})
        except sqlite3.IntegrityError:
            ui.error("An account with this email already exists.")
            return
        ui.info("Account created. Please sign in.")
        self.show_login()
        ui.set_entry(self.email, v["email"])

    # ------------------------------------------------------------ forgot password
    def show_forgot(self):
        card = self._shell()
        bg = ui.C["card"]
        tk.Label(card, text="Reset your password", font=ui.font(18, True), bg=bg, fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(card, text="Answer your recovery question, then choose a new 4-digit password.",
                 font=ui.font(10), bg=bg, fg=ui.C["muted"], wraplength=420, justify="left").pack(anchor="w", pady=(2, 14))
        wrap, self.f_email = ui.field(card, "Email of your account", width=36, bg=bg)
        wrap.pack(fill="x", pady=6)
        self.f_question = tk.Label(card, text="", font=ui.font(10, True), bg=bg, fg=ui.C["accent"],
                                   wraplength=420, justify="left")
        self.f_question.pack(anchor="w", pady=(8, 0))
        ans_wrap, self.f_answer = ui.field(card, "Your answer", width=36, bg=bg)
        ans_wrap.pack(fill="x", pady=6)
        new_wrap, self.f_pin = self._pin_field(card, f"New password ({PIN_HINT})", bg)
        new_wrap.pack(fill="x", pady=6)
        conf_wrap, self.f_confirm = self._pin_field(card, "Confirm new password", bg)
        conf_wrap.pack(fill="x", pady=6)
        self._f_user = None

        row = tk.Frame(card, bg=bg)
        row.pack(fill="x", pady=(14, 0))
        ui.Button(row, "Back to sign in", self.show_login, "ghost", bg=bg).pack(side="left")
        ui.Button(row, "Find account", self.forgot_find, "secondary", bg=bg).pack(side="right", padx=4)
        ui.Button(row, "Reset password", self.forgot_reset, "primary", bg=bg).pack(side="right")

    def forgot_find(self):
        user = self.db.find_user_by_email(self.f_email.get())
        if not user:
            ui.error("No account was found with that email.")
            return
        if not user["security_question"]:
            ui.error("This account has no recovery question yet.\n\nSign in with your password, then open "
                     "Settings and save a recovery question. After that, Forgot password will work.")
            return
        self._f_user = user
        self.f_question.configure(text="Question: " + user["security_question"])

    def forgot_reset(self):
        if not self._f_user:
            ui.error("Enter your email and press 'Find account' first.")
            return
        if not self.db.verify_recovery_answer(self._f_user["id"], self.f_answer.get()):
            ui.error("That answer is not correct.")
            return
        pin = self.f_pin.get().strip()
        if not is_valid_pin(pin):
            ui.error(f"New password must be exactly {PIN_LENGTH} digits.")
            return
        if pin != self.f_confirm.get().strip():
            ui.error("The two passwords do not match.")
            return
        self.db.reset_pin(self._f_user["id"], pin)
        SessionFile.clear()
        ui.info("Your password has been reset. Please sign in with the new password.")
        self.show_login()
