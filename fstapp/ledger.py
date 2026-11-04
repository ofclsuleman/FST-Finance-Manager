"""Double-entry ledger: chart of accounts, automatic posting, statements.

Every journal entry must balance (total debits == total credits). Sales,
purchases and payments post automatically; expenses, capital and transfers
are posted through quick entries.
"""
from datetime import datetime

DEFAULT_ACCOUNTS = [
    ("1000", "Cash in hand", "asset"),
    ("1010", "Bank & mobile wallets", "asset"),
    ("1100", "Accounts receivable (customers)", "asset"),
    ("1200", "Inventory", "asset"),
    ("2000", "Accounts payable (suppliers)", "liability"),
    ("2100", "Tax payable", "liability"),
    ("3000", "Owner's capital", "equity"),
    ("3100", "Owner's drawings", "equity"),
    ("4000", "Sales revenue", "income"),
    ("4100", "Other income", "income"),
    ("5000", "Cost of goods sold", "expense"),
    ("6000", "General expenses", "expense"),
    ("6100", "Rent", "expense"),
    ("6200", "Salaries & wages", "expense"),
    ("6300", "Utilities", "expense"),
    ("6400", "Transport", "expense"),
    ("6500", "Marketing", "expense"),
]

CASH, BANK, AR, INVENTORY, AP, TAX_PAYABLE = "1000", "1010", "1100", "1200", "2000", "2100"
CAPITAL, DRAWINGS, SALES, OTHER_INCOME, COGS, GENERAL_EXP = "3000", "3100", "4000", "4100", "5000", "6000"
PAYMENT_ACCOUNT = {"Cash": CASH, "Bank Transfer": BANK, "Card": BANK, "Mobile Wallet": BANK, "Cheque": BANK}
ACCOUNT_PREFIX = {"asset": "1", "liability": "2", "equity": "3", "income": "4", "expense": "6"}
DEBIT_NORMAL = ("asset", "expense")


def today():
    return datetime.now().strftime("%Y-%m-%d")


def pay_account(method):
    return PAYMENT_ACCOUNT.get(method or "Cash", CASH)


class LedgerMixin:
    """Mixed into Database. Relies on self.conn, self.query, self.one, self.scalar."""

    # ------------------------------------------------------------ setup
    def _setup_ledger(self):
        for code, name, typ in DEFAULT_ACCOUNTS:
            self.conn.execute("INSERT OR IGNORE INTO accounts (code, name, type, system) VALUES (?,?,?,1)",
                              (code, name, typ))
        self.conn.commit()

    def acct(self, code):
        row = self.conn.execute("SELECT id FROM accounts WHERE code=?", (code,)).fetchone()
        if not row:
            raise ValueError(f"Unknown account {code}")
        return row[0]

    def accounts(self, active_only=True):
        where = " WHERE active=1" if active_only else ""
        return self.query(f"SELECT * FROM accounts{where} ORDER BY code")

    def add_account(self, name, typ):
        row = self.one("SELECT MAX(code) AS m FROM accounts WHERE type=?", (typ,))
        base = int(row["m"]) if row and row["m"] else int(ACCOUNT_PREFIX[typ] + "000")
        code = str(base + 10)
        with self.conn:
            self.conn.execute("INSERT INTO accounts (code, name, type) VALUES (?,?,?)", (code, name, typ))
        return code

    # ------------------------------------------------------------ posting core
    def _post(self, entry_date, ref_type, ref_id, ref_no, memo, lines):
        """Insert one balanced journal entry. Must run inside a transaction.

        lines: dicts with code, debit, credit and optional party_type / party_id.
        """
        lines = [l for l in lines if round(l.get("debit", 0) + l.get("credit", 0), 2) > 0]
        dr = round(sum(l.get("debit", 0) for l in lines), 2)
        cr = round(sum(l.get("credit", 0) for l in lines), 2)
        if abs(dr - cr) > 0.005:
            raise ValueError(f"Unbalanced journal entry {ref_no}: debits {dr} != credits {cr}")
        cur = self.conn.execute(
            """INSERT INTO journal_entries (entry_date, ref_type, ref_id, ref_no, memo, created_at)
               VALUES (?,?,?,?,?,?)""",
            (entry_date, ref_type, ref_id, ref_no, memo, datetime.now().isoformat(timespec="seconds")))
        eid = cur.lastrowid
        for l in lines:
            self.conn.execute(
                """INSERT INTO journal_lines (entry_id, account_id, debit, credit, party_type, party_id, memo)
                   VALUES (?,?,?,?,?,?,?)""",
                (eid, self.acct(l["code"]), round(l.get("debit", 0), 2), round(l.get("credit", 0), 2),
                 l.get("party_type"), l.get("party_id"), l.get("memo")))
        return eid

    def _unpost(self, ref_type, ref_id):
        self.conn.execute("DELETE FROM journal_entries WHERE ref_type=? AND ref_id=?", (ref_type, ref_id))

    # ------------------------------------------------------------ automatic postings
    def post_sale(self, sale_id, inv_no, day, total, net, tax, cogs, customer_id):
        lines = [
            {"code": AR, "debit": total, "party_type": "customer" if customer_id else None,
             "party_id": customer_id},
            {"code": SALES, "credit": net},
            {"code": TAX_PAYABLE, "credit": tax},
            {"code": COGS, "debit": cogs},
            {"code": INVENTORY, "credit": cogs},
        ]
        self._post(day, "sale", sale_id, inv_no, f"Sales invoice {inv_no}", lines)

    def post_purchase(self, purchase_id, inv_no, day, total, supplier_id):
        lines = [
            {"code": INVENTORY, "debit": total},
            {"code": AP, "credit": total, "party_type": "supplier" if supplier_id else None,
             "party_id": supplier_id},
        ]
        self._post(day, "purchase", purchase_id, inv_no, f"Purchase invoice {inv_no}", lines)

    def post_payment(self, kind, payment_id, inv_no, day, amount, method, party_id):
        if kind == "sale":
            lines = [{"code": pay_account(method), "debit": amount},
                     {"code": AR, "credit": amount, "party_type": "customer" if party_id else None,
                      "party_id": party_id}]
            memo = f"Receipt against {inv_no}"
        else:
            lines = [{"code": AP, "debit": amount, "party_type": "supplier" if party_id else None,
                      "party_id": party_id},
                     {"code": pay_account(method), "credit": amount}]
            memo = f"Payment against {inv_no}"
        self._post(day, f"{kind}_payment", payment_id, inv_no, memo, lines)

    def post_simple(self, day, memo, debit_code, credit_code, amount, ref_type="manual"):
        """Quick entry: one debit and one credit of the same amount."""
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")
        with self.conn:
            self._post(day, ref_type, None, None, memo,
                       [{"code": debit_code, "debit": amount}, {"code": credit_code, "credit": amount}])

    def delete_manual_entry(self, entry_id):
        with self.conn:
            row = self.one("SELECT ref_type FROM journal_entries WHERE id=?", (entry_id,))
            if not row or row["ref_type"] != "manual":
                raise ValueError("Only manual entries can be deleted here. Delete the invoice instead.")
            self.conn.execute("DELETE FROM journal_entries WHERE id=?", (entry_id,))

    # ------------------------------------------------------------ statements
    def _activity(self, date_from, date_to):
        """Per-account debit and credit totals within a date range."""
        return self.query(
            """SELECT a.id, a.code, a.name, a.type,
               (SELECT IFNULL(SUM(jl.debit),0) FROM journal_lines jl JOIN journal_entries je ON je.id=jl.entry_id
                  WHERE jl.account_id=a.id AND je.entry_date BETWEEN ? AND ?) AS dr,
               (SELECT IFNULL(SUM(jl.credit),0) FROM journal_lines jl JOIN journal_entries je ON je.id=jl.entry_id
                  WHERE jl.account_id=a.id AND je.entry_date BETWEEN ? AND ?) AS cr
               FROM accounts a ORDER BY a.code""",
            (date_from, date_to, date_from, date_to))

    def _statement(self, where_sql, params, sign, date_from, date_to):
        opening = self.scalar(
            f"""SELECT IFNULL(SUM(jl.debit - jl.credit),0) FROM journal_lines jl
                JOIN journal_entries je ON je.id=jl.entry_id
                WHERE {where_sql} AND je.entry_date < ?""", params + (date_from,)) * sign
        rows = self.query(
            f"""SELECT je.entry_date, je.ref_no, je.memo, jl.debit, jl.credit
                FROM journal_lines jl JOIN journal_entries je ON je.id=jl.entry_id
                WHERE {where_sql} AND je.entry_date BETWEEN ? AND ?
                ORDER BY je.entry_date, je.id, jl.id""", params + (date_from, date_to))
        running = opening
        for r in rows:
            running += (r["debit"] - r["credit"]) * sign
            r["balance"] = running
        return {"opening": opening, "rows": rows, "closing": running}

    def account_statement(self, account_id, date_from, date_to):
        acct = self.one("SELECT * FROM accounts WHERE id=?", (account_id,))
        sign = 1 if acct["type"] in DEBIT_NORMAL else -1
        result = self._statement("jl.account_id=?", (account_id,), sign, date_from, date_to)
        result["account"] = acct
        return result

    def party_statement(self, party_type, party_id, date_from, date_to):
        code = AR if party_type == "customer" else AP
        sign = 1 if party_type == "customer" else -1
        acct_id = self.acct(code)
        return self._statement("jl.account_id=? AND jl.party_type=? AND jl.party_id=?",
                               (acct_id, party_type, party_id), sign, date_from, date_to)

    def journal(self, date_from, date_to, limit=300):
        entries = self.query(
            """SELECT * FROM journal_entries WHERE entry_date BETWEEN ? AND ?
               ORDER BY entry_date DESC, id DESC LIMIT ?""", (date_from, date_to, limit))
        for e in entries:
            e["lines"] = self.query(
                """SELECT a.code, a.name, jl.debit, jl.credit, jl.memo FROM journal_lines jl
                   JOIN accounts a ON a.id=jl.account_id WHERE jl.entry_id=? ORDER BY jl.id""", (e["id"],))
            e["total"] = sum(l["debit"] for l in e["lines"])
        return entries

    def trial_balance(self, date_from, date_to):
        rows = self._activity(date_from, date_to)
        for r in rows:
            r["sign"] = 1 if r["type"] in DEBIT_NORMAL else -1
            r["balance"] = (r["dr"] - r["cr"]) * r["sign"]
        return rows

    def profit_and_loss(self, date_from, date_to):
        rows = self._activity(date_from, date_to)
        income = [(r["name"], r["cr"] - r["dr"]) for r in rows if r["type"] == "income" and (r["cr"] or r["dr"])]
        expenses = [(r["code"], r["name"], r["dr"] - r["cr"]) for r in rows
                    if r["type"] == "expense" and (r["cr"] or r["dr"])]
        revenue = sum(v for _, v in income)
        cogs = sum(v for c, _, v in expenses if c == COGS)
        opex = [(n, v) for c, n, v in expenses if c != COGS]
        gross = revenue - cogs
        opex_total = sum(v for _, v in opex)
        return {"income": income, "revenue": revenue, "cogs": cogs, "gross": gross,
                "expenses": opex, "expense_total": opex_total, "net": gross - opex_total}

    def balance_sheet(self, as_of):
        rows = self._activity("0000-00-00", as_of)
        assets = [(r["name"], r["dr"] - r["cr"]) for r in rows if r["type"] == "asset" and (r["dr"] or r["cr"])]
        liabilities = [(r["name"], r["cr"] - r["dr"]) for r in rows if r["type"] == "liability" and (r["dr"] or r["cr"])]
        equity = [(r["name"], r["cr"] - r["dr"]) for r in rows if r["type"] == "equity" and (r["dr"] or r["cr"])]
        profit = sum((r["cr"] - r["dr"]) if r["type"] == "income" else -(r["dr"] - r["cr"])
                     for r in rows if r["type"] in ("income", "expense"))
        total_assets = sum(v for _, v in assets)
        total_liab = sum(v for _, v in liabilities)
        total_equity = sum(v for _, v in equity) + profit
        return {"assets": assets, "total_assets": total_assets, "liabilities": liabilities,
                "total_liabilities": total_liab, "equity": equity, "profit": profit,
                "total_equity": total_equity, "balanced": abs(total_assets - total_liab - total_equity) < 0.01}
