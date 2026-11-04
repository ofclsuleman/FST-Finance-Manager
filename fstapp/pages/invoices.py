"""Sales and Purchase invoices (one class, two modes).

* Customer/supplier picker searches saved contacts while you type.
* Every product line has a description, prefilled from the product catalogue.
* Payments can be recorded later with a chosen method; each one posts to the ledger.
"""
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, ttk

from .. import ui_kit as ui
from ..config import PAYMENT_METHODS, WALK_IN
from ..documents import invoice_image
from ..share_view import ShareDialog
from ..csv_io import read_csv, to_float, write_csv

KIND_INFO = {
    "sale": {"title": "Sales", "table": "customers", "party": "Customer", "price": "Sale price"},
    "purchase": {"title": "Purchase", "table": "suppliers", "party": "Supplier", "price": "Cost price"},
}
STATUS_TAG = {"Paid": "good", "Partial": "warn", "Unpaid": "bad"}


def _blank_draft(db):
    return {"lines": [], "party_id": None, "party_label": "", "party_name": "", "party_phone": "",
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "save_new": False, "discount": "0", "tax": db.get_setting("default_tax_rate", "0"),
            "paid": "", "method": "Cash", "note": ""}


class InvoicePage:
    def __init__(self, app, kind):
        self.app = app
        self.kind = kind
        self.info = KIND_INFO[kind]
        self.draft = _blank_draft(app.db)
        self._discard = False

    # ------------------------------------------------------------ build
    def build(self, parent):
        self._discard = False
        d = self.draft
        ui.page_header(parent, self.info["title"], "Ctrl+S save  ·  Ctrl+N new  ·  Double-click a row to open it"
                       ).pack(fill="x", pady=(0, 10))

        party_box = ui.card(parent, pad=14)
        party_box.pack(fill="x")
        pick_wrap = self._label_frame(party_box, f"{self.info['party']} (type to search, or pick a saved one)")
        pick_wrap.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.party_picker = ui.Picker(pick_wrap, self._party_provider, width=38, on_pick=self._on_party_pick)
        self.party_picker.pack(fill="x", ipady=4)
        self.party_picker.bind("<KeyRelease>", lambda e: self._sync(), add="+")
        self.party_picker.set(d["party_label"] or d["party_name"] or WALK_IN)
        self.phone_wrap, self.phone_entry = ui.field(party_box, "Phone", width=18, value=d["party_phone"])
        self.phone_wrap.grid(row=0, column=1, padx=8, sticky="ew")
        self.phone_entry.bind("<KeyRelease>", lambda e: self._sync())
        date_wrap, self.date_entry = ui.field(party_box, "Date of entry (YYYY-MM-DD)", width=14,
                                              value=d["entry_date"], bg=ui.C["card"])
        date_wrap.grid(row=0, column=3, padx=8, sticky="ew")
        self.date_entry.bind("<KeyRelease>", lambda e: self._sync())
        self.save_new_var = tk.BooleanVar(value=d["save_new"])
        tk.Checkbutton(party_box, text=f"Save as new {self.info['party'].lower()}", variable=self.save_new_var,
                       bg=ui.C["card"], fg=ui.C["fg"], selectcolor=ui.C["entry"], activebackground=ui.C["card"],
                       font=ui.font(9), command=self._sync).grid(row=0, column=2, padx=8, sticky="w")
        party_box.columnconfigure(0, weight=1)

        add = ui.card(parent, pad=14)
        add.pack(fill="x", pady=10)
        prod_wrap = self._label_frame(add, "Product (type to search, or type a new name)")
        prod_wrap.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.prod_picker = ui.Picker(prod_wrap, self._product_provider, width=28, on_pick=self._on_product_pick)
        self.prod_picker.pack(fill="x", ipady=4)
        self.desc_wrap, self.desc_entry = ui.field(add, "Description", width=28, bg=ui.C["card"])
        self.desc_wrap.grid(row=0, column=1, padx=8, sticky="ew")
        self.qty_wrap, self.qty_entry = ui.field(add, "Qty", width=7, value="1", bg=ui.C["card"])
        self.qty_wrap.grid(row=0, column=2, padx=8, sticky="ew")
        self.price_wrap, self.price_entry = ui.field(add, self.info["price"], width=12, bg=ui.C["card"])
        self.price_wrap.grid(row=0, column=3, padx=8, sticky="ew")
        for entry in (self.desc_entry, self.qty_entry, self.price_entry):
            entry.bind("<Return>", lambda e: self.add_line())
        ui.Button(add, "+ Add", self.add_line, "primary", bg=ui.C["card"]).grid(row=0, column=4, padx=8, sticky="s")
        add.columnconfigure(0, weight=2)
        add.columnconfigure(1, weight=2)

        body = tk.Frame(parent, bg=ui.C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        lines_box = ui.card(body, pad=12)
        lines_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.lines_table = ui.Table(lines_box, [("product", "Product", 200, "w"), ("desc", "Description", 220, "w"),
                                                ("qty", "Qty", 60, "e"), ("price", "Price", 110, "e"),
                                                ("amount", "Amount", 120, "e")], height=7)
        self.lines_table.pack(fill="both", expand=True)
        row = tk.Frame(lines_box, bg=ui.C["card"])
        row.pack(fill="x", pady=(8, 0))
        ui.Button(row, "Remove selected", self.remove_lines, "secondary", bg=ui.C["card"]).pack(side="left")
        ui.Button(row, "Import lines (CSV)", self.import_lines, "ghost", bg=ui.C["card"]).pack(side="left", padx=6)
        ui.Button(row, "Sample sheet", self.sample_sheet, "ghost", bg=ui.C["card"]).pack(side="left")

        tot = ui.card(body, pad=16)
        tot.grid(row=0, column=1, sticky="nsew")
        self.subtotal_lbl = self._total_row(tot, "Subtotal")
        self.discount_wrap, self.discount_entry = ui.field(tot, "Discount (amount)", width=14, value=d["discount"], bg=ui.C["card"])
        self.discount_wrap.pack(fill="x", pady=4)
        self.tax_wrap, self.tax_entry = ui.field(tot, "Tax (%)", width=14, value=d["tax"], bg=ui.C["card"])
        self.tax_wrap.pack(fill="x", pady=4)
        self.tax_lbl = self._total_row(tot, "Tax amount")
        self.total_lbl = tk.Label(tot, text="", font=ui.font(18, True), bg=ui.C["card"], fg=ui.C["accent"])
        self.total_lbl.pack(anchor="e", pady=(10, 4))
        self.paid_wrap, self.paid_entry = ui.field(tot, "Amount paid now (blank = full)", width=14, value=d["paid"], bg=ui.C["card"])
        self.paid_wrap.pack(fill="x", pady=4)
        method_wrap = tk.Frame(tot, bg=ui.C["card"])
        method_wrap.pack(fill="x", pady=4)
        tk.Label(method_wrap, text="Payment method (Credit = pay later)", font=ui.font(9), bg=ui.C["card"],
                 fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.method = ttk.Combobox(method_wrap, values=PAYMENT_METHODS + ["Credit"], state="readonly", font=ui.font(10))
        self.method.set(d["method"])
        self.method.pack(fill="x", ipady=4)
        self.method.bind("<<ComboboxSelected>>", lambda e: self._sync_and_totals())
        self.balance_lbl = tk.Label(tot, text="", font=ui.font(10, True), bg=ui.C["card"], fg=ui.C["muted"])
        self.balance_lbl.pack(anchor="e", pady=(4, 8))
        for entry in (self.discount_entry, self.tax_entry, self.paid_entry):
            entry.bind("<KeyRelease>", lambda e: self._sync_and_totals())
        self.note_wrap, self.note_entry = ui.field(tot, "Note (optional)", width=14, value=d["note"], bg=ui.C["card"])
        self.note_wrap.pack(fill="x", pady=4)
        actions = tk.Frame(tot, bg=ui.C["card"])
        actions.pack(fill="x", pady=(12, 0))
        ui.Button(actions, "Save invoice", self.on_save, "primary", bg=ui.C["card"]).pack(fill="x")
        sub = tk.Frame(actions, bg=ui.C["card"])
        sub.pack(fill="x", pady=(6, 0))
        ui.Button(sub, "Clear", self.clear_draft, "secondary", bg=ui.C["card"]).pack(side="left", fill="x", expand=True)
        ui.Button(sub, "Receipt (.txt)", self.export_receipt, "secondary", bg=ui.C["card"]).pack(
            side="left", fill="x", expand=True, padx=(6, 0))

        hist = ui.card(parent, pad=12)
        hist.pack(fill="both", expand=True, pady=(10, 0))
        bar = tk.Frame(hist, bg=ui.C["card"])
        bar.pack(fill="x", pady=(0, 8))
        ui.section_label(bar, f"{self.info['title']} history").pack(side="left")
        today = datetime.now().strftime("%Y-%m-%d")
        self.search_wrap, self.search_entry = ui.field(bar, "Search", width=20, bg=ui.C["card"])
        self.search_wrap.pack(side="right", padx=4)
        self.to_wrap, self.to_entry = ui.field(bar, "To (YYYY-MM-DD)", width=12, value=today, bg=ui.C["card"])
        self.to_wrap.pack(side="right", padx=4)
        self.from_wrap, self.from_entry = ui.field(bar, "From (YYYY-MM-DD)", width=12, value=today, bg=ui.C["card"])
        self.from_wrap.pack(side="right", padx=4)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_history())
        self.from_entry.bind("<Return>", lambda e: self.refresh_history())
        self.to_entry.bind("<Return>", lambda e: self.refresh_history())
        ui.Button(bar, "Show all", self._show_all, "ghost", bg=ui.C["card"]).pack(side="right", padx=4, pady=(14, 0))
        self.hist_table = ui.Table(hist, [("no", "Invoice", 170, "w"), ("party", self.info["party"], 230, "w"),
                                          ("total", "Total", 120, "e"), ("paid", "Paid", 110, "e"),
                                          ("due", "Due", 110, "e"), ("status", "Status", 90, "w"),
                                          ("date", "Date", 150, "w")], height=6, on_double=self.open_selected)
        self.hist_table.pack(fill="both", expand=True)
        bottom = tk.Frame(hist, bg=ui.C["card"])
        bottom.pack(fill="x", pady=(8, 0))
        ui.Button(bottom, "Open selected", self.open_selected, "secondary", bg=ui.C["card"]).pack(side="left")
        ui.Button(bottom, "Share on WhatsApp", self.share_selected, "primary", bg=ui.C["card"]).pack(side="left", padx=6)
        ui.Button(bottom, "Export history (CSV)", self.export_history, "ghost", bg=ui.C["card"]).pack(side="right")

        self._redraw_lines()
        self.refresh_history()

    def _label_frame(self, parent, text):
        wrap = tk.Frame(parent, bg=ui.C["card"])
        tk.Label(wrap, text=text, font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        return wrap

    def _total_row(self, parent, label):
        row = tk.Frame(parent, bg=ui.C["card"])
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=ui.font(10), bg=ui.C["card"], fg=ui.C["muted"]).pack(side="left")
        val = tk.Label(row, text="0.00", font=ui.font(10, True), bg=ui.C["card"], fg=ui.C["fg"])
        val.pack(side="right")
        return val

    # ------------------------------------------------------------ pickers
    def _party_provider(self, term):
        opts = [(WALK_IN, None)] if not term else []
        return opts + self.app.db.contact_options(self.info["table"], term)

    def _product_provider(self, term):
        return self.app.db.product_options(term)

    def _on_party_pick(self, label, value):
        d = self.draft
        if value is None:
            d.update(party_id=None, party_label="", party_name="", party_phone="")
        else:
            d.update(party_id=value["id"], party_label=label, party_name=value["name"], party_phone=value["phone"] or "")
            ui.set_entry(self.phone_entry, d["party_phone"])
        self._sync()

    def _on_product_pick(self, label, value):
        if value is None:
            return
        self.prod_picker.set(value["name"])
        price = value["sale_price"] if self.kind == "sale" else value["cost_price"]
        ui.set_entry(self.price_entry, f"{price:g}")
        ui.set_entry(self.desc_entry, value.get("description") or "")
        self.qty_entry.focus_set()

    # ------------------------------------------------------------ draft state
    def leave(self):
        if not self._discard:
            self._sync()

    def _sync(self):
        try:
            d = self.draft
            text = self.party_picker.get().strip()
            text = "" if text == WALK_IN else text
            if d["party_id"] and text != d["party_label"]:
                d["party_id"], d["party_label"] = None, ""
            d["party_name"] = text
            d["party_phone"] = self.phone_entry.get().strip()
            d["save_new"] = bool(self.save_new_var.get())
            d["entry_date"] = self.date_entry.get().strip()
            d["discount"], d["tax"] = self.discount_entry.get(), self.tax_entry.get()
            d["paid"], d["note"] = self.paid_entry.get(), self.note_entry.get()
            d["method"] = self.method.get() or "Cash"
        except tk.TclError:
            pass

    def _sync_and_totals(self):
        self._sync()
        self._refresh_totals()

    def _amounts(self):
        d = self.draft
        subtotal = sum(l["qty"] * l["price"] for l in d["lines"])
        try:
            discount = min(max(to_float(d["discount"]), 0), subtotal)
        except ValueError:
            discount = 0.0
        try:
            rate = to_float(d["tax"])
        except ValueError:
            rate = 0.0
        tax = round((subtotal - discount) * rate / 100, 2)
        return subtotal, discount, tax, round(subtotal - discount + tax, 2)

    def _refresh_totals(self):
        cur = self.app.user["currency"]
        subtotal, _, tax, total = self._amounts()
        self.subtotal_lbl.configure(text=f"{subtotal:,.2f}")
        self.tax_lbl.configure(text=f"{tax:,.2f}")
        self.total_lbl.configure(text=f"Total  {total:,.2f} {cur}")
        try:
            paid = to_float(self.draft["paid"], total) if self.draft["paid"] else total
        except ValueError:
            paid = total
        if self.draft["method"] == "Credit":
            paid = 0
        due = max(total - paid, 0)
        self.balance_lbl.configure(text="Fully paid" if due <= 0.005 else f"Balance due  {due:,.2f} {cur}",
                                   fg=ui.C["success"] if due <= 0.005 else ui.C["warn"])

    # ------------------------------------------------------------ lines
    def add_line(self):
        self._sync()
        name = self.prod_picker.get().strip()
        desc = self.desc_entry.get().strip()
        try:
            qty, price = to_float(self.qty_entry.get(), 0), to_float(self.price_entry.get(), -1)
        except ValueError:
            ui.error("Quantity and price must be numbers.")
            return
        if not name or qty <= 0 or price < 0:
            ui.error("Enter a product name, a quantity above 0 and a valid price.")
            return
        product = self.prod_picker.selected()
        self.draft["lines"].append({"product_id": product["id"] if product else None,
                                    "name": product["name"] if product else name,
                                    "desc": desc, "qty": qty, "price": price})
        for entry, value in ((self.prod_picker, ""), (self.desc_entry, ""), (self.qty_entry, "1"), (self.price_entry, "")):
            if isinstance(entry, ttk.Combobox):
                entry.set(value)
            else:
                ui.set_entry(entry, value)
        self.prod_picker.focus_set()
        self._redraw_lines()

    def remove_lines(self):
        for idx in sorted(self.lines_table.selected_ids(), reverse=True):
            if 0 <= idx < len(self.draft["lines"]):
                self.draft["lines"].pop(idx)
        self._redraw_lines()

    def _redraw_lines(self):
        self.lines_table.set_rows([
            (i, (l["name"], l.get("desc", ""), f"{l['qty']:g}", f"{l['price']:,.2f}",
                 f"{l['qty'] * l['price']:,.2f}"), None)
            for i, l in enumerate(self.draft["lines"])])
        self._refresh_totals()

    def clear_draft(self):
        keep_tax = self.app.db.get_setting("default_tax_rate", "0")
        self.draft.update(lines=[], party_id=None, party_label="", party_name="", party_phone="", save_new=False,
                          entry_date=datetime.now().strftime("%Y-%m-%d"),
                          discount="0", tax=keep_tax, paid="", note="")
        self._discard = True
        self.app.refresh_current()

    # ------------------------------------------------------------ save
    def on_save(self):
        self._sync()
        d = self.draft
        db = self.app.db
        if not d["lines"]:
            ui.error("Add at least one product before saving.")
            return
        _, discount, _, total = self._amounts()
        try:
            paid = to_float(d["paid"], total) if d["paid"] else total
        except ValueError:
            ui.error("Amount paid must be a number.")
            return
        if d["method"] == "Credit":
            paid = 0
        try:
            entry_day = datetime.strptime(d["entry_date"], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            ui.error("Date of entry must look like 2026-11-04 (year-month-day).")
            return
        if paid > total + 0.005:
            ui.error("Amount paid cannot be more than the total.")
            return
        if self.kind == "sale":
            short = []
            for l in d["lines"]:
                if l["product_id"]:
                    stock = db.scalar("SELECT stock FROM products WHERE id=?", (l["product_id"],))
                    if stock < l["qty"]:
                        short.append(f"{l['name']} (have {stock:g}, selling {l['qty']:g})")
            if short and not ui.ask("These items exceed available stock:\n\n• " + "\n• ".join(short)
                                    + "\n\nSave anyway? Stock will go negative."):
                return

        party_id, party_name, party_phone = d["party_id"], d["party_name"], d["party_phone"]
        table = self.info["table"]
        if party_name and not party_id:
            match = db.one(f"SELECT id, phone FROM {table} WHERE name=? COLLATE NOCASE", (party_name,))
            if match:
                party_id, party_phone = match["id"], party_phone or match["phone"] or ""
            elif d["save_new"]:
                party_id = db.add_contact(table, {"name": party_name, "phone": party_phone})
        try:
            inv_no = db.save_invoice(self.kind, d["lines"], party_id=party_id, party_name=party_name or None,
                                     party_phone=party_phone or None, discount=discount,
                                     tax_rate=to_float(d["tax"], 0) if d["tax"] else 0, paid=paid,
                                     method=d["method"], note=d["note"], entry_date=entry_day)
        except Exception as ex:
            ui.error(f"Could not save the invoice:\n{ex}")
            return
        linked = "linked to a saved contact" if party_id else "saved without a contact"
        self.app.notify(f"Invoice {inv_no} saved ({linked}).")
        ui.info(f"Invoice {inv_no} saved for {entry_day}.\n{linked.capitalize()}. Journal updated.")
        self.clear_draft()

    # ------------------------------------------------------------ history
    def refresh_history(self):
        rows = self.app.db.invoices(self.kind, self._date(self.from_entry), self._date(self.to_entry),
                                    self.search_entry.get().strip())
        self.hist_table.set_rows([
            (r["id"], (r["invoice_no"], r["party"] or "Walk-in", f"{r['total']:,.2f}", f"{r['paid']:,.2f}",
                       f"{r['due']:,.2f}", r["status"], r["created_at"][:16].replace("T", " ")),
             STATUS_TAG[r["status"]]) for r in rows])

    @staticmethod
    def _date(entry):
        text = entry.get().strip()
        try:
            return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d") if text else None
        except ValueError:
            return None

    def _show_all(self):
        ui.set_entry(self.from_entry, "")
        ui.set_entry(self.to_entry, "")
        self.refresh_history()

    def open_selected(self):
        inv_id = self.hist_table.first_selected()
        if inv_id is None:
            ui.error("Select an invoice in the list first.")
            return
        InvoiceDialog(self, inv_id)

    def share_selected(self):
        inv_id = self.hist_table.first_selected()
        if inv_id is None:
            ui.error("Select an invoice in the list first.")
            return
        self.share_invoice(inv_id)

    def share_invoice(self, inv_id):
        try:
            path, info = invoice_image(self.app.db, self.app.user, self.kind, inv_id)
        except ImportError:
            ui.error("Sharing needs the Pillow library.\n\nOpen a terminal and run:  pip install pillow")
            return
        except Exception as ex:
            ui.error(f"Could not create the invoice image:\n{ex}")
            return
        ShareDialog(self.app, path, info)

    # ------------------------------------------------------------ import / export
    def import_lines(self):
        path = filedialog.askopenfilename(filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        try:
            rows = read_csv(path, required=["product", "qty", "price"])
        except (ValueError, OSError) as ex:
            ui.error(f"Could not import this file.\n{ex}\n\nUse 'Sample sheet' for the correct format.")
            return
        db = self.app.db
        added, skipped = 0, []
        for n, r in rows:
            try:
                qty, price = to_float(r["qty"]), to_float(r["price"])
                if not r["product"] or qty <= 0:
                    raise ValueError("product name and quantity above 0 are required")
                product = db.one("SELECT id, name FROM products WHERE name=? COLLATE NOCASE", (r["product"],))
                self.draft["lines"].append({"product_id": product["id"] if product else None,
                                            "name": product["name"] if product else r["product"],
                                            "desc": r.get("description", ""), "qty": qty, "price": price})
                added += 1
                if not self.draft["party_name"] and r.get("party"):
                    self.draft["party_name"], self.draft["party_phone"] = r["party"], r.get("phone", "")
            except ValueError as ex:
                skipped.append(f"Line {n}: {ex}")
        self._redraw_lines()
        msg = f"Added {added} line(s) to this invoice."
        if skipped:
            msg += f"\n{len(skipped)} skipped:\n" + "\n".join(skipped[:8])
        ui.info(msg)

    def sample_sheet(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"{self.kind}_sample.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            write_csv(path, ["party", "phone", "product", "description", "qty", "price"],
                      [["Ali Traders", "0300-1234567", "Sample product", "Blue, size M", "2", "1500"],
                       ["Ali Traders", "0300-1234567", "Another product", "", "1", "750"]])
            ui.info("Sample sheet saved. Each row is one product line.\n"
                    "The party name on the first row is applied to the invoice.")

    def export_history(self):
        rows = self.app.db.invoices(self.kind, self._date(self.from_entry), self._date(self.to_entry),
                                    self.search_entry.get().strip())
        if not rows:
            ui.info("Nothing to export for this period.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"{self.kind}_history.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            write_csv(path, ["invoice_no", "party", "total", "paid", "due", "status", "date"],
                      [[r["invoice_no"], r["party"] or "", r["total"], r["paid"], r["due"], r["status"],
                        r["created_at"]] for r in rows])
            ui.info(f"Exported {len(rows)} invoice(s).")

    def export_receipt(self):
        self._sync()
        if not self.draft["lines"]:
            ui.error("Add products first, then export the receipt.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="receipt.txt",
                                            filetypes=[("Text file", "*.txt")])
        if not path:
            return
        _, _, _, total = self._amounts()
        out = [self.app.user["business_name"],
               f"{self.info['title']} receipt  ·  {datetime.now():%Y-%m-%d %H:%M}",
               f"Date: {self.draft['entry_date']}",
               f"{self.info['party']}: {self.draft['party_name'] or 'Walk-in'}", "-" * 64]
        for l in self.draft["lines"]:
            out.append(f"{l['name'][:30]:<30} {l['qty']:>6g} x {l['price']:>9,.2f} {l['qty'] * l['price']:>10,.2f}")
            if l.get("desc"):
                out.append(f"    {l['desc'][:58]}")
        out += ["-" * 64, f"TOTAL  {total:,.2f} {self.app.user['currency']}"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        ui.info("Receipt saved.")

    # ------------------------------------------------------------ shortcuts
    def on_new(self):
        self.clear_draft()

    def on_search(self):
        self.search_entry.focus_set()


class InvoiceDialog:
    """Invoice details: lines, payment history, add payment, receipt, delete."""

    def __init__(self, page, inv_id):
        self.page = page
        self.app = page.app
        self.kind = page.kind
        self.inv_id = inv_id
        self.win = tk.Toplevel(self.app.root)
        self.win.title("Invoice details")
        self.win.configure(bg=ui.C["card"])
        self.win.geometry("820x640")
        self.win.transient(self.app.root)
        self.render()

    def render(self):
        for w in self.win.winfo_children():
            w.destroy()
        db, cur = self.app.db, self.app.user["currency"]
        inv = db.invoice_detail(self.kind, self.inv_id)
        if not inv:
            ui.error("This invoice no longer exists.")
            self.win.destroy()
            return
        due = round(inv["total"] - inv["paid"], 2)
        party = inv.get("customer_name") or inv.get("supplier_name") or "Walk-in"
        top = tk.Frame(self.win, bg=ui.C["card"], padx=22, pady=16)
        top.pack(fill="x")
        tk.Label(top, text=inv["invoice_no"], font=ui.font(16, True), bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(top, text=f"{party}   ·   {inv['created_at'][:16].replace('T', ' ')}   ·   {inv['payment_method'] or ''}",
                 font=ui.font(10), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(2, 0))

        table = ui.Table(self.win, [("p", "Product", 200, "w"), ("d", "Description", 240, "w"),
                                    ("q", "Qty", 60, "e"), ("u", "Price", 100, "e"), ("a", "Amount", 110, "e")], height=6)
        table.pack(fill="both", expand=True, padx=22)
        table.set_rows([(i, (it["product_name"], it.get("description") or "", f"{it['qty']:g}",
                             f"{it['unit_price']:,.2f}", f"{it['line_total']:,.2f}"), None)
                        for i, it in enumerate(inv["items"])])

        body = tk.Frame(self.win, bg=ui.C["card"], padx=22, pady=10)
        body.pack(fill="x")
        left = tk.Frame(body, bg=ui.C["card"])
        left.pack(side="left", fill="y")
        for label, value in [("Subtotal", inv["subtotal"]), ("Discount", inv["discount"]), ("Tax", inv["tax"]),
                             ("Total", inv["total"]), ("Paid", inv["paid"]), ("Balance due", max(due, 0))]:
            row = tk.Frame(left, bg=ui.C["card"])
            row.pack(fill="x")
            tk.Label(row, text=label, width=12, anchor="w", font=ui.font(10), bg=ui.C["card"], fg=ui.C["muted"]).pack(side="left")
            tk.Label(row, text=f"{value:,.2f} {cur}", font=ui.font(10, True), bg=ui.C["card"], fg=ui.C["fg"]).pack(side="left")

        pay = ui.card(body, pad=12)
        pay.pack(side="right", fill="x")
        ui.section_label(pay, "Record a payment").pack(anchor="w")
        amt_wrap, self.pay_amount = ui.field(pay, "Amount", width=14, bg=ui.C["card"])
        amt_wrap.pack(fill="x", pady=4)
        tk.Label(pay, text="Method", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.pay_method = ttk.Combobox(pay, values=[m for m in PAYMENT_METHODS if m != "Credit"], state="readonly")
        self.pay_method.set("Cash")
        self.pay_method.pack(fill="x", ipady=3)
        ui.Button(pay, "Add payment", self._pay, "primary", bg=ui.C["card"]).pack(fill="x", pady=(8, 0))

        hist = ui.Table(self.win, [("when", "Date", 170, "w"), ("method", "Method", 160, "w"),
                                   ("amount", "Amount", 120, "e")], height=3)
        hist.pack(fill="x", padx=22, pady=(6, 0))
        hist.set_rows([(p["id"], (p["paid_at"][:16].replace("T", " "), p["method"] or "", f"{p['amount']:,.2f}"), None)
                       for p in db.payments(self.kind, self.inv_id)])

        foot = tk.Frame(self.win, bg=ui.C["card"], padx=22, pady=14)
        foot.pack(fill="x", side="bottom")
        ui.Button(foot, "Delete invoice", self._delete, "danger", bg=ui.C["card"]).pack(side="left")
        ui.Button(foot, "Receipt (.txt)", lambda: self._receipt(inv), "secondary", bg=ui.C["card"]).pack(side="right")
        ui.Button(foot, "Share on WhatsApp", lambda: self.page.share_invoice(self.inv_id), "primary",
                  bg=ui.C["card"]).pack(side="right", padx=8)
        ui.Button(foot, "Close", self.win.destroy, "secondary", bg=ui.C["card"]).pack(side="right", padx=8)

    def _pay(self):
        try:
            amount = to_float(self.pay_amount.get(), 0)
        except ValueError:
            ui.error("Enter a valid amount.")
            return
        if amount <= 0:
            ui.error("Enter an amount above 0.")
            return
        try:
            applied = self.app.db.record_payment(self.kind, self.inv_id, amount, method=self.pay_method.get())
        except ValueError as ex:
            ui.error(str(ex))
            return
        self.app.notify(f"Payment of {applied:,.2f} recorded and posted to the ledger.")
        self.page.refresh_history()
        self.render()

    def _delete(self):
        if not ui.ask("Delete this invoice? Stock and ledger entries will be reversed."):
            return
        self.app.db.delete_invoice(self.kind, self.inv_id)
        self.app.notify("Invoice deleted. Stock and ledger restored.")
        self.page.refresh_history()
        self.win.destroy()

    def _receipt(self, inv):
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=f"{inv['invoice_no']}.txt",
                                            filetypes=[("Text file", "*.txt")])
        if not path:
            return
        party = inv.get("customer_name") or inv.get("supplier_name") or "Walk-in"
        out = [self.app.user["business_name"], f"Invoice {inv['invoice_no']}  ·  {inv['created_at'][:16]}",
               f"Party: {party}", "-" * 64]
        for it in inv["items"]:
            out.append(f"{it['product_name'][:30]:<30} {it['qty']:>6g} x {it['unit_price']:>9,.2f} {it['line_total']:>10,.2f}")
            if it.get("description"):
                out.append(f"    {it['description'][:58]}")
        out += ["-" * 64, f"Total {inv['total']:,.2f}   Paid {inv['paid']:,.2f}   Due {max(inv['total'] - inv['paid'], 0):,.2f}"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        ui.info("Receipt saved.")
