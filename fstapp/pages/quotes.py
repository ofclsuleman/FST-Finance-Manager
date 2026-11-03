"""Quotation maker: build a quote, track its status, convert it to a sale."""
import json
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog

from .. import ui_kit as ui
from ..config import WALK_IN
from ..csv_io import to_float

STATUS_TAG = {"Draft": None, "Sent": "warn", "Accepted": "good", "Rejected": "bad", "Converted": "good"}


class QuotationPage:
    def __init__(self, app):
        self.app = app
        self.draft = {
            "lines": [], "party_id": None, "party_label": "", "party_name": "", "party_phone": "",
            "discount": "0", "tax": app.db.get_setting("default_tax_rate", "0"),
            "valid": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"), "note": "",
        }
        self._discard = False

    # ------------------------------------------------------------ build
    def build(self, parent):
        self._discard = False
        cur = self.app.user["currency"]
        ui.page_header(parent, "Quotations",
                       "Create a quote, send it to the customer, then convert it to a sale when accepted."
                       ).pack(fill="x", pady=(0, 10))
        d = self.draft

        party = ui.card(parent, pad=14)
        party.pack(fill="x")
        pick_wrap = tk.Frame(party, bg=ui.C["card"])
        pick_wrap.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        tk.Label(pick_wrap, text="Customer (type to search, or pick a saved one)", font=ui.font(9),
                 bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.picker = ui.Picker(pick_wrap, self._provider, width=36, on_pick=self._on_pick)
        self.picker.pack(fill="x", ipady=4)
        self.picker.set(d["party_label"] or d["party_name"] or WALK_IN)
        self.phone_wrap, self.phone = ui.field(party, "Phone", width=16, value=d["party_phone"])
        self.phone_wrap.grid(row=0, column=1, padx=8, sticky="ew")
        self.valid_wrap, self.valid = ui.field(party, "Valid until (YYYY-MM-DD)", width=14, value=d["valid"])
        self.valid_wrap.grid(row=0, column=2, padx=8, sticky="ew")
        party.columnconfigure(0, weight=1)

        add = ui.card(parent, pad=14)
        add.pack(fill="x", pady=10)
        desc_wrap = tk.Frame(add, bg=ui.C["card"])
        desc_wrap.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        tk.Label(desc_wrap, text="Item / product (type to search)", font=ui.font(9), bg=ui.C["card"],
                 fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.prod = ui.Picker(desc_wrap, self.app.db.product_options, width=36, on_pick=self._on_product)
        self.prod.pack(fill="x", ipady=4)
        self.qty_wrap, self.qty = ui.field(add, "Qty", width=8, value="1")
        self.qty_wrap.grid(row=0, column=1, padx=8, sticky="ew")
        self.price_wrap, self.price = ui.field(add, f"Unit price ({cur})", width=14)
        self.price_wrap.grid(row=0, column=2, padx=8, sticky="ew")
        self.qty.bind("<Return>", lambda e: self.add_line())
        self.price.bind("<Return>", lambda e: self.add_line())
        ui.Button(add, "+ Add item", self.add_line, "primary", bg=ui.C["card"]).grid(row=0, column=3, padx=8, sticky="s")
        add.columnconfigure(0, weight=1)

        body = tk.Frame(parent, bg=ui.C["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        lines = ui.card(body, pad=12)
        lines.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.lines_table = ui.Table(lines, [("item", "Item", 280, "w"), ("qty", "Qty", 70, "e"),
                                            ("price", "Unit price", 120, "e"), ("amount", "Amount", 130, "e")],
                                    height=6)
        self.lines_table.pack(fill="both", expand=True)
        ui.Button(lines, "Remove selected", self.remove_lines, "secondary", bg=ui.C["card"]).pack(anchor="w", pady=(8, 0))

        totals = ui.card(body, pad=16)
        totals.grid(row=0, column=1, sticky="nsew")
        self.discount_wrap, self.discount = ui.field(totals, "Discount (amount)", width=14, value=d["discount"], bg=ui.C["card"])
        self.discount_wrap.pack(fill="x", pady=4)
        self.tax_wrap, self.tax = ui.field(totals, "Tax (%)", width=14, value=d["tax"], bg=ui.C["card"])
        self.tax_wrap.pack(fill="x", pady=4)
        self.total_lbl = tk.Label(totals, text="", font=ui.font(18, True), bg=ui.C["card"], fg=ui.C["accent"])
        self.total_lbl.pack(anchor="e", pady=(12, 6))
        self.note_wrap, self.note = ui.field(totals, "Terms / note", width=14, value=d["note"], bg=ui.C["card"])
        self.note_wrap.pack(fill="x", pady=4)
        for entry in (self.discount, self.tax):
            entry.bind("<KeyRelease>", lambda e: self._refresh_totals())
        row = tk.Frame(totals, bg=ui.C["card"])
        row.pack(fill="x", pady=(12, 0))
        ui.Button(row, "Save quotation", self.save, "primary", bg=ui.C["card"]).pack(side="left", fill="x", expand=True)
        ui.Button(row, "Export (.txt)", self.export_text, "secondary", bg=ui.C["card"]).pack(side="left", fill="x", expand=True, padx=(6, 0))
        ui.Button(totals, "Clear quote", self.clear, "ghost", bg=ui.C["card"]).pack(anchor="w", pady=(8, 0))

        listing = ui.card(parent, pad=12)
        listing.pack(fill="both", expand=True, pady=(10, 0))
        top = tk.Frame(listing, bg=ui.C["card"])
        top.pack(fill="x", pady=(0, 8))
        ui.section_label(top, "Saved quotations").pack(side="left")
        self.search_wrap, self.search = ui.field(top, "Search", width=26, bg=ui.C["card"])
        self.search_wrap.pack(side="right")
        self.search.bind("<KeyRelease>", lambda e: self.refresh_list())
        self.list_table = ui.Table(listing, [("no", "Quote", 160, "w"), ("cust", "Customer", 220, "w"),
                                             ("total", "Total", 130, "e"), ("status", "Status", 110, "w"),
                                             ("valid", "Valid until", 120, "w"), ("date", "Created", 150, "w")],
                                   height=6)
        self.list_table.pack(fill="both", expand=True)
        foot = tk.Frame(listing, bg=ui.C["card"])
        foot.pack(fill="x", pady=(8, 0))
        for label, status in [("Mark sent", "Sent"), ("Accepted", "Accepted"), ("Rejected", "Rejected")]:
            ui.Button(foot, label, lambda s=status: self.set_status(s), "secondary", bg=ui.C["card"]).pack(side="left", padx=(0, 6))
        ui.Button(foot, "Convert to sale", self.convert, "primary", bg=ui.C["card"]).pack(side="right")

        self._redraw_lines()
        self.refresh_list()

    # ------------------------------------------------------------ pickers / sync
    def _provider(self, term):
        opts = [(WALK_IN, None)] if not term else []
        return opts + self.app.db.contact_options("customers", term)

    def _on_pick(self, label, value):
        d = self.draft
        if value is None:
            d.update(party_id=None, party_label="", party_name="", party_phone="")
        else:
            d.update(party_id=value["id"], party_label=label, party_name=value["name"], party_phone=value["phone"] or "")
            ui.set_entry(self.phone, d["party_phone"])

    def _on_product(self, label, value):
        if value:
            self.prod.set(value["name"])
            ui.set_entry(self.price, f"{value['sale_price']:g}")
            self.qty.focus_set()

    def leave(self):
        """Save widget values into the draft before the page is redrawn."""
        if self._discard:
            return
        try:
            d = self.draft
            text = self.picker.get().strip()
            text = "" if text == WALK_IN else text
            if d["party_id"] and text != d["party_label"]:
                d["party_id"], d["party_label"] = None, ""
            d["party_name"] = text
            d["party_phone"] = self.phone.get().strip()
            d["discount"], d["tax"] = self.discount.get(), self.tax.get()
            d["valid"], d["note"] = self.valid.get().strip(), self.note.get()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ lines & totals
    def add_line(self):
        name = self.prod.get().strip()
        try:
            qty, price = to_float(self.qty.get(), 0), to_float(self.price.get(), -1)
        except ValueError:
            ui.error("Quantity and price must be numbers.")
            return
        if not name or qty <= 0 or price < 0:
            ui.error("Enter an item, a quantity above 0 and a valid price.")
            return
        product = self.prod.selected()
        self.draft["lines"].append({"product_id": product["id"] if product else None,
                                    "name": product["name"] if product else name, "qty": qty, "price": price})
        self.prod.set("")
        ui.set_entry(self.qty, "1")
        ui.set_entry(self.price, "")
        self._redraw_lines()

    def remove_lines(self):
        for idx in sorted(self.lines_table.selected_ids(), reverse=True):
            if 0 <= idx < len(self.draft["lines"]):
                self.draft["lines"].pop(idx)
        self._redraw_lines()

    def _redraw_lines(self):
        self.lines_table.set_rows([(i, (l["name"], f"{l['qty']:g}", f"{l['price']:,.2f}",
                                        f"{l['qty'] * l['price']:,.2f}"), None)
                                   for i, l in enumerate(self.draft["lines"])])
        self._refresh_totals()

    def _amounts(self):
        lines = self.draft["lines"]
        subtotal = sum(l["qty"] * l["price"] for l in lines)
        try:
            discount = min(max(to_float(self.discount.get()), 0), subtotal)
            rate = to_float(self.tax.get())
        except (ValueError, tk.TclError):
            discount, rate = 0.0, 0.0
        tax = round((subtotal - discount) * rate / 100, 2)
        return subtotal, discount, tax, round(subtotal - discount + tax, 2)

    def _refresh_totals(self):
        _, _, _, total = self._amounts()
        self.total_lbl.configure(text=f"Total  {total:,.2f} {self.app.user['currency']}")

    def clear(self):
        self.draft.update(lines=[], party_id=None, party_label="", party_name="", party_phone="",
                          note="", discount="0", tax=self.app.db.get_setting("default_tax_rate", "0"),
                          valid=(datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"))
        self._discard = True
        self.app.refresh_current()

    # ------------------------------------------------------------ save / list / status
    def save(self):
        self.leave()
        d = self.draft
        if not d["lines"]:
            ui.error("Add at least one item to the quotation.")
            return
        db = self.app.db
        party_id, name = d["party_id"], d["party_name"]
        if name and not party_id:
            match = db.one("SELECT id FROM customers WHERE name=? COLLATE NOCASE", (name,))
            party_id = match["id"] if match else None
        _, discount, _, _ = self._amounts()
        try:
            qno = db.save_quotation(d["lines"], party_id, name, d["party_phone"], d["valid"],
                                    discount=discount, tax_rate=to_float(d["tax"], 0), note=d["note"])
        except Exception as ex:
            ui.error(f"Could not save the quotation:\n{ex}")
            return
        self.app.notify(f"Quotation {qno} saved.")
        self.clear()

    def _selected_quote(self):
        qid = self.list_table.first_selected()
        if qid is None:
            ui.error("Select a quotation in the list first.")
        return qid

    def set_status(self, status):
        qid = self._selected_quote()
        if qid:
            self.app.db.set_quotation_status(qid, status)
            self.refresh_list()

    def convert(self):
        qid = self._selected_quote()
        if not qid:
            return
        q = self.app.db.one("SELECT * FROM quotations WHERE id=?", (qid,))
        if q["status"] == "Converted":
            ui.info("This quotation was already converted to a sale.")
            return
        sales = self.app.pages["Sales"]
        sales.draft.update(lines=[dict(l) for l in json.loads(q["items_json"])],
                           party_id=q["customer_id"],
                           party_label=(f"{q['customer_name']}  ·  {q['customer_phone']}" if q["customer_phone"] else (q["customer_name"] or "")),
                           party_name=q["customer_name"] or "", party_phone=q["customer_phone"] or "",
                           discount=f"{q['discount']:g}", note=f"From quotation {q['quote_no']}")
        self.app.db.set_quotation_status(qid, "Converted")
        self.app.notify("Quotation loaded into a new sale. Review it and save.")
        self.app.go("Sales")

    def refresh_list(self):
        rows = []
        for q in self.app.db.quotations(self.search.get().strip()):
            rows.append((q["id"], (q["quote_no"], q["customer_name"] or "Walk-in",
                                   f"{q['total']:,.2f}", q["status"], q["valid_until"] or "",
                                   q["created_at"][:16].replace("T", " ")), STATUS_TAG.get(q["status"])))
        self.list_table.set_rows(rows)

    def export_text(self):
        self.leave()
        if not self.draft["lines"]:
            ui.error("Add items first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="quotation.txt",
                                            filetypes=[("Text file", "*.txt")])
        if not path:
            return
        cur = self.app.user["currency"]
        subtotal, discount, tax, total = self._amounts()
        out = [self.app.user["business_name"], "QUOTATION", f"Date: {datetime.now():%Y-%m-%d}",
               f"To: {self.draft['party_name'] or 'Customer'}  {self.draft['party_phone']}".rstrip(),
               f"Valid until: {self.draft['valid'] or '-'}", "-" * 60]
        for l in self.draft["lines"]:
            out.append(f"{l['name'][:30]:<30} {l['qty']:>6g} x {l['price']:>10,.2f} = {l['qty'] * l['price']:>12,.2f}")
        out += ["-" * 60, f"Subtotal {subtotal:,.2f}", f"Discount {discount:,.2f}", f"Tax {tax:,.2f}",
                f"TOTAL {total:,.2f} {cur}"]
        if self.draft["note"]:
            out += ["", "Terms: " + self.draft["note"]]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        ui.info("Quotation exported.")

    def on_new(self):
        self.clear()

    def on_search(self):
        self.search.focus_set()
