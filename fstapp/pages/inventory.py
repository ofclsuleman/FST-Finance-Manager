"""Inventory: products, stock levels, low-stock filter, adjustments, CSV."""
import tkinter as tk
from tkinter import filedialog, ttk

from .. import ui_kit as ui
from ..config import DEFAULT_LOW_STOCK, UNITS
from ..csv_io import read_csv, to_float, write_csv


class InventoryPage:
    def __init__(self, app):
        self.app = app
        self.editing_id = None
        self.default_reorder = app.db.get_setting("low_stock_default", str(DEFAULT_LOW_STOCK))

    def build(self, parent):
        cur = self.app.user["currency"]
        ui.page_header(parent, "Inventory",
                       "Products are created automatically when you type a new name on an invoice."
                       ).pack(fill="x", pady=(0, 10))

        form = ui.card(parent, pad=16)
        form.pack(fill="x")
        grid = tk.Frame(form, bg=ui.C["card"])
        grid.pack(fill="x")
        self.fields = {}
        specs = [("name", "Product name *", 26), ("sku", "SKU / code", 14), ("category", "Category", 16),
                 ("cost_price", "Cost price", 12), ("sale_price", "Sale price", 12),
                 ("stock", "Opening / current stock", 14), ("reorder_level", "Reorder level", 12)]
        for i, (key, label, width) in enumerate(specs):
            default = self.default_reorder if key == "reorder_level" else ("0" if key in ("stock", "cost_price", "sale_price") else "")
            wrap, entry = ui.field(grid, label, width=width, value=default if key != "name" else "")
            r, c = divmod(i, 4)
            wrap.grid(row=r, column=c, padx=8, pady=4, sticky="ew")
            self.fields[key] = entry
        unit_wrap = tk.Frame(grid, bg=ui.C["card"])
        tk.Label(unit_wrap, text="Unit", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.unit = ttk.Combobox(unit_wrap, values=UNITS, width=12, font=ui.font(10))
        self.unit.set("pcs")
        self.unit.pack(fill="x", ipady=4)
        unit_wrap.grid(row=1, column=3, padx=8, pady=4, sticky="ew")
        for c in range(4):
            grid.columnconfigure(c, weight=1)

        bar = tk.Frame(form, bg=ui.C["card"])
        bar.pack(fill="x", pady=(10, 0))
        self.save_btn = ui.Button(bar, "Add product", self.save, "primary", bg=ui.C["card"])
        self.save_btn.pack(side="left")
        ui.Button(bar, "Clear form", self.clear_form, "secondary", bg=ui.C["card"]).pack(side="left", padx=6)
        self.status_lbl = tk.Label(bar, text="", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"])
        self.status_lbl.pack(side="left", padx=10)

        listing = ui.card(parent, pad=12)
        listing.pack(fill="both", expand=True, pady=(12, 0))
        top = tk.Frame(listing, bg=ui.C["card"])
        top.pack(fill="x", pady=(0, 8))
        ui.section_label(top, "Stock list").pack(side="left")
        self.low_only = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="Hide items in stock — show only low / out of stock", variable=self.low_only,
                       bg=ui.C["card"], fg=ui.C["fg"], selectcolor=ui.C["entry"], activebackground=ui.C["card"],
                       font=ui.font(9), command=self.refresh).pack(side="left", padx=16)
        self.search_wrap, self.search = ui.field(top, "Search", width=26, bg=ui.C["card"])
        self.search_wrap.pack(side="right")
        self.search.bind("<KeyRelease>", lambda e: self.refresh())

        self.table = ui.Table(
            listing,
            [("name", "Product", 230, "w"), ("sku", "SKU", 100, "w"), ("category", "Category", 120, "w"),
             ("cost", "Cost", 100, "e"), ("sale", "Sale price", 100, "e"), ("stock", "Stock", 90, "e"),
             ("reorder", "Reorder at", 90, "e"), ("status", "Status", 130, "w")],
            height=9, on_double=self.load_selected)
        self.table.pack(fill="both", expand=True)

        foot = tk.Frame(listing, bg=ui.C["card"])
        foot.pack(fill="x", pady=(8, 0))
        ui.Button(foot, "Edit selected", self.load_selected, "secondary", bg=ui.C["card"]).pack(side="left")
        ui.Button(foot, "Adjust stock", self.adjust_stock, "secondary", bg=ui.C["card"]).pack(side="left", padx=6)
        ui.Button(foot, "Delete selected", self.delete_selected, "danger", bg=ui.C["card"]).pack(side="left")
        ui.Button(foot, "Import (CSV)", self.import_csv, "ghost", bg=ui.C["card"]).pack(side="left", padx=6)
        ui.Button(foot, "Export (CSV)", self.export_csv, "ghost", bg=ui.C["card"]).pack(side="left")
        ui.Button(foot, "Sample sheet", self.sample_csv, "ghost", bg=ui.C["card"]).pack(side="right")
        self.summary = tk.Label(foot, text="", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"])
        self.summary.pack(side="right", padx=14)
        self.cur = cur
        self.refresh()

    # ------------------------------------------------------------ data
    def refresh(self):
        db = self.app.db
        rows = []
        for p in db.products(self.search.get().strip(), low_only=self.low_only.get()):
            if p["stock"] <= 0:
                status, tag = "Out of stock", "bad"
            elif p["stock"] <= p["reorder_level"]:
                status, tag = "Low stock", "warn"
            else:
                status, tag = "In stock", None
            rows.append((p["id"], (p["name"], p["sku"] or "", p["category"] or "",
                                   f"{p['cost_price']:,.2f}", f"{p['sale_price']:,.2f}",
                                   f"{p['stock']:g} {p['unit'] or ''}".strip(), f"{p['reorder_level']:g}",
                                   status), tag))
        self.table.set_rows(rows)
        all_items = db.products()
        low = sum(1 for p in all_items if p["stock"] <= p["reorder_level"])
        value = sum(max(p["stock"], 0) * p["cost_price"] for p in all_items)
        self.summary.configure(text=f"{len(all_items)} products  ·  {low} need restocking  ·  "
                                    f"stock value {value:,.2f} {self.cur}")

    def _values(self):
        d = {k: w.get().strip() for k, w in self.fields.items()}
        if not d["name"]:
            ui.error("Product name is required.")
            return None
        try:
            return {"name": d["name"], "sku": d["sku"], "category": d["category"],
                    "unit": self.unit.get() or "pcs",
                    "cost_price": to_float(d["cost_price"]), "sale_price": to_float(d["sale_price"]),
                    "stock": to_float(d["stock"]), "reorder_level": to_float(d["reorder_level"])}
        except ValueError:
            ui.error("Prices, stock and reorder level must be numbers (zero or more).")
            return None

    def save(self):
        d = self._values()
        if not d:
            return
        try:
            if self.editing_id:
                self.app.db.update_product(self.editing_id, d)
                msg = "Product updated."
            else:
                self.app.db.add_product(d)
                msg = "Product added."
        except Exception as ex:
            ui.error(f"Could not save product. SKU may already be used.\n{ex}")
            return
        self.app.notify(msg)
        self.clear_form()

    def load_selected(self):
        pid = self.table.first_selected()
        if pid is None:
            ui.error("Select a product first.")
            return
        p = self.app.db.one("SELECT * FROM products WHERE id=?", (pid,))
        if not p:
            return
        for key, entry in self.fields.items():
            value = p.get(key)
            ui.set_entry(entry, "" if value is None else (f"{value:g}" if isinstance(value, float) else value))
        self.unit.set(p["unit"] or "pcs")
        self.editing_id = pid
        self.save_btn.configure(text="Update product")
        self.status_lbl.configure(text=f"Editing: {p['name']}")

    def clear_form(self):
        for key, entry in self.fields.items():
            default = self.default_reorder if key == "reorder_level" else ("0" if key in ("stock", "cost_price", "sale_price") else "")
            ui.set_entry(entry, "" if key == "name" else default)
        self.unit.set("pcs")
        self.editing_id = None
        self.save_btn.configure(text="Add product")
        self.status_lbl.configure(text="")
        self.refresh()

    def adjust_stock(self):
        ids = self.table.selected_ids()
        if not ids:
            ui.error("Select one or more products first.")
            return
        value = ui.prompt_value(self.app.root, "Adjust stock",
                                "Quantity to add (use a minus sign to remove):", "0")
        if value is None:
            return
        try:
            delta = to_float(value.replace("-", "").strip() or "0") * (-1 if value.strip().startswith("-") else 1)
        except ValueError:
            ui.error("Enter a number, for example 10 or -3.")
            return
        self.app.db.adjust_stock(ids, delta)
        self.app.notify(f"Stock adjusted by {delta:+g} for {len(ids)} product(s).")
        self.refresh()

    def delete_selected(self):
        ids = self.table.selected_ids()
        if not ids:
            ui.error("Select one or more products to delete.")
            return
        if ui.ask(f"Delete {len(ids)} product(s)?\nPast invoices keep their product names."):
            self.app.db.delete_products(ids)
            self.app.notify("Products deleted.")
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
        db = self.app.db
        added, updated, skipped = 0, 0, []
        for n, r in rows:
            try:
                if not r.get("name"):
                    raise ValueError("name is empty")
                d = {"name": r["name"], "sku": r.get("sku", ""), "category": r.get("category", ""),
                     "unit": r.get("unit", "") or "pcs",
                     "cost_price": to_float(r.get("cost_price", "")), "sale_price": to_float(r.get("sale_price", "")),
                     "stock": to_float(r.get("stock", "")),
                     "reorder_level": to_float(r.get("reorder_level", ""), float(self.default_reorder))}
                existing = db.one("SELECT id FROM products WHERE name=? COLLATE NOCASE", (r["name"],))
                if existing:
                    db.update_product(existing["id"], d)
                    updated += 1
                else:
                    db.add_product(d)
                    added += 1
            except ValueError as ex:
                skipped.append(f"Line {n}: {ex}")
        msg = f"Added {added} and updated {updated} product(s)."
        if skipped:
            msg += f"\n{len(skipped)} skipped:\n" + "\n".join(skipped[:8])
        ui.info(msg)
        self.refresh()

    def export_csv(self):
        rows = self.app.db.products()
        if not rows:
            ui.info("No products to export yet.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="inventory.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            write_csv(path, ["name", "sku", "category", "unit", "cost_price", "sale_price", "stock", "reorder_level"],
                      [[p["name"], p["sku"] or "", p["category"] or "", p["unit"], p["cost_price"],
                        p["sale_price"], p["stock"], p["reorder_level"]] for p in rows])
            ui.info(f"Exported {len(rows)} product(s).")

    def sample_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="inventory_sample.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            write_csv(path, ["name", "sku", "category", "unit", "cost_price", "sale_price", "stock", "reorder_level"],
                      [["Sample product", "SKU-001", "General", "pcs", "800", "1200", "25", "5"]])
            ui.info("Sample sheet saved. Only 'name' is required; existing names are updated.")

    # ------------------------------------------------------------ shortcuts
    def on_new(self):
        self.clear_form()

    def on_search(self):
        self.search.focus_set()
