"""Reports: revenue, collections, outstanding balances, profit and top products."""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog

from .. import ui_kit as ui
from ..csv_io import write_csv


class ReportsPage:
    def __init__(self, app):
        self.app = app
        today = datetime.now()
        self.range = {"from": today.replace(day=1).strftime("%Y-%m-%d"), "to": today.strftime("%Y-%m-%d")}
        self.report = None

    def build(self, parent):
        cur = self.app.user["currency"]
        ui.page_header(parent, "Reports", "Pick a period to see how the business performed."
                       ).pack(fill="x", pady=(0, 10))

        bar = ui.card(parent, pad=14)
        bar.pack(fill="x")
        self.from_wrap, self.from_e = ui.field(bar, "From (YYYY-MM-DD)", width=14, value=self.range["from"], bg=ui.C["card"])
        self.from_wrap.pack(side="left", padx=(0, 8))
        self.to_wrap, self.to_e = ui.field(bar, "To (YYYY-MM-DD)", width=14, value=self.range["to"], bg=ui.C["card"])
        self.to_wrap.pack(side="left", padx=(0, 12))
        ui.Button(bar, "Run report", self.run, "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        for label, days in [("This month", None), ("Last 30 days", 30), ("This year", "year")]:
            ui.Button(bar, label, lambda d=days: self.quick(d), "ghost", bg=ui.C["card"]).pack(side="left", padx=4, pady=(14, 0))
        ui.Button(bar, "Export (CSV)", self.export, "secondary", bg=ui.C["card"]).pack(side="right", pady=(14, 0))

        self.cards = tk.Frame(parent, bg=ui.C["bg"])
        self.cards.pack(fill="x", pady=10)
        self.cur = cur

        self.top_box = ui.card(parent, pad=14)
        self.top_box.pack(fill="both", expand=True)
        ui.section_label(self.top_box, "Top-selling products").pack(anchor="w")
        self.top_table = ui.Table(self.top_box, [("name", "Product", 360, "w"), ("qty", "Qty sold", 120, "e"),
                                                 ("rev", "Revenue", 160, "e")], height=8)
        self.top_table.pack(fill="both", expand=True, pady=(8, 0))
        self.run()

    def quick(self, days):
        today = datetime.now()
        if days == "year":
            start = today.replace(month=1, day=1)
        elif days:
            start = today - timedelta(days=days - 1)
        else:
            start = today.replace(day=1)
        ui.set_entry(self.from_e, start.strftime("%Y-%m-%d"))
        ui.set_entry(self.to_e, today.strftime("%Y-%m-%d"))
        self.run()

    def _range(self):
        try:
            start = datetime.strptime(self.from_e.get().strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
            end = datetime.strptime(self.to_e.get().strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            ui.error("Dates must be in the format YYYY-MM-DD, for example 2026-11-01.")
            return None
        if start > end:
            ui.error("The 'From' date must be before the 'To' date.")
            return None
        return start, end

    def run(self):
        dates = self._range()
        if not dates:
            return
        self.range = {"from": dates[0], "to": dates[1]}
        self.report = self.app.db.report(*dates)
        r, cur = self.report, self.cur
        for w in self.cards.winfo_children():
            w.destroy()
        figures = [
            ("Sales", f"{r['sales_total']:,.2f} {cur}", f"{r['sales_count']} invoice(s)", ui.C["success"]),
            ("Collected from customers", f"{r['collected']:,.2f} {cur}", "payments received", ui.C["accent"]),
            ("Outstanding (customers)", f"{r['outstanding']:,.2f} {cur}", "still to collect", ui.C["warn"]),
            ("Estimated gross profit", f"{r['gross_profit']:,.2f} {cur}", "sales minus product cost", ui.C["success"]),
            ("Purchases", f"{r['purchases_total']:,.2f} {cur}", f"{r['purchase_count']} invoice(s)", ui.C["accent"]),
            ("Paid to suppliers", f"{r['paid_to_suppliers']:,.2f} {cur}", "payments made", ui.C["muted"]),
            ("Tax collected", f"{r['tax_collected']:,.2f} {cur}", "on sales in period", ui.C["muted"]),
            ("Net sales", f"{r['sales_total'] - r['tax_collected']:,.2f} {cur}", "before tax", ui.C["muted"]),
        ]
        for i, (label, value, sub, color) in enumerate(figures):
            box = ui.stat_card(self.cards, label, value, color)
            box.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="nsew")
            self.cards.columnconfigure(i % 4, weight=1, uniform="r")
            tk.Label(box, text=sub, font=ui.font(8), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(2, 0))
        self.top_table.set_rows([(i, (t["name"], f"{t['qty']:g}", f"{t['revenue']:,.2f}"), None)
                                 for i, t in enumerate(r["top_products"])])

    def export(self):
        if not self.report:
            self.run()
        r = self.report
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile=f"report_{self.range['from']}_{self.range['to']}.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        rows = [["Period", f"{self.range['from']} to {self.range['to']}"],
                ["Sales total", f"{r['sales_total']:.2f}"], ["Sales count", r["sales_count"]],
                ["Tax collected", f"{r['tax_collected']:.2f}"], ["Collected", f"{r['collected']:.2f}"],
                ["Outstanding", f"{r['outstanding']:.2f}"], ["Purchases total", f"{r['purchases_total']:.2f}"],
                ["Paid to suppliers", f"{r['paid_to_suppliers']:.2f}"],
                ["Estimated gross profit", f"{r['gross_profit']:.2f}"], [],
                ["Product", "Qty sold", "Revenue"]]
        rows += [[t["name"], t["qty"], f"{t['revenue']:.2f}"] for t in r["top_products"]]
        write_csv(path, ["Item", "Value"], rows)
        ui.info("Report exported.")

    def on_search(self):
        self.from_e.focus_set()
