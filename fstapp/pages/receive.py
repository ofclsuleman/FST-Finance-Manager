"""Receive a lump-sum customer payment. Shared by the Customers page and the Ledger."""
import tkinter as tk
from tkinter import ttk

from .. import ui_kit as ui
from ..config import PAYMENT_METHODS
from ..csv_io import to_float
from ..ledger import today


def open_receive_payment(app, party, on_done=None):
    """Dialog: take money from a customer, dated on the day it was received. No items are added.

    party is a customer row (needs "id" and "name"). on_done() runs after a successful save.
    """
    db, cur = app.db, app.user["currency"]
    due = db.customer_due(party["id"])
    if due <= 0.005:
        ui.info(f"{party['name']} has no unpaid invoices.")
        return

    win = tk.Toplevel(app.root)
    win.title("Receive payment")
    win.configure(bg=ui.C["card"])
    win.geometry("480x500")
    win.transient(app.root)
    box = tk.Frame(win, bg=ui.C["card"], padx=22, pady=18)
    box.pack(fill="both", expand=True)
    tk.Label(box, text=f"Receive payment from {party['name']}", font=ui.font(13, True),
             bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
    tk.Label(box, text=f"Still owed: {due:,.2f} {cur}.\nThe amount is applied to the oldest unpaid invoices first. "
                       "No items are added.",
             font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], justify="left").pack(anchor="w", pady=(6, 12))

    amt_wrap, amt_e = ui.field(box, f"Amount received ({cur})", width=20, bg=ui.C["card"])
    amt_wrap.pack(fill="x", pady=4)
    day_wrap, day_e = ui.date_field(box, "Date received (YYYY-MM-DD)", width=20, value=today(), bg=ui.C["card"])
    day_wrap.pack(fill="x", pady=4)
    tk.Label(box, text="Method", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x", pady=(4, 0))
    method_cb = ttk.Combobox(box, values=[m for m in PAYMENT_METHODS if m != "Credit"], state="readonly")
    method_cb.set("Cash")
    method_cb.pack(fill="x", ipady=3)
    note_wrap, note_e = ui.field(box, "Note (optional)", width=20, bg=ui.C["card"])
    note_wrap.pack(fill="x", pady=4)

    def save():
        try:
            amount = to_float(amt_e.get(), 0)
        except ValueError:
            ui.error("Enter a valid amount.", title="Receive payment")
            return
        try:
            applied = db.receive_customer_payment(party["id"], amount, method=method_cb.get(),
                                                  day=day_e.get().strip() or None, note=note_e.get().strip())
        except ValueError as ex:
            ui.error(str(ex), title="Receive payment")
            return
        lines = "\n".join(f"  {no}: {amt:,.2f}" for no, amt in applied)
        ui.info(f"Payment of {sum(a for _, a in applied):,.2f} {cur} recorded.\n\n{lines}\n\n"
                f"Remaining due: {db.customer_due(party['id']):,.2f} {cur}.", title="Receive payment")
        app.notify(f"Payment received from {party['name']}.")
        win.destroy()
        if on_done:
            on_done()

    foot = tk.Frame(win, bg=ui.C["card"], padx=22, pady=14)
    foot.pack(fill="x", side="bottom")
    ui.Button(foot, "Save payment", save, "primary", bg=ui.C["card"]).pack(side="right")
    ui.Button(foot, "Cancel", win.destroy, "secondary", bg=ui.C["card"]).pack(side="right", padx=8)


def open_payment_editor(app, pay, on_done=None):
    """Dialog: change one saved receipt (amount, date, method, note). pay is a payments row."""
    db, cur = app.db, app.user["currency"]
    win = tk.Toplevel(app.root)
    win.title("Edit payment")
    win.configure(bg=ui.C["card"])
    win.geometry("460x440")
    win.transient(app.root)
    box = tk.Frame(win, bg=ui.C["card"], padx=22, pady=18)
    box.pack(fill="both", expand=True)
    tk.Label(box, text="Edit payment", font=ui.font(13, True), bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
    tk.Label(box, text="The ledger entry is updated too.", font=ui.font(9), bg=ui.C["card"],
             fg=ui.C["muted"]).pack(anchor="w", pady=(4, 12))

    amt_wrap, amt_e = ui.field(box, f"Amount ({cur})", width=20, value=f"{pay['amount']:g}", bg=ui.C["card"])
    amt_wrap.pack(fill="x", pady=4)
    day_wrap, day_e = ui.date_field(box, "Date received (YYYY-MM-DD)", width=14,
                                    value=(pay["paid_at"] or "")[:10], bg=ui.C["card"])
    day_wrap.pack(fill="x", pady=4)
    tk.Label(box, text="Method", font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x", pady=(4, 0))
    method_cb = ttk.Combobox(box, values=[m for m in PAYMENT_METHODS if m != "Credit"], state="readonly")
    method_cb.set(pay["method"] or "Cash")
    method_cb.pack(fill="x", ipady=3)
    note_wrap, note_e = ui.field(box, "Note (optional)", width=20, value=pay["note"] or "", bg=ui.C["card"])
    note_wrap.pack(fill="x", pady=4)

    def save():
        try:
            amount = to_float(amt_e.get(), 0)
        except ValueError:
            ui.error("Enter a valid amount.", title="Edit payment")
            return
        try:
            db.update_payment(pay["id"], amount, day_e.get().strip(), method_cb.get(), note_e.get().strip())
        except ValueError as ex:
            ui.error(str(ex), title="Edit payment")
            return
        app.notify("Payment updated.")
        win.destroy()
        if on_done:
            on_done()

    foot = tk.Frame(win, bg=ui.C["card"], padx=22, pady=14)
    foot.pack(fill="x", side="bottom")
    ui.Button(foot, "Save changes", save, "primary", bg=ui.C["card"]).pack(side="right")
    ui.Button(foot, "Cancel", win.destroy, "secondary", bg=ui.C["card"]).pack(side="right", padx=8)
