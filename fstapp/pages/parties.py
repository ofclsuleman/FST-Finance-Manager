"""Customer and Supplier pages (same layout, different table)."""
import tkinter as tk
from tkinter import filedialog

from .. import ui_kit as ui
from ..csv_io import read_csv, write_csv
from .receive import open_receive_payment

TITLES = {"customers": ("Customers", "Customer", "to collect"),
          "suppliers": ("Suppliers", "Supplier", "to pay")}


class PartyPage:
    def __init__(self, app, table):
        self.app = app
        self.table = table
        self.editing_id = None
        self.title, self.singular, self.balance_word = TITLES[table]

    def build(self, parent):
        ui.page_header(parent, self.title,
                       f"Save people once, then pick them on any invoice. Double-click a row to edit."
                       ).pack(fill="x", pady=(0, 10))

        form = ui.card(parent, pad=16)
        form.pack(fill="x")
        self.fields = {}
        grid = tk.Frame(form, bg=ui.C["card"])
        grid.pack(fill="x")
        specs = [("name", f"{self.singular} name *", 26), ("phone", "Phone", 18),
                 ("business_name", "Business name", 26), ("email", "Email", 26),
                 ("address", "Address", 40)]
        for i, (key, label, width) in enumerate(specs):
            wrap, entry = ui.field(grid, label, width=width)
            r, c = divmod(i, 3)
            wrap.grid(row=r, column=c, padx=8, pady=4, sticky="ew")
            self.fields[key] = entry
        for c in range(3):
            grid.columnconfigure(c, weight=1)

        bar = tk.Frame(form, bg=ui.C["card"])
        bar.pack(fill="x", pady=(10, 0))
        self.save_btn = ui.Button(bar, f"Add {self.singular.lower()}", self.save, "primary", bg=ui.C["card"])
        self.save_btn.pack(side="left")
        ui.Button(bar, "Clear form", self.clear_form, "secondary", bg=ui.C["card"]).pack(side="left", padx=6)
        self.status_lbl = tk.Label(bar, text="", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"])
        self.status_lbl.pack(side="left", padx=10)

        listing = ui.card(parent, pad=12)
        listing.pack(fill="both", expand=True, pady=(12, 0))
        top = tk.Frame(listing, bg=ui.C["card"])
        top.pack(fill="x", pady=(0, 8))
        ui.section_label(top, f"{self.title} ({self.app.db.scalar(f'SELECT COUNT(*) FROM {self.table}')})").pack(side="left")
        self.search_wrap, self.search = ui.field(top, "Search", width=28, bg=ui.C["card"])
        self.search_wrap.pack(side="right")
        self.search.bind("<KeyRelease>", lambda e: self.refresh())

        self.grid_table = ui.Table(
            listing,
            [("name", "Name", 200, "w"), ("business", "Business", 180, "w"), ("phone", "Phone", 130, "w"),
             ("email", "Email", 180, "w"), ("balance", f"Balance {self.balance_word}", 140, "e")],
            height=8, on_double=self.load_selected)
        self.grid_table.pack(fill="both", expand=True)

        foot = tk.Frame(listing, bg=ui.C["card"])
        foot.pack(fill="x", pady=(8, 0))
        ui.Button(foot, "Edit selected", self.load_selected, "secondary", bg=ui.C["card"]).pack(side="left")
        if self.table == "customers":
            ui.Button(foot, "Receive payment", self.receive_selected, "primary", bg=ui.C["card"]).pack(side="left", padx=6)
        ui.Button(foot, "Delete selected", self.delete_selected, "danger", bg=ui.C["card"]).pack(side="left", padx=6)
        ui.Button(foot, "Import (CSV)", self.import_csv, "ghost", bg=ui.C["card"]).pack(side="left", padx=6)
        ui.Button(foot, "Export (CSV)", self.export_csv, "ghost", bg=ui.C["card"]).pack(side="left")
        ui.Button(foot, "Sample sheet", self.sample_csv, "ghost", bg=ui.C["card"]).pack(side="right")

        self.refresh()

    # ------------------------------------------------------------ data
    def refresh(self):
        db = self.app.db
        cur = self.app.user["currency"]
        balances = db.contact_balances(self.table)
        rows = []
        for r in db.contacts(self.table, self.search.get().strip()):
            due = balances.get(r["id"], 0) or 0
            tag = "warn" if due > 0.005 else None
            rows.append((r["id"], (r["name"], r["business_name"] or "", r["phone"] or "",
                                   r["email"] or "", f"{due:,.2f} {cur}"), tag))
        self.grid_table.set_rows(rows)

    def _form_data(self):
        d = {k: w.get().strip() for k, w in self.fields.items()}
        if not d["name"]:
            ui.error(f"{self.singular} name is required.")
            return None
        return d

    def save(self):
        d = self._form_data()
        if not d:
            return
        db = self.app.db
        try:
            if self.editing_id:
                db.update_contact(self.table, self.editing_id, d)
                msg = f"{self.singular} updated."
            else:
                db.add_contact(self.table, d)
                msg = f"{self.singular} added."
        except Exception as ex:
            ui.error(f"Could not save: {ex}")
            return
        self.app.notify(msg)
        self.clear_form()

    def load_selected(self):
        cid = self.grid_table.first_selected()
        if cid is None:
            ui.error("Select a row first.")
            return
        row = next((r for r in self.app.db.contacts(self.table) if r["id"] == cid), None)
        if not row:
            return
        for key, entry in self.fields.items():
            ui.set_entry(entry, row.get(key) or "")
        self.editing_id = cid
        self.save_btn.configure(text="Update " + self.singular.lower())
        self.status_lbl.configure(text=f"Editing: {row['name']}")

    def receive_selected(self):
        cid = self.grid_table.first_selected()
        if cid is None:
            ui.error("Select a customer row first.")
            return
        row = next((r for r in self.app.db.contacts(self.table) if r["id"] == cid), None)
        if row:
            open_receive_payment(self.app, row, self.refresh)

    def clear_form(self):
        for entry in self.fields.values():
            ui.set_entry(entry, "")
        self.editing_id = None
        self.save_btn.configure(text=f"Add {self.singular.lower()}")
        self.status_lbl.configure(text="")
        self.refresh()

    def delete_selected(self):
        ids = self.grid_table.selected_ids()
        if not ids:
            ui.error("Select one or more rows to delete.")
            return
        if ui.ask(f"Delete {len(ids)} {self.singular.lower()}(s)?\nPast invoices stay in history."):
            self.app.db.delete_contacts(self.table, ids)
            self.app.notify("Deleted.")
            self.clear_form()

    # ------------------------------------------------------------ CSV
    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        try:
            rows = read_csv(path, required=["name"])
        except (ValueError, OSError) as ex:
            ui.error(f"Could not import this file.\n{ex}\n\nUse 'Sample sheet' for the correct format.")
            return
        added, skipped = 0, []
        for n, r in rows:
            if not r.get("name"):
                skipped.append(f"Line {n}: name is empty")
                continue
            self.app.db.upsert_contact(self.table, {
                "name": r["name"], "phone": r.get("phone", ""), "email": r.get("email", ""),
                "business_name": r.get("business_name", "") or r.get("business name", ""),
                "address": r.get("address", "")})
            added += 1
        msg = f"Imported {added} {self.title.lower()}."
        if skipped:
            msg += f"\n{len(skipped)} skipped:\n" + "\n".join(skipped[:8])
        ui.info(msg)
        self.refresh()

    def export_csv(self):
        rows = self.app.db.contacts(self.table)
        if not rows:
            ui.info("Nothing to export yet.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"{self.table}.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            write_csv(path, ["name", "phone", "email", "business_name", "address"],
                      [[r["name"], r["phone"] or "", r["email"] or "", r["business_name"] or "",
                        r["address"] or ""] for r in rows])
            ui.info(f"Exported {len(rows)} record(s).")

    def sample_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"{self.table}_sample.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            write_csv(path, ["name", "phone", "email", "business_name", "address"],
                      [["Ali Khan", "0300-1234567", "ali@example.com", "Khan Traders", "Karachi"]])
            ui.info("Sample sheet saved. Only 'name' is required.")

    # ------------------------------------------------------------ shortcuts
    def on_new(self):
        self.clear_form()

    def on_search(self):
        self.search.focus_set()


class PartiesPage:
    """Customers and suppliers on one page. Switch with the two tabs at the top."""

    TABS = [("customers", "Customers"), ("suppliers", "Suppliers")]

    def __init__(self, app):
        self.app = app
        self.pages = {key: PartyPage(app, key) for key, _ in self.TABS}
        self.frames = {}
        self.tab_buttons = {}
        self.current = "customers"

    def build(self, parent):
        bar = tk.Frame(parent, bg=ui.C["bg"])
        bar.pack(fill="x", pady=(0, 10))
        for key, label in self.TABS:
            btn = tk.Label(bar, text=label, font=ui.font(10), padx=16, pady=8, cursor="hand2")
            btn.pack(side="left", padx=(0, 4))
            btn.bind("<Button-1>", lambda e, k=key: self.switch(k))
            self.tab_buttons[key] = btn
        holder = tk.Frame(parent, bg=ui.C["bg"])
        holder.pack(fill="both", expand=True)
        for key, _ in self.TABS:
            frame = tk.Frame(holder, bg=ui.C["bg"])
            self.pages[key].build(frame)
            self.frames[key] = frame
        self.switch(self.current)

    def switch(self, key):
        self.current = key
        for k, frame in self.frames.items():
            if k == key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        for k, btn in self.tab_buttons.items():
            active = k == key
            btn.configure(bg=ui.C["accent"] if active else ui.C["card"],
                          fg=ui.C["accent_fg"] if active else ui.C["fg"], font=ui.font(10, active))

