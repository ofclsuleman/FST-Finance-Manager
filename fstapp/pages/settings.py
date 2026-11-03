"""Settings (business profile, numbering, tax, security, backup) and About Us."""
import os
import sqlite3
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
import webbrowser

from .. import ui_kit as ui
from ..auth_view import logo_image
from ..config import APP_NAME, APP_VERSION, CURRENCIES, DATA_DIR, DB_PATH
from ..csv_io import to_float
from ..security import hash_password, verify_password


class SettingsPage:
    def __init__(self, app):
        self.app = app

    def build(self, parent):
        app, db = self.app, self.app.db
        ui.page_header(parent, "Settings", "Business profile, numbering, tax and security."
                       ).pack(fill="x", pady=(0, 10))
        user = db.get_user(app.user["id"])
        cols = tk.Frame(parent, bg=ui.C["bg"])
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1, uniform="s")
        cols.columnconfigure(1, weight=1, uniform="s")

        # --- profile
        prof = ui.card(cols, pad=18)
        prof.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ui.section_label(prof, "Business profile").pack(anchor="w", pady=(0, 10))
        self.p = {}
        for key, label, value in [("first_name", "First name *", user["first_name"]),
                                  ("last_name", "Last name", user["last_name"] or ""),
                                  ("business_name", "Business name *", user["business_name"]),
                                  ("phone", "Phone", user["phone"] or ""),
                                  ("address", "Address", user["address"] or "")]:
            wrap, entry = ui.field(prof, label, width=40, value=value, bg=ui.C["card"])
            wrap.pack(fill="x", pady=4)
            self.p[key] = entry
        cur_wrap = tk.Frame(prof, bg=ui.C["card"])
        cur_wrap.pack(fill="x", pady=4)
        tk.Label(cur_wrap, text="Currency", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.currency = ttk.Combobox(cur_wrap, values=CURRENCIES, state="readonly", font=ui.font(10))
        self.currency.set(user["currency"])
        self.currency.pack(fill="x", ipady=4)
        ui.Button(prof, "Save profile", self.save_profile, "primary", bg=ui.C["card"]).pack(anchor="w", pady=(12, 0))

        # --- numbering & tax
        num = ui.card(cols, pad=18)
        num.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ui.section_label(num, "Invoices, tax and stock").pack(anchor="w", pady=(0, 10))
        self.n = {}
        for key, label in [("invoice_prefix", "Sales invoice prefix"), ("purchase_prefix", "Purchase invoice prefix"),
                           ("quote_prefix", "Quotation prefix"), ("default_tax_rate", "Default tax rate (%)"),
                           ("low_stock_default", "Default reorder level for new products")]:
            wrap, entry = ui.field(num, label, width=30, value=db.get_setting(key, ""), bg=ui.C["card"])
            wrap.pack(fill="x", pady=4)
            self.n[key] = entry
        ui.Button(num, "Save settings", self.save_numbering, "primary", bg=ui.C["card"]).pack(anchor="w", pady=(12, 0))

        # --- security
        sec = ui.card(cols, pad=18)
        sec.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(12, 0))
        ui.section_label(sec, "Change password").pack(anchor="w", pady=(0, 10))
        self.pw = {}
        for key, label in [("current", "Current password"), ("new", "New password (min 6)"), ("confirm", "Confirm new password")]:
            wrap, entry = ui.field(sec, label, width=30, show="•", bg=ui.C["card"])
            wrap.pack(fill="x", pady=4)
            self.pw[key] = entry
        ui.Button(sec, "Update password", self.change_password, "primary", bg=ui.C["card"]).pack(anchor="w", pady=(12, 0))

        # --- data
        data = ui.card(cols, pad=18)
        data.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(12, 0))
        ui.section_label(data, "Data & backup").pack(anchor="w", pady=(0, 10))
        tk.Label(data, text=f"Database: {DB_PATH}", font=ui.font(8), bg=ui.C["card"], fg=ui.C["muted"],
                 wraplength=420, justify="left").pack(anchor="w")
        tk.Label(data, text="A backup copies the whole database file (customers, invoices, stock).",
                 font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], wraplength=420, justify="left").pack(anchor="w", pady=(6, 10))
        row = tk.Frame(data, bg=ui.C["card"])
        row.pack(anchor="w")
        ui.Button(row, "Back up now", self.backup, "primary", bg=ui.C["card"]).pack(side="left")
        ui.Button(row, "Open data folder", self.open_folder, "secondary", bg=ui.C["card"]).pack(side="left", padx=8)

    # ------------------------------------------------------------ actions
    def save_profile(self):
        d = {k: w.get().strip() for k, w in self.p.items()}
        if not d["first_name"] or not d["business_name"]:
            ui.error("First name and business name are required.")
            return
        d["currency"] = self.currency.get()
        self.app.db.update_profile(self.app.user["id"], d)
        self.app.user = self.app.db.get_user(self.app.user["id"])
        self.app.root.title(APP_NAME)
        self.app.notify("Profile saved.")
        self.app.refresh_chrome()

    def save_numbering(self):
        try:
            rate = to_float(self.n["default_tax_rate"].get(), 0)
            reorder = to_float(self.n["low_stock_default"].get(), 5)
        except ValueError:
            ui.error("Tax rate and reorder level must be numbers.")
            return
        db = self.app.db
        for key in ("invoice_prefix", "purchase_prefix", "quote_prefix"):
            value = self.n[key].get().strip().upper()
            if value:
                db.set_setting(key, value)
        db.set_setting("default_tax_rate", f"{rate:g}")
        db.set_setting("low_stock_default", f"{reorder:g}")
        self.app.notify("Settings saved. New invoices use these values.")

    def change_password(self):
        user = self.app.db.get_user(self.app.user["id"])
        cur, new, conf = (self.pw[k].get() for k in ("current", "new", "confirm"))
        if not verify_password(cur, user["password_hash"]):
            ui.error("Current password is incorrect.")
        elif len(new) < 6:
            ui.error("New password must be at least 6 characters.")
        elif new != conf:
            ui.error("New passwords do not match.")
        else:
            self.app.db.change_password(user["id"], new)
            for w in self.pw.values():
                ui.set_entry(w, "")
            ui.info("Password updated.")

    def backup(self):
        try:
            path = self.app.db.backup()
        except (OSError, sqlite3.Error) as ex:
            ui.error(f"Backup failed:\n{ex}")
            return
        self.app.notify("Backup created.")
        ui.info(f"Backup saved to:\n{path}")

    def open_folder(self):
        try:
            if sys.platform.startswith("win"):
                os.startfile(DATA_DIR)  # noqa: S606 - opens the user's own data folder
            elif sys.platform == "darwin":
                subprocess.Popen(["open", DATA_DIR])
            else:
                webbrowser.open("file://" + DATA_DIR)
        except OSError as ex:
            ui.error(f"Could not open the folder:\n{ex}")


class AboutPage:
    FEATURES = [
        ("Sales & purchases", "Multi-product invoices, discounts, tax, partial payments and receipts."),
        ("Customers & suppliers", "Saved contacts you can pick on any invoice, with balances due."),
        ("Inventory", "Stock levels, low-stock alerts, adjustments, and selling at zero stock."),
        ("Quotations", "Create quotes, track status, and convert accepted quotes into sales."),
        ("Reports", "Revenue, collections, outstanding balances and top-selling products."),
        ("Data", "CSV import and export for every list, sample sheets, and one-click backups."),
    ]

    def __init__(self, app):
        self.app = app

    def build(self, parent):
        app = self.app
        ui.page_header(parent, "About Us", f"{APP_NAME}  ·  version {APP_VERSION}").pack(fill="x", pady=(0, 10))
        top = ui.card(parent, pad=24)
        top.pack(fill="x")
        logo = logo_image(app.root, 2)
        if logo:
            tk.Label(top, image=logo, bg=ui.C["card"], bd=0).pack(side="left", padx=(0, 22))
        text = tk.Frame(top, bg=ui.C["card"])
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text="FST - Finance Management", font=ui.font(18, True), bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(text, text="A focused, fast finance tool for small and growing businesses.",
                 font=ui.font(10), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(2, 8))
        tk.Label(text, text=f"Licensed to {app.user['business_name']}  ·  Owner: {app.user['first_name']} {app.user['last_name'] or ''}".strip(),
                 font=ui.font(10, True), bg=ui.C["card"], fg=ui.C["accent"]).pack(anchor="w")

        grid = tk.Frame(parent, bg=ui.C["bg"])
        grid.pack(fill="both", expand=True, pady=(12, 0))
        for i, (title, body) in enumerate(self.FEATURES):
            box = ui.card(grid, pad=16)
            box.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            grid.columnconfigure(i % 3, weight=1, uniform="f")
            tk.Label(box, text=title, font=ui.font(11, True), bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
            tk.Label(box, text=body, font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"],
                     wraplength=260, justify="left").pack(anchor="w", pady=(4, 0))

        keys = ui.card(parent, pad=16)
        keys.pack(fill="x", pady=(6, 0))
        ui.section_label(keys, "Keyboard shortcuts").pack(anchor="w")
        tk.Label(keys, text="Ctrl+1 … Ctrl+9  open a page     ·     Ctrl+S  save invoice     ·     "
                            "Ctrl+N  new draft     ·     Ctrl+F  search",
                 font=ui.font(10), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(6, 0))
