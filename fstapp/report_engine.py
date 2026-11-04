"""Builds every financial report in one consistent structure.

Each report is a dict:
    title, subtitle, summary [(label, text)], headers [str],
    aligns ["l"|"r"], rows [(cells, style)], note
where style is None (normal), "section" (bold heading row) or "total" (bold, ruled).
The page renders all reports the same way, so layouts stay uniform.
"""
from datetime import datetime

REPORTS = [
    ("pl", "Profit & loss", "range"),
    ("bs", "Balance sheet", "asof"),
    ("tb", "Trial balance", "range"),
    ("sales", "Sales register", "range"),
    ("purch", "Purchase register", "range"),
    ("ar", "Receivables aging", "asof"),
    ("ap", "Payables aging", "asof"),
    ("stock", "Stock valuation", "asof"),
    ("tax", "Tax summary", "range"),
    ("exp", "Expense breakdown", "range"),
]

ALL_TIME_FROM = "0000-00-00"
FAR_FUTURE = "9999-12-31"


def money(value):
    value = value or 0
    return f"({abs(value):,.2f})" if value < -0.005 else f"{value:,.2f}"


def _report(title, subtitle, headers, aligns, rows, summary=(), note=""):
    return {"title": title, "subtitle": subtitle, "headers": headers, "aligns": aligns,
            "rows": rows, "summary": list(summary), "note": note}


def _days_between(day, as_of):
    try:
        return (datetime.strptime(as_of, "%Y-%m-%d") - datetime.strptime(day[:10], "%Y-%m-%d")).days
    except ValueError:
        return 0


def _bucket(days):
    if days <= 30:
        return 0
    if days <= 60:
        return 1
    if days <= 90:
        return 2
    return 3


def build(db, key, date_from, date_to, business):
    """Return the report dict for key, covering date_from..date_to (or as of date_to)."""
    if key == "pl":
        return _profit_loss(db, date_from, date_to, business)
    if key == "bs":
        return _balance_sheet(db, date_to, business)
    if key == "tb":
        return _trial_balance(db, date_from, date_to, business)
    if key in ("sales", "purch"):
        return _register(db, key, date_from, date_to, business)
    if key in ("ar", "ap"):
        return _aging(db, key, date_to, business)
    if key == "stock":
        return _stock(db, date_to, business)
    if key == "tax":
        return _tax(db, date_from, date_to, business)
    if key == "exp":
        return _expenses(db, date_from, date_to, business)
    raise ValueError(f"Unknown report {key}")


def _period(date_from, date_to):
    return f"For the period {date_from} to {date_to}"


def _profit_loss(db, f, t, business):
    pl = db.profit_and_loss(f, t)
    rows = [(("Income", ""), "section")]
    rows += [((name, money(v)), None) for name, v in pl["income"]] or [(("No income recorded", ""), None)]
    rows += [((("Total revenue", money(pl["revenue"]))), "total")]
    rows += [(("Less: cost of goods sold", money(-pl["cogs"])), None)]
    rows += [(("Gross profit", money(pl["gross"])), "total")]
    rows += [(("Operating expenses", ""), "section")]
    rows += [((name, money(v)), None) for name, v in pl["expenses"]] or [(("No expenses recorded", ""), None)]
    rows += [(("Total operating expenses", money(pl["expense_total"])), "total")]
    rows += [(("Net profit / (loss)", money(pl["net"])), "total")]
    return _report(f"{business} — Profit & loss", _period(f, t), ["Account", "Amount"], ["l", "r"], rows,
                   summary=[("Revenue", money(pl["revenue"])), ("Gross profit", money(pl["gross"])),
                            ("Net profit", money(pl["net"]))],
                   note="Revenue is recognised on invoice date. Cost of goods uses product cost price at the time of sale.")


def _balance_sheet(db, as_of, business):
    bs = db.balance_sheet(as_of)
    rows = [(("Assets", ""), "section")]
    rows += [((n, money(v)), None) for n, v in bs["assets"]]
    rows += [(("Total assets", money(bs["total_assets"])), "total")]
    rows += [(("Liabilities", ""), "section")]
    rows += [((n, money(v)), None) for n, v in bs["liabilities"]]
    rows += [(("Total liabilities", money(bs["total_liabilities"])), "total")]
    rows += [(("Equity", ""), "section")]
    rows += [((n, money(v)), None) for n, v in bs["equity"]]
    rows += [(("Retained profit for the period", money(bs["profit"])), None)]
    rows += [(("Total equity", money(bs["total_equity"])), "total")]
    rows += [(("Total liabilities and equity", money(bs["total_liabilities"] + bs["total_equity"])), "total")]
    return _report(f"{business} — Balance sheet", f"As at {as_of}", ["Item", "Amount"], ["l", "r"], rows,
                   summary=[("Total assets", money(bs["total_assets"])),
                            ("Total liabilities", money(bs["total_liabilities"])),
                            ("Total equity", money(bs["total_equity"]))],
                   note=("Balanced: assets equal liabilities plus equity." if bs["balanced"]
                         else "WARNING: the books do not balance. Please check manual entries."))


def _trial_balance(db, f, t, business):
    rows, dr_total, cr_total = [], 0.0, 0.0
    for r in db.trial_balance(f, t):
        if not (r["dr"] or r["cr"]):
            continue
        net = r["dr"] - r["cr"]
        dr_total += r["dr"]
        cr_total += r["cr"]
        rows.append(((r["code"], r["name"], money(net) if net >= 0 else "", money(-net) if net < 0 else ""), None))
    rows.append((("", "Total", money(dr_total), money(cr_total)), "total"))
    ok = abs(dr_total - cr_total) < 0.01
    return _report(f"{business} — Trial balance", _period(f, t),
                   ["Code", "Account", "Debit", "Credit"], ["l", "l", "r", "r"], rows,
                   summary=[("Total debits", money(dr_total)), ("Total credits", money(cr_total))],
                   note="Totals agree." if ok else "WARNING: debits and credits differ.")


def _register(db, kind, f, t, business):
    table = "sales" if kind == "sale" or kind == "sales" else "purchases"
    party = "customer_name" if table == "sales" else "supplier_name"
    raw = db.query(f"""SELECT invoice_no, date(created_at) d, {party} AS party, subtotal, discount, tax,
                       total, paid FROM {table} WHERE date(created_at) BETWEEN ? AND ? ORDER BY created_at""",
                   (f, t))
    rows = []
    tot = {"subtotal": 0, "discount": 0, "tax": 0, "total": 0, "paid": 0, "due": 0}
    for r in raw:
        due = r["total"] - r["paid"]
        for k in tot:
            tot[k] += due if k == "due" else r[k]
        rows.append(((r["invoice_no"], r["d"], r["party"] or "Walk-in", money(r["subtotal"]), money(r["discount"]),
                      money(r["tax"]), money(r["total"]), money(r["paid"]), money(due)), None))
    rows.append((("", "", "Total", money(tot["subtotal"]), money(tot["discount"]), money(tot["tax"]),
                  money(tot["total"]), money(tot["paid"]), money(tot["due"])), "total"))
    label = "Sales register" if table == "sales" else "Purchase register"
    who = "Customer" if table == "sales" else "Supplier"
    return _report(f"{business} — {label}", _period(f, t),
                   ["Invoice", "Date", who, "Subtotal", "Discount", "Tax", "Total", "Paid", "Due"],
                   ["l", "l", "l", "r", "r", "r", "r", "r", "r"], rows,
                   summary=[("Invoices", str(len(raw))), ("Total value", money(tot["total"])),
                            ("Paid", money(tot["paid"])), ("Outstanding", money(tot["due"]))])


def _aging(db, kind, as_of, business):
    table, party_col = ("sales", "customer_name") if kind == "ar" else ("purchases", "supplier_name")
    raw = db.query(f"""SELECT {party_col} AS party, created_at, total - paid AS due FROM {table}
                       WHERE total - paid > 0.005 AND date(created_at) <= ?""", (as_of,))
    buckets = {}
    for r in raw:
        name = r["party"] or "Walk-in"
        b = buckets.setdefault(name, [0.0, 0.0, 0.0, 0.0])
        b[_bucket(_days_between(r["created_at"], as_of))] += r["due"]
    rows, col_tot = [], [0.0, 0.0, 0.0, 0.0]
    for name in sorted(buckets):
        vals = buckets[name]
        for i, v in enumerate(vals):
            col_tot[i] += v
        rows.append(((name, *[money(v) for v in vals], money(sum(vals))), None))
    rows.append((("Total", *[money(v) for v in col_tot], money(sum(col_tot))), "total"))
    label = "Receivables aging (customers)" if kind == "ar" else "Payables aging (suppliers)"
    return _report(f"{business} — {label}", f"As at {as_of}, by invoice age in days",
                   ["Party", "0–30", "31–60", "61–90", "Over 90", "Total"],
                   ["l", "r", "r", "r", "r", "r"], rows,
                   summary=[("Total outstanding", money(sum(col_tot))),
                            ("Over 90 days", money(col_tot[3]))])


def _stock(db, as_of, business):
    rows, cost_tot, sale_tot, qty_tot = [], 0.0, 0.0, 0.0
    for p in db.products():
        qty = max(p["stock"], 0)
        cost_value, sale_value = qty * p["cost_price"], qty * p["sale_price"]
        cost_tot += cost_value
        sale_tot += sale_value
        qty_tot += qty
        status = "" if p["stock"] > p["reorder_level"] else (" (out)" if p["stock"] <= 0 else " (low)")
        rows.append(((p["name"] + status, p["sku"] or "", p["category"] or "", f"{p['stock']:g}",
                      money(p["cost_price"]), money(cost_value), money(sale_value)), None))
    rows.append((("Total", "", "", f"{qty_tot:g}", "", money(cost_tot), money(sale_tot)), "total"))
    return _report(f"{business} — Stock valuation", f"As at {as_of}",
                   ["Product", "SKU", "Category", "Qty", "Unit cost", "Value at cost", "Value at sale price"],
                   ["l", "l", "l", "r", "r", "r", "r"], rows,
                   summary=[("Value at cost", money(cost_tot)), ("Value at sale price", money(sale_tot))],
                   note="Negative stock (sold before receiving) is valued at zero.")


def _tax(db, f, t, business):
    sales = {r["m"]: r for r in db.query(
        """SELECT substr(created_at,1,7) m, SUM(subtotal-discount) net, SUM(tax) tax FROM sales
           WHERE date(created_at) BETWEEN ? AND ? GROUP BY m""", (f, t))}
    buys = {r["m"]: r for r in db.query(
        """SELECT substr(created_at,1,7) m, SUM(subtotal-discount) net, SUM(tax) tax FROM purchases
           WHERE date(created_at) BETWEEN ? AND ? GROUP BY m""", (f, t))}
    rows, tot = [], [0.0, 0.0, 0.0, 0.0]
    for m in sorted(set(sales) | set(buys)):
        s, b = sales.get(m, {}), buys.get(m, {})
        vals = [s.get("net", 0) or 0, s.get("tax", 0) or 0, b.get("net", 0) or 0, b.get("tax", 0) or 0]
        for i, v in enumerate(vals):
            tot[i] += v
        rows.append(((m, *[money(v) for v in vals], money(vals[1] - vals[3])), None))
    rows.append((("Total", *[money(v) for v in tot], money(tot[1] - tot[3])), "total"))
    return _report(f"{business} — Tax summary", _period(f, t),
                   ["Month", "Taxable sales", "Tax collected", "Taxable purchases", "Tax paid", "Net tax"],
                   ["l", "r", "r", "r", "r", "r"], rows,
                   summary=[("Tax collected", money(tot[1])), ("Tax paid", money(tot[3])),
                            ("Net tax payable", money(tot[1] - tot[3]))],
                   note="Net tax is the amount to pay to the tax authority for the period.")


def _expenses(db, f, t, business):
    pl = db.profit_and_loss(f, t)
    total = pl["expense_total"] or 1
    rows = [((name, money(v), f"{v / total * 100:.1f}%"), None) for name, v in pl["expenses"]]
    rows.append((("Total", money(pl["expense_total"]), "100.0%" if pl["expense_total"] else "0.0%"), "total"))
    return _report(f"{business} — Expense breakdown", _period(f, t),
                   ["Expense account", "Amount", "Share"], ["l", "r", "r"], rows,
                   summary=[("Total expenses", money(pl["expense_total"]))],
                   note="Record expenses with Ledger → Quick entry.")
