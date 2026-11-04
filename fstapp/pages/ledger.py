"""Ledger: accounts and balances, journal, account and party statements, quick entries."""
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from .. import ui_kit as ui
from ..csv_io import to_float
from ..ledger import CAPITAL, BANK, CASH, DRAWINGS, OTHER_INCOME, COGS

VIEWS = [("accounts", "Accounts & balances"), ("journal", "Journal"), ("account", "Account statement"),
         ("party", "Customer / supplier statement"), ("quick", "Quick entry")]
ACCOUNT_TYPES = ["asset", "liability", "equity", "income", "expense"]


class LedgerPage:
    def __init__(self, app):
        self.app = app
        self.view = "accounts"
        now = datetime.now()
        self.date_from = now.replace(day=1).strftime("%Y-%m-%d")
        self.date_to = now.strftime("%Y-%m-%d")
        self.account_ids = {}

    # ------------------------------------------------------------ frame
    def build(self, parent):
        ui.page_header(parent, "Ledger", "Double-entry books. Sales, purchases and payments post automatically."
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
        self.from_wrap, self.from_e = ui.field(bar, "From", width=13, value=self.date_from, bg=ui.C["card"])
        self.from_wrap.pack(side="left", padx=(0, 8))
        self.to_wrap, self.to_e = ui.field(bar, "To", width=13, value=self.date_to, bg=ui.C["card"])
        self.to_wrap.pack(side="left", padx=(0, 8))
        ui.Button(bar, "Apply period", self._apply_period, "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
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
        try:
            start = datetime.strptime(self.from_e.get().strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
            end = datetime.strptime(self.to_e.get().strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            ui.error("Dates must look like 2026-11-01.")
            return
        self.date_from, self.date_to = start, end
        self.switch(self.view)

    def _period(self):
        return self.date_from, self.date_to

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
        self.party_kind.set("Customer")
        self.party_kind.pack(ipady=4)
        pick_wrap = tk.Frame(top, bg=ui.C["card"])
        pick_wrap.pack(side="left", padx=(0, 10))
        tk.Label(pick_wrap, text="Name (type to search)", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(fill="x")
        self.party_picker = ui.Picker(pick_wrap, self._party_options, width=40)
        self.party_picker.pack(fill="x", ipady=4)
        self.party_value = None
        self.party_picker.bind("<<ComboboxSelected>>", lambda e: self._pick_party(), add="+")
        ui.Button(top, "Show statement", lambda: self._render_party(parent), "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        self.stmt_holder = tk.Frame(parent, bg=ui.C["bg"])
        self.stmt_holder.pack(fill="both", expand=True, pady=(10, 0))

    def _party_options(self, term):
        table = "customers" if self.party_kind.get() == "Customer" else "suppliers"
        return self.app.db.contact_options(table, term)

    def _pick_party(self):
        self.party_value = self.party_picker.selected()

    def _render_party(self, parent):
        if not self.party_value:
            ui.error("Pick a saved customer or supplier from the list.")
            return
        kind = "customer" if self.party_kind.get() == "Customer" else "supplier"
        start, end = self._period()
        st = self.app.db.party_statement(kind, self.party_value["id"], start, end)
        self._show_statement(st, title=f"{self.party_value['name']} — {kind} statement")

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
        box = ui.card(self.stmt_holder, pad=12)
        box.pack(fill="both", expand=True)
        ui.section_label(box, title).pack(anchor="w")
        table = ui.Table(box, [("date", "Date", 100, "w"), ("ref", "Reference", 160, "w"), ("memo", "Description", 300, "w"),
                               ("dr", "Debit", 120, "e"), ("cr", "Credit", 120, "e"), ("bal", "Balance", 130, "e")], height=12)
        table.pack(fill="both", expand=True, pady=(8, 0))
        table.set_rows([(i, (r["entry_date"], r["ref_no"] or "", r["memo"] or "",
                             f"{r['debit']:,.2f}" if r["debit"] else "", f"{r['credit']:,.2f}" if r["credit"] else "",
                             f"{r['balance']:,.2f}"), None) for i, r in enumerate(st["rows"])])
        if not st["rows"]:
            tk.Label(box, text="No movements in this period.", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=6)

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
