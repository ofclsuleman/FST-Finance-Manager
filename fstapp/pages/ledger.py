"""Ledger: accounts and balances, journal, account and party statements, quick entries."""
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, ttk

from .. import ui_kit as ui
from ..csv_io import to_float, write_csv
from ..ledger import CAPITAL, BANK, CASH, DRAWINGS, OTHER_INCOME, COGS
from ..customer_report import collect as collect_details, write_csv as write_details_csv, write_pdf as write_details_pdf
from ..ledger_export import safe_name, write_all_ledgers_csv, write_statement_csv
from .receive import open_receive_payment

VIEWS = [("party", "Customer / supplier ledger")]
ACCOUNT_TYPES = ["asset", "liability", "equity", "income", "expense"]
ALL_FROM, ALL_TO = "0000-00-00", "9999-12-31"


class LedgerPage:
    def __init__(self, app):
        self.app = app
        self.view = "party"
        now = datetime.now()
        self.date_from = now.replace(day=1).strftime("%Y-%m-%d")
        self.date_to = now.strftime("%Y-%m-%d")
        self.account_ids = {}
        self.party_value = None  # the customer/supplier whose statement is open
        self.kind_name = "Customer"

    # ------------------------------------------------------------ frame
    def build(self, parent):
        ui.page_header(parent, "Ledger", "Customer and supplier ledgers. Sales, purchases and payments post automatically."
                       ).pack(fill="x", pady=(0, 10))
        tabs = tk.Frame(parent, bg=ui.C["bg"])
        tabs.pack(fill="x", pady=(0, 10))
        self.tab_buttons = {}
        for key, label in VIEWS:
            btn = tk.Label(tabs, text=label, font=ui.font(10), padx=14, pady=8, cursor="hand2")
            btn.pack(side="left", padx=(0, 4))
            btn.bind("<Button-1>", lambda e, k=key: self.switch(k))
            self.tab_buttons[key] = btn
        bar = ui.card(parent, pad=10)
        bar.pack(fill="x")
        self.from_wrap, self.from_e = ui.date_field(bar, "From (blank = beginning)", width=16, value=self.date_from, bg=ui.C["card"])
        self.from_wrap.pack(side="left", padx=(0, 8))
        self.to_wrap, self.to_e = ui.date_field(bar, "To (blank = today)", width=16, value=self.date_to, bg=ui.C["card"])
        self.to_wrap.pack(side="left", padx=(0, 8))
        ui.Button(bar, "Apply period", self._apply_period, "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        for label, mode in [("This month", "month"), ("This year", "year"), ("All time", "all")]:
            ui.Button(bar, label, lambda m=mode: self._preset(m), "ghost", bg=ui.C["card"]).pack(side="left", padx=3, pady=(14, 0))
        self.body = tk.Frame(parent, bg=ui.C["bg"])
        self.body.pack(fill="both", expand=True, pady=(10, 0))
        self.switch(self.view)

    def switch(self, key):
        self.view = key
        for k, btn in self.tab_buttons.items():
            active = k == key
            btn.configure(bg=ui.C["accent"] if active else ui.C["card"],
                          fg=ui.C["accent_fg"] if active else ui.C["fg"], font=ui.font(10, active))
        for w in self.body.winfo_children():
            w.destroy()
        getattr(self, f"_view_{key}")(self.body)

    def _apply_period(self):
        def parse(entry, fallback):
            text = entry.get().strip()
            return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d") if text else fallback
        try:
            start = parse(self.from_e, ALL_FROM)
            end = parse(self.to_e, ALL_TO)
        except ValueError:
            ui.error("Dates must look like 2026-11-01, or leave a box blank for no limit.")
            return
        if start > end:
            ui.error("The 'From' date must be before the 'To' date.")
            return
        self.date_from, self.date_to = start, end
        self.switch(self.view)

    def _preset(self, mode):
        now = datetime.now()
        if mode == "all":
            start, end = "", ""
        elif mode == "year":
            start, end = now.replace(month=1, day=1).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        else:
            start, end = now.replace(day=1).strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
        ui.set_entry(self.from_e, start)
        ui.set_entry(self.to_e, end)
        self._apply_period()

    def _period(self):
        return self.date_from, self.date_to

    def _period_label(self):
        start, end = self._period()
        if start == ALL_FROM and end == ALL_TO:
            return "all time"
        return f"{'beginning' if start == ALL_FROM else start} to {'today' if end == ALL_TO else end}"

    def _cur(self):
        return self.app.user["currency"]

    def _account_picker(self, parent, codes=None, label="Account", width=34):
        """Combobox of accounts. Returns (wrap, combobox, mapping label->code)."""
        accounts = [a for a in self.app.db.accounts() if codes is None or a["code"] in codes]
        mapping = {f"{a['code']}  ·  {a['name']}": a["code"] for a in accounts}
        wrap = tk.Frame(parent, bg=ui.C["card"])
        tk.Label(wrap, text=label, font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        cb = ttk.Combobox(wrap, values=list(mapping), state="readonly", width=width, font=ui.font(10))
        if mapping:
            cb.set(next(iter(mapping)))
        cb.pack(fill="x", ipady=4)
        return wrap, cb, mapping

    # ------------------------------------------------------------ accounts & balances
    def _view_accounts(self, parent):
        start, end = self._period()
        rows = self.app.db.trial_balance(start, end)
        table = ui.Table(parent, [("code", "Code", 80, "w"), ("name", "Account", 300, "w"), ("type", "Type", 110, "w"),
                                  ("dr", "Debits", 140, "e"), ("cr", "Credits", 140, "e"),
                                  ("bal", "Balance", 150, "e")], height=14)
        table.pack(fill="both", expand=True)
        out = []
        for r in rows:
            out.append((r["id"], (r["code"], r["name"], r["type"].title(), f"{r['dr']:,.2f}", f"{r['cr']:,.2f}",
                                  f"{r['balance']:,.2f}"), None if r["balance"] >= 0 else "warn"))
        table.set_rows(out)
        form = ui.card(parent, pad=12)
        form.pack(fill="x", pady=(10, 0))
        ui.section_label(form, "Add an account").pack(anchor="w")
        row = tk.Frame(form, bg=ui.C["card"])
        row.pack(fill="x", pady=(6, 0))
        name_wrap, self.new_name = ui.field(row, "Account name", width=40, bg=ui.C["card"])
        name_wrap.pack(side="left", padx=(0, 8))
        tk.Label(row, text="Type", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(side="left", padx=(0, 4))
        self.new_type = ttk.Combobox(row, values=ACCOUNT_TYPES, state="readonly", width=12, font=ui.font(10))
        self.new_type.set("expense")
        self.new_type.pack(side="left", padx=(0, 8), pady=(14, 0), ipady=3)
        ui.Button(row, "Add account", self._add_account, "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        tk.Label(form, text="Balances follow normal sign: assets and expenses are shown as debit balances; "
                            "liabilities, equity and income as credit balances.",
                 font=ui.font(8), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(8, 0))

    def _add_account(self):
        name = self.new_name.get().strip()
        if not name:
            ui.error("Enter a name for the account.")
            return
        code = self.app.db.add_account(name, self.new_type.get())
        self.app.notify(f"Account {code} · {name} added.")
        self.switch("accounts")

    # ------------------------------------------------------------ journal
    def _view_journal(self, parent):
        start, end = self._period()
        entries = self.app.db.journal(start, end)
        table = ui.Table(parent, [("date", "Date", 100, "w"), ("ref", "Reference", 170, "w"),
                                  ("memo", "Description", 380, "w"), ("total", "Amount", 130, "e"),
                                  ("kind", "Source", 130, "w")], height=14,
                         on_double=lambda: self._open_entry(table))
        table.pack(fill="both", expand=True)
        self._entries = {e["id"]: e for e in entries}
        table.set_rows([(e["id"], (e["entry_date"], e["ref_no"] or "", e["memo"] or "", f"{e['total']:,.2f}",
                                   e["ref_type"].replace("_", " ").title()), None) for e in entries])
        foot = tk.Frame(parent, bg=ui.C["bg"])
        foot.pack(fill="x", pady=(8, 0))
        ui.Button(foot, "Show selected entry", lambda: self._open_entry(table), "secondary", bg=ui.C["bg"]).pack(side="left")
        ui.Button(foot, "Delete selected manual entry", lambda: self._delete_entry(table), "danger", bg=ui.C["bg"]).pack(side="left", padx=8)
        tk.Label(foot, text="Invoice entries are removed by deleting the invoice.", font=ui.font(9),
                 bg=ui.C["bg"], fg=ui.C["muted"]).pack(side="left", padx=8)

    def _open_entry(self, table):
        eid = table.first_selected()
        if eid is None:
            ui.error("Select a journal entry first.")
            return
        e = self._entries.get(eid)
        win = tk.Toplevel(self.app.root)
        win.title(e["ref_no"] or "Journal entry")
        win.configure(bg=ui.C["card"])
        win.geometry("680x360")
        win.transient(self.app.root)
        tk.Label(win, text=f"{e['entry_date']}  ·  {e['memo'] or ''}", font=ui.font(12, True),
                 bg=ui.C["card"], fg=ui.C["fg"], wraplength=640, justify="left").pack(anchor="w", padx=20, pady=(16, 8))
        lines = ui.Table(win, [("code", "Code", 80, "w"), ("acct", "Account", 300, "w"),
                               ("dr", "Debit", 120, "e"), ("cr", "Credit", 120, "e")], height=8)
        lines.pack(fill="both", expand=True, padx=20)
        lines.set_rows([(i, (l["code"], l["name"], f"{l['debit']:,.2f}" if l["debit"] else "",
                             f"{l['credit']:,.2f}" if l["credit"] else ""), None) for i, l in enumerate(e["lines"])])
        ui.Button(win, "Close", win.destroy, "secondary", bg=ui.C["card"]).pack(pady=12)

    def _delete_entry(self, table):
        eid = table.first_selected()
        if eid is None:
            ui.error("Select a journal entry first.")
            return
        if not ui.ask("Delete this journal entry? This cannot be undone."):
            return
        try:
            self.app.db.delete_manual_entry(eid)
        except ValueError as ex:
            ui.error(str(ex))
            return
        self.app.notify("Entry deleted.")
        self.switch("journal")

    # ------------------------------------------------------------ account statement
    def _view_account(self, parent):
        start, end = self._period()
        top = ui.card(parent, pad=12)
        top.pack(fill="x")
        wrap, self.acct_cb, self.acct_map = self._account_picker(top, label="Account", width=52)
        wrap.pack(side="left", padx=(0, 10))
        ui.Button(top, "Show statement", lambda: self._render_statement(parent, "account"), "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        self.stmt_holder = tk.Frame(parent, bg=ui.C["bg"])
        self.stmt_holder.pack(fill="both", expand=True, pady=(10, 0))
        if self.acct_map:
            self._render_statement(parent, "account")

    # ------------------------------------------------------------ party statement
    def _view_party(self, parent):
        top = ui.card(parent, pad=12)
        top.pack(fill="x")
        kind_wrap = tk.Frame(top, bg=ui.C["card"])
        kind_wrap.pack(side="left", padx=(0, 10))
        tk.Label(kind_wrap, text="Party", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(fill="x")
        self.party_kind = ttk.Combobox(kind_wrap, values=["Customer", "Supplier"], state="readonly", width=14, font=ui.font(10))
        self.party_kind.set(self.kind_name)
        self.party_kind.pack(ipady=4)
        self.party_kind.bind("<<ComboboxSelected>>", lambda e: self._change_kind())
        pick_wrap = tk.Frame(top, bg=ui.C["card"])
        pick_wrap.pack(side="left", padx=(0, 10))
        tk.Label(pick_wrap, text="Name (type to search, or click the arrow)", font=ui.font(9),
                 bg=ui.C["card"], fg=ui.C["muted"]).pack(fill="x")
        self.party_picker = ui.Picker(pick_wrap, self._party_options, width=40)
        self.party_picker.pack(fill="x", ipady=4)
        self.party_picker.bind("<<ComboboxSelected>>", lambda e: self._pick_party(), add="+")
        if self.party_value:
            self.party_picker.set(self.party_value["name"])
        ui.Button(top, "Show statement", self._render_party, "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        if self.kind_name == "Customer":
            ui.Button(top, "Receive payment", self._receive_payment, "secondary", bg=ui.C["card"]).pack(side="left", padx=8, pady=(14, 0))
        exports = tk.Frame(parent, bg=ui.C["bg"])
        exports.pack(fill="x", pady=(8, 0))
        ui.Button(exports, "Export this statement (CSV)", self._export_statement, "secondary",
                  bg=ui.C["bg"]).pack(side="left")
        ui.Button(exports, f"Export all {self.kind_name.lower()}s (CSV)", self._export_all, "secondary",
                  bg=ui.C["bg"]).pack(side="left", padx=8)
        if self.kind_name == "Customer":
            ui.Button(exports, "Customer details (CSV)", lambda: self._export_details("csv"), "primary",
                      bg=ui.C["bg"]).pack(side="left", padx=8)
            ui.Button(exports, "Print / save PDF", lambda: self._export_details("pdf"), "primary",
                      bg=ui.C["bg"]).pack(side="left")
        self.stmt_holder = tk.Frame(parent, bg=ui.C["bg"])
        self.stmt_holder.pack(fill="both", expand=True, pady=(10, 0))
        if self.party_value:
            self._render_party()

    def _change_kind(self):
        self.kind_name = self.party_kind.get()
        self.party_value = None
        self.switch("party")

    def _party_options(self, term):
        table = "customers" if self.party_kind.get() == "Customer" else "suppliers"
        return self.app.db.contact_options(table, term)

    def _pick_party(self):
        party = self.party_picker.selected()
        if party:
            self.party_value = party
            self._render_party()

    def _match_party_name(self):
        """Fallback when a name is typed without picking it from the list."""
        text = self.party_picker.get().strip().split("  ·  ")[0].strip()
        if not text:
            return None
        table = "customers" if self.party_kind.get() == "Customer" else "suppliers"
        return self.app.db.one(f"SELECT id, name FROM {table} WHERE name=? COLLATE NOCASE", (text,))

    def _render_party(self):
        party = self.party_value or self._match_party_name()
        if not party:
            ui.error("Pick a saved customer or supplier from the list.")
            return
        self.party_value = party
        kind = "customer" if self.party_kind.get() == "Customer" else "supplier"
        start, end = self._period()
        st = self.app.db.party_statement(kind, party["id"], start, end)
        self._last_export = (party, kind, start, end, st)
        self._show_statement(st, title=f"{party['name']} — {kind} statement  ·  {self._period_label()}")

    def _receive_payment(self):
        party = self.party_value or self._match_party_name()
        if not party:
            ui.error("Pick a saved customer from the list first.")
            return
        self.party_value = party
        open_receive_payment(self.app, party, self._render_party)

    # ------------------------------------------------------------ export
    def _export_details(self, fmt):
        """Every invoice of the selected customer, with products, descriptions, payments and balances."""
        party = self.party_value or self._match_party_name()
        if not party or self.party_kind.get() != "Customer":
            ui.error("Pick a customer from the list first.")
            return
        start, end = self._period()
        data = collect_details(self.app.db, party["id"], start, end)
        if not data["invoices"] and not data["outstanding_now"]:
            ui.error("This customer has no invoices or payments in this period.")
            return
        base = f"{safe_name(party['name'])}_details"
        if fmt == "csv":
            path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=base + ".csv",
                                                filetypes=[("CSV file (opens in Excel)", "*.csv")])
            if not path:
                return
            write_details_csv(path, data, self.app.user["business_name"], self._cur())
            ui.info("Customer ledger exported. Every product and payment is a row, with totals at the top.")
        else:
            path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=base + ".pdf",
                                                filetypes=[("PDF file", "*.pdf")])
            if not path:
                return
            write_details_pdf(path, data, self.app.user["business_name"], self._cur())
            ui.info("PDF saved. Open it and print from your PDF viewer.")

    def _export_statement(self):
        if not getattr(self, "_last_export", None):
            ui.error("Show a statement first, then export it.")
            return
        party, kind, start, end, st = self._last_export
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV file (opens in Excel)", "*.csv")],
                                            initialfile=f"{kind}_{safe_name(party['name'])}_statement.csv")
        if not path:
            return
        write_statement_csv(path, self.app.user["business_name"], kind, party, st, start, end,
                            self._period_label(), self._cur())
        ui.info("Statement exported with every movement and both balances.")

    def _export_all(self):
        kind = "customer" if self.party_kind.get() == "Customer" else "supplier"
        start, end = self._period()
        blocks = self.app.db.party_ledger_blocks(kind, start, end)
        if not blocks:
            ui.error(f"No {kind}s have entries or balances in this period.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV file (opens in Excel)", "*.csv")],
                                            initialfile=f"all_{kind}s_ledger.csv")
        if not path:
            return
        write_all_ledgers_csv(path, self.app.user["business_name"], kind, blocks, start, end,
                              self._period_label(), self._cur())
        ui.info(f"Exported the ledger of {len(blocks)} {kind}s.")

    def _render_statement(self, parent, _mode):
        label = self.acct_cb.get()
        if not label or label not in self.acct_map:
            return
        account_id = self.app.db.one("SELECT id FROM accounts WHERE code=?", (self.acct_map[label],))["id"]
        start, end = self._period()
        st = self.app.db.account_statement(account_id, start, end)
        self._show_statement(st, title=f"{st['account']['code']} · {st['account']['name']}")

    def _show_statement(self, st, title):
        for w in self.stmt_holder.winfo_children():
            w.destroy()
        cur = self._cur()
        tiles = tk.Frame(self.stmt_holder, bg=ui.C["bg"])
        tiles.pack(fill="x", pady=(0, 8))
        for i, (label, value) in enumerate([("Opening balance", st["opening"]), ("Closing balance", st["closing"])]):
            ui.stat_card(tiles, label, f"{value:,.2f} {cur}", ui.C["accent"]).grid(row=0, column=i, padx=6, sticky="nsew")
            tiles.columnconfigure(i, weight=1, uniform="t")
        self._last_statement = (title, st, cur)
        box = ui.card(self.stmt_holder, pad=12)
        box.pack(fill="both", expand=True)
        head = tk.Frame(box, bg=ui.C["card"])
        head.pack(fill="x")
        ui.section_label(head, title).pack(side="left", anchor="w")
        ui.Button(head, "Export to Excel (CSV)", self.export_statement, "secondary", bg=ui.C["card"]).pack(side="right")
        table = ui.Table(box, [("date", "Date", 100, "w"), ("ref", "Reference", 160, "w"), ("memo", "Description", 300, "w"),
                               ("dr", "Debit", 120, "e"), ("cr", "Credit", 120, "e"), ("bal", "Balance", 130, "e")], height=12)
        table.pack(fill="both", expand=True, pady=(8, 0))
        table.set_rows([(i, (r["entry_date"], r["ref_no"] or "", r["memo"] or "",
                             f"{r['debit']:,.2f}" if r["debit"] else "", f"{r['credit']:,.2f}" if r["credit"] else "",
                             f"{r['balance']:,.2f}"), None) for i, r in enumerate(st["rows"])])
        if not st["rows"]:
            tk.Label(box, text="No movements in this period.", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=6)

    def export_statement(self):
        """Save the statement on screen as a CSV file (opens in Excel), with the balances at the top."""
        if not getattr(self, "_last_statement", None):
            ui.error("Open a statement first.")
            return
        title, st, cur = self._last_statement
        safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in title.split(" — ")[0]).strip() or "statement"
        start, end = self._period()
        initial = f"{safe}_{(start if start != ALL_FROM else 'start')}_to_{(end if end != ALL_TO else 'today')}.csv"
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=initial,
                                            filetypes=[("CSV file (opens in Excel)", "*.csv")])
        if not path:
            return
        rows = [["Opening balance", "", "", "", "", f"{st['opening']:.2f}"]]
        for r in st["rows"]:
            rows.append([r["entry_date"], r["ref_no"] or "", r["memo"] or "",
                         f"{r['debit']:.2f}" if r["debit"] else "", f"{r['credit']:.2f}" if r["credit"] else "",
                         f"{r['balance']:.2f}"])
        rows.append(["Closing balance", "", "", "", "", f"{st['closing']:.2f}"])
        write_csv(path, ["Date", "Reference", "Description", "Debit", "Credit", f"Balance ({cur})"], rows)
        ui.info("Statement exported.")

    # ------------------------------------------------------------ quick entries
    def _view_quick(self, parent):
        db = self.app.db
        today = datetime.now().strftime("%Y-%m-%d")
        grid = tk.Frame(parent, bg=ui.C["bg"])
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1, uniform="q")
        grid.columnconfigure(1, weight=1, uniform="q")
        expense_codes = [a["code"] for a in db.accounts() if a["type"] == "expense" and a["code"] != COGS]
        money_codes = {"Cash in hand": CASH, "Bank & mobile wallets": BANK}
        forms = [
            ("Record an expense", "Pay an expense", expense_codes, "Expense account", "Paid from", money_codes, "expense"),
            ("Owner introduces capital", "Money the owner puts into the business", None, None, "Received into", money_codes, "capital"),
            ("Owner takes drawings", "Money the owner takes out", None, None, "Paid from", money_codes, "drawings"),
            ("Other income", "Income that is not a sale (e.g. commission)", None, None, "Received into", money_codes, "income"),
            ("Transfer cash to bank", "Move money from cash in hand to the bank", None, None, None, None, "transfer"),
        ]
        for i, spec in enumerate(forms):
            box = ui.card(grid, pad=14)
            box.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            self._quick_form(box, today, *spec)
        box = ui.card(grid, pad=14)
        box.grid(row=len(forms) // 2, column=len(forms) % 2, sticky="nsew", padx=6, pady=6)
        tk.Label(box, text="Every quick entry is balanced automatically: one debit and one credit of the same amount. "
                           "Entries can be reviewed in the Journal tab.", font=ui.font(9), bg=ui.C["card"],
                 fg=ui.C["muted"], wraplength=420, justify="left").pack(anchor="w")

    def _quick_form(self, box, today, title, hint, codes, acct_label, from_label, money_map, kind):
        ui.section_label(box, title).pack(anchor="w")
        tk.Label(box, text=hint, font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(0, 8))
        date_wrap, date_e = ui.field(box, "Date (YYYY-MM-DD)", width=16, value=today, bg=ui.C["card"])
        date_wrap.pack(fill="x", pady=3)
        amt_wrap, amt_e = ui.field(box, "Amount", width=16, bg=ui.C["card"])
        amt_wrap.pack(fill="x", pady=3)
        memo_wrap, memo_e = ui.field(box, "Description", width=40, bg=ui.C["card"])
        memo_wrap.pack(fill="x", pady=3)
        picks = {}
        if acct_label:
            if codes is None:
                codes = [a["code"] for a in self.app.db.accounts() if a["type"] == "income"]
            wrap, cb, mapping = self._account_picker(box, codes=codes, label=acct_label, width=44)
            wrap.pack(fill="x", pady=3)
            picks["account"] = mapping
            picks["account_cb"] = cb
        if from_label:
            labels = list(money_map)
            wrap = tk.Frame(box, bg=ui.C["card"])
            wrap.pack(fill="x", pady=3)
            tk.Label(wrap, text=from_label, font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(fill="x")
            cb = ttk.Combobox(wrap, values=labels, state="readonly", font=ui.font(10))
            cb.set(labels[0])
            cb.pack(fill="x", ipady=4)
            picks["money_cb"] = cb
            picks["money"] = money_map

        def post():
            try:
                amount = to_float(amt_e.get(), 0)
            except ValueError:
                ui.error("Amount must be a number.")
                return
            if amount <= 0:
                ui.error("Enter an amount above 0.")
                return
            day = date_e.get().strip()
            try:
                datetime.strptime(day, "%Y-%m-%d")
            except ValueError:
                ui.error("Date must look like 2026-11-01.")
                return
            memo = memo_e.get().strip() or title
            try:
                if kind == "expense":
                    dr = picks["account"][picks["account_cb"].get()]
                    cr = picks["money"][picks["money_cb"].get()]
                elif kind == "capital":
                    dr, cr = picks["money"][picks["money_cb"].get()], CAPITAL
                elif kind == "drawings":
                    dr, cr = DRAWINGS, picks["money"][picks["money_cb"].get()]
                elif kind == "income":
                    dr, cr = picks["money"][picks["money_cb"].get()], picks["account"][picks["account_cb"].get()]
                else:
                    dr, cr = BANK, CASH
                self.app.db.post_simple(day, memo, dr, cr, amount)
            except (ValueError, KeyError) as ex:
                ui.error(f"Could not post the entry: {ex}")
                return
            self.app.notify(f"Posted {amount:,.2f}: {memo}")
            for e in (amt_e, memo_e):
                ui.set_entry(e, "")

        ui.Button(box, "Post entry", post, "primary", bg=ui.C["card"]).pack(anchor="w", pady=(10, 0))

    # ------------------------------------------------------------ shortcuts
    def on_search(self):
        self.from_e.focus_set()
