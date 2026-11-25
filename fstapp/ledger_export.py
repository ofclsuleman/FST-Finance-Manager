"""CSV exports of customer and supplier ledgers.

Every movement is written with its reference, description, debit, credit and running
balance, plus an opening and closing balance for each party. Files open in Excel.
"""
import csv
import re

HEADERS = ["Party", "Phone", "Date", "Reference", "Description", "Debit", "Credit", "Balance"]
ALL_FROM = "0000-00-00"


def safe_name(text):
    """A file-name friendly version of a party name."""
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "party"


def _amount(value):
    return f"{value:.2f}" if value else ""


def _date(value):
    return "" if not value or value == ALL_FROM else value


def _party_rows(name, phone, st, date_from, date_to):
    phone = phone or ""
    rows = [[name, phone, _date(date_from), "", "Opening balance", "", "", f"{st['opening']:.2f}"]]
    for r in st["rows"]:
        rows.append([name, phone, r["entry_date"], r["ref_no"] or "", r["memo"] or "",
                     _amount(r["debit"]), _amount(r["credit"]), f"{r['balance']:.2f}"])
    rows.append([name, phone, _date(date_to), "", "Closing balance", "", "", f"{st['closing']:.2f}"])
    return rows


def write_statement_csv(path, business, kind, party, st, date_from, date_to, period_text, currency):
    """One customer or supplier statement, with a header block describing it."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Business", business])
        w.writerow(["Statement", f"{kind.title()} ledger"])
        w.writerow(["Name", party["name"]])
        w.writerow(["Phone", party["phone"] or ""])
        w.writerow(["Period", period_text])
        w.writerow(["Currency", currency])
        w.writerow([])
        w.writerow(HEADERS)
        w.writerows(_party_rows(party["name"], party["phone"], st, date_from, date_to))


def write_all_ledgers_csv(path, business, kind, blocks, date_from, date_to, period_text, currency):
    """Every customer or supplier in one file. Each row names its party, so the file can be filtered."""
    total_closing = sum(st["closing"] for _, st in blocks)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Business", business])
        w.writerow(["Statement", f"All {kind}s ledger"])
        w.writerow(["Period", period_text])
        w.writerow(["Currency", currency])
        w.writerow(["Total closing balance", f"{total_closing:.2f}"])
        w.writerow([])
        w.writerow(HEADERS)
        for party, st in blocks:
            w.writerows(_party_rows(party["name"], party["phone"], st, date_from, date_to))
