"""Sales & purchase list: every saved entry, filterable, with line-item view.

Lets you check what was saved: invoice by invoice, or product line by product
line, for any date range. Double-click opens the invoice; share and export are
available from the same page.
"""
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, ttk

from .. import ui_kit as ui
from ..csv_io import write_csv
from .invoices import InvoiceDialog, InvoicePage

STATUS_TAG = {"Paid": "good", "Partial": "warn", "Unpaid": "bad"}
KINDS = {"Sales": "sale", "Purchases": "purchase"}
STATUSES = ["All statuses", "Paid", "Partial", "Unpaid"]


class EntriesPage:
    def __init__(self, app):
        self.app = app
        self.kind = "sale"
        self.view = "invoices"
        self.date_from = None
        self.date_to = None
        self.rows = []
        self.line_to_invoice = {}

    # ------------------------------------------------------------ build
    def build(self, parent):
        ui.page_header(parent, "Sales & purchase list",
                       "Every entry you have saved. Pick a range, filter, then double-click to open."
                       ).pack(fill="x", pady=(0, 10))

        bar = ui.card(parent, pad=12)
        bar.pack(fill="x")
        row1 = tk.Frame(bar, bg=ui.C["card"])
        row1.pack(fill="x")
        self.type_cb = self._combo(row1, "Type", list(KINDS), "Sales" if self.kind == "sale" else "Purchases", 14)
        self.type_cb.bind("<<ComboboxSelected>>", lambda e: self._switch_type())
        self.view_cb = self._combo(row1, "Show", ["Invoices", "Line items"], "Invoices", 14)
        self.view_cb.bind("<<ComboboxSelected>>", lambda e: self._switch_view())
        self.status_cb = self._combo(row1, "Status", STATUSES, STATUSES[0], 14)
        self.status_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.search_wrap, self.search = ui.field(row1, "Search (invoice, party, product)", width=30, bg=ui.C["card"])
        self.search_wrap.pack(side="left", padx=8)
        self.search.bind("<KeyRelease>", lambda e: self.refresh())

        row2 = tk.Frame(bar, bg=ui.C["card"])
        row2.pack(fill="x", pady=(10, 0))
        self.from_wrap, self.from_e = ui.field(row2, "From (YYYY-MM-DD)", width=13, bg=ui.C["card"])
        self.from_wrap.pack(side="left", padx=(0, 8))
        self.to_wrap, self.to_e = ui.field(row2, "To (YYYY-MM-DD)", width=13, bg=ui.C["card"])
        self.to_wrap.pack(side="left", padx=(0, 10))
        ui.Button(row2, "Apply", self.apply_dates, "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        ui.Button(row2, "This month", lambda: self.quick("month"), "ghost", bg=ui.C["card"]).pack(side="left", padx=3, pady=(14, 0))
        ui.Button(row2, "Today", lambda: self.quick("today"), "ghost", bg=ui.C["card"]).pack(side="left", padx=3, pady=(14, 0))
        ui.Button(row2, "All time", lambda: self.quick("all"), "ghost", bg=ui.C["card"]).pack(side="left", padx=3, pady=(14, 0))

        self.summary = tk.Frame(parent, bg=ui.C["bg"])
        self.summary.pack(fill="x", pady=(10, 0))

        listing = ui.card(parent, pad=12)
        listing.pack(fill="both", expand=True, pady=(10, 0))
        self.table_holder = tk.Frame(listing, bg=ui.C["card"])
        self.table_holder.pack(fill="both", expand=True)
        foot = tk.Frame(listing, bg=ui.C["card"])
        foot.pack(fill="x", pady=(8, 0))
        self.count_lbl = tk.Label(foot, text="", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"])
        self.count_lbl.pack(side="left")
        ui.Button(foot, "Export (CSV)", self.export, "secondary", bg=ui.C["card"]).pack(side="right")
        ui.Button(foot, "Share on WhatsApp", self.share_selected, "secondary", bg=ui.C["card"]).pack(side="right", padx=6)
        ui.Button(foot, "Open selected", self.open_selected, "primary", bg=ui.C["card"]).pack(side="right", padx=6)

        self.quick("month")

    def _combo(self, parent, label, values, current, width):
        wrap = tk.Frame(parent, bg=ui.C["card"])
        wrap.pack(side="left", padx=(0, 8))
        tk.Label(wrap, text=label, font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        cb = ttk.Combobox(wrap, values=values, state="readonly", width=width, font=ui.font(10))
        cb.set(current)
        cb.pack(ipady=4)
        return cb

    # ------------------------------------------------------------ period & switches
    def quick(self, mode):
        today = datetime.now()
        if mode == "today":
            start, end = today, today
        elif mode == "month":
            start, end = today.replace(day=1), today
        else:
            start = end = None
        if start is None:
            ui.set_entry(self.from_e, "")
            ui.set_entry(self.to_e, "")
        else:
            ui.set_entry(self.from_e, start.strftime("%Y-%m-%d"))
            ui.set_entry(self.to_e, end.strftime("%Y-%m-%d"))
        self.apply_dates()

    def apply_dates(self):
        parsed = []
        for entry in (self.from_e, self.to_e):
            text = entry.get().strip()
            if not text:
                parsed.append(None)
                continue
            try:
                parsed.append(datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d"))
            except ValueError:
                ui.error("Dates must look like 2026-11-01 (year-month-day), or leave blank for all dates.")
                return
        if parsed[0] and parsed[1] and parsed[0] > parsed[1]:
            ui.error("The 'From' date must be before the 'To' date.")
            return
        self.date_from, self.date_to = parsed
        self.refresh()

    def _switch_type(self):
        self.kind = KINDS[self.type_cb.get()]
        self.refresh()

    def _switch_view(self):
        self.view = "lines" if self.view_cb.get() == "Line items" else "invoices"
        self.refresh()

    # ------------------------------------------------------------ data & render
    def refresh(self):
        db = self.app.db
        term = self.search.get().strip()
        status = self.status_cb.get()
        cur = self.app.user["currency"]
        for w in self.table_holder.winfo_children():
            w.destroy()

        if self.view == "invoices":
            entries = db.invoices(self.kind, self.date_from, self.date_to, term, limit=100000)
            if status in STATUS_TAG:
                entries = [e for e in entries if e["status"] == status]
            total = sum(e["total"] for e in entries)
            paid = sum(e["paid"] for e in entries)
            cols = [("date", "Date", 110, "w"), ("no", "Invoice", 170, "w"),
                    ("party", "Customer" if self.kind == "sale" else "Supplier", 230, "w"),
                    ("items", "Items", 60, "e"), ("total", "Total", 120, "e"), ("paid", "Paid", 110, "e"),
                    ("due", "Due", 110, "e"), ("status", "Status", 90, "w")]
            rows = []
            for e in entries:
                rows.append((e["id"], (e["created_at"][:10], e["invoice_no"], e["party"] or "Walk-in",
                                       e["item_count"], f"{e['total']:,.2f}", f"{e['paid']:,.2f}",
                                       f"{e['due']:,.2f}", e["status"]), STATUS_TAG[e["status"]]))
            self.line_to_invoice = {}
            count_text = f"{len(entries)} invoice(s)"
        else:
            lines = db.invoice_lines(self.kind, self.date_from, self.date_to, term)
            if status in STATUS_TAG:
                allowed = {e["id"] for e in db.invoices(self.kind, self.date_from, self.date_to, term, limit=100000)
                           if e["status"] == status}
                lines = [l for l in lines if l["invoice_id"] in allowed]
            total = sum(l["line_total"] for l in lines)
            paid = None
            cols = [("date", "Date", 110, "w"), ("no", "Invoice", 170, "w"),
                    ("party", "Customer" if self.kind == "sale" else "Supplier", 180, "w"),
                    ("product", "Product", 180, "w"), ("desc", "Description", 200, "w"),
                    ("qty", "Qty", 60, "e"), ("price", "Price", 100, "e"), ("amount", "Amount", 110, "e")]
            rows = []
            self.line_to_invoice = {}
            for l in lines:
                self.line_to_invoice[l["line_id"]] = l["invoice_id"]
                rows.append((l["line_id"], (l["created_at"][:10], l["invoice_no"], l["party"] or "Walk-in",
                                            l["product_name"], l["description"] or "", f"{l['qty']:g}",
                                            f"{l['unit_price']:,.2f}", f"{l['line_total']:,.2f}"), None))
            count_text = f"{len(lines)} line(s)"

        self._summary(len(rows), total, paid, cur)
        self.table = ui.Table(self.table_holder, cols, height=16, on_double=self.open_selected)
        self.table.pack(fill="both", expand=True)
        self.table.set_rows(rows)
        self.count_lbl.configure(text=f"{count_text}  ·  double-click a row to open  ·  {self._period_text()}")
        self.current_rows = rows

    def _period_text(self):
        if not self.date_from and not self.date_to:
            return "all dates"
        return f"{self.date_from or 'beginning'} to {self.date_to or 'today'}"

    def _summary(self, count, total, paid, cur):
        for w in self.summary.winfo_children():
            w.destroy()
        label = "Sales" if self.kind == "sale" else "Purchases"
        tiles = [(f"{label} entries", str(count), ui.C["accent"]),
                 ("Total value", f"{total:,.2f} {cur}", ui.C["success"] if self.kind == "sale" else ui.C["accent"])]
        if paid is not None:
            tiles += [("Paid", f"{paid:,.2f} {cur}", ui.C["success"]),
                      ("Outstanding", f"{total - paid:,.2f} {cur}", ui.C["warn"])]
        for i, (lbl, value, color) in enumerate(tiles):
            ui.stat_card(self.summary, lbl, value, color).grid(row=0, column=i, padx=(0 if i == 0 else 8, 0), sticky="nsew")
            self.summary.columnconfigure(i, weight=1, uniform="sum")

    # ------------------------------------------------------------ actions
    def _selected_invoice_id(self):
        sel = self.table.first_selected() if hasattr(self, "table") else None
        if sel is None:
            ui.error("Select an entry in the list first.")
            return None
        return self.line_to_invoice.get(sel, sel) if self.view == "lines" else sel

    def open_selected(self):
        inv_id = self._selected_invoice_id()
        if inv_id is not None:
            InvoiceDialog(self, inv_id)

    def share_selected(self):
        inv_id = self._selected_invoice_id()
        if inv_id is not None:
            self.share_invoice(inv_id)

    # InvoiceDialog calls these on its page.
    def share_invoice(self, inv_id):
        InvoicePage(self.app, self.kind).share_invoice(inv_id)

    def refresh_history(self):
        self.refresh()

    def export(self):
        if not getattr(self, "current_rows", None):
            ui.info("Nothing to export for this selection.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile=f"{self.kind}_list_{datetime.now():%Y%m%d}.csv",
                                            filetypes=[("CSV file (opens in Excel)", "*.csv")])
        if not path:
            return
        headers = [self.table.tree.heading(k)["text"] for k in self.table.keys]
        write_csv(path, headers, [list(values) for _, values, _ in self.current_rows])
        ui.info(f"Exported {len(self.current_rows)} row(s).")

    def on_search(self):
        self.search.focus_set()
