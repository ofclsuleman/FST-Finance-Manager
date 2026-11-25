"""Dashboard: key figures, 7-day sales chart, low-stock alerts, recent invoices."""
import tkinter as tk

from .. import ui_kit as ui


class HomePage:
    def __init__(self, app):
        self.app = app

    def build(self, parent):
        app, db, cur = self.app, self.app.db, self.app.user["currency"]
        s = db.dashboard()
        greeting = ui.page_header(parent, f"Hello, {app.user['first_name']}",
                                  "Here is how your business is doing today.")
        greeting.pack(fill="x", pady=(0, 14))

        grid = tk.Frame(parent, bg=ui.C["bg"])
        grid.pack(fill="x")
        figures = [
            ("Today's sales", f"{s['today_sales']:,.2f} {cur}", ui.C["success"]),
            ("Today's purchases", f"{s['today_purchases']:,.2f} {cur}", ui.C["accent"]),
            ("To collect (customers)", f"{s['receivable']:,.2f} {cur}", ui.C["warn"]),
            ("To pay (suppliers)", f"{s['payable']:,.2f} {cur}", ui.C["danger"]),
            ("Stock value", f"{s['stock_value']:,.2f} {cur}", ui.C["accent"]),
            ("Low-stock items", str(s["low_count"]), ui.C["danger"]),
            ("Customers", str(s["customers"]), ui.C["success"]),
            ("Products", str(s["products"]), ui.C["muted"]),
        ]
        for i, (label, value, color) in enumerate(figures):
            ui.stat_card(grid, label, value, color).grid(
                row=i // 4, column=i % 4, padx=6, pady=6, sticky="nsew")
            grid.columnconfigure(i % 4, weight=1, uniform="stat")

        actions = tk.Frame(parent, bg=ui.C["bg"])
        actions.pack(fill="x", pady=(10, 6))
        ui.Button(actions, "+ New sale", lambda: app.go("Sales"), "primary", bg=ui.C["bg"]).pack(side="left", padx=(0, 8))
        ui.Button(actions, "+ New purchase", lambda: app.go("Purchase"), "secondary", bg=ui.C["bg"]).pack(side="left", padx=4)
        ui.Button(actions, "+ Add customer", lambda: app.go("Customer"), "secondary", bg=ui.C["bg"]).pack(side="left", padx=4)
        ui.Button(actions, "Create quotation", lambda: app.go("Quotation"), "secondary", bg=ui.C["bg"]).pack(side="left", padx=4)

        middle = tk.Frame(parent, bg=ui.C["bg"])
        middle.pack(fill="both", expand=True, pady=(8, 0))
        middle.columnconfigure(0, weight=3, uniform="mid")
        middle.columnconfigure(1, weight=2, uniform="mid")

        chart_box = ui.card(middle)
        chart_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ui.section_label(chart_box, "Sales — last 7 days").pack(anchor="w")
        self._draw_chart(chart_box, db.sales_by_day(7), cur)

        low_box = ui.card(middle)
        low_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ui.section_label(low_box, "Low stock alerts").pack(anchor="w")
        low = db.products(low_only=True)[:8]
        if low:
            table = ui.Table(low_box, [("name", "Product", 180, "w"), ("stock", "Stock", 70, "e"),
                                       ("reorder_level", "Reorder at", 90, "e")], height=7)
            table.pack(fill="both", expand=True, pady=(8, 0))
            table.set_rows([(p["id"], (p["name"], f"{p['stock']:g}", f"{p['reorder_level']:g}"),
                             "bad" if p["stock"] <= 0 else "warn") for p in low])
        else:
            tk.Label(low_box, text="All products are above their reorder level.",
                     font=ui.font(10), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=14)

        recent_box = ui.card(parent)
        recent_box.pack(fill="both", expand=True, pady=(12, 0))
        ui.section_label(recent_box, "Recent sales").pack(anchor="w")
        rows = db.invoices("sale")[:8]
        table = ui.Table(recent_box, [("no", "Invoice", 170, "w"), ("party", "Customer", 260, "w"),
                                      ("total", "Total", 130, "e"), ("status", "Status", 110, "w"),
                                      ("date", "Date", 160, "w")], height=6)
        table.pack(fill="both", expand=True, pady=(8, 0))
        table.set_rows([(r["id"], (r["invoice_no"], r["party"] or "Walk-in customer",
                                   f"{r['total']:,.2f}", r["status"], r["created_at"][:16].replace("T", " ")),
                         {"Paid": "good", "Partial": "warn", "Unpaid": "bad"}[r["status"]])
                        for r in rows])

    def _draw_chart(self, box, data, cur):
        canvas = tk.Canvas(box, height=230, bg=ui.C["card"], highlightthickness=0)
        canvas.pack(fill="both", expand=True, pady=(10, 0))

        def draw(event=None):
            canvas.delete("all")
            w = event.width if event else canvas.winfo_width()
            h = 230
            if w < 50:
                return
            pad_b, pad_t = 30, 24
            top = max((v for _, v in data), default=0) or 1
            slot = (w - 20) / len(data)
            bar_w = min(42, slot * 0.55)
            for i, (day, value) in enumerate(data):
                x = 10 + i * slot + (slot - bar_w) / 2
                bar_h = (h - pad_b - pad_t) * (value / top)
                y = h - pad_b - bar_h
                canvas.create_rectangle(x, y, x + bar_w, h - pad_b, fill=ui.C["chart"], outline="")
                canvas.create_text(x + bar_w / 2, y - 8, text=f"{value:,.0f}" if value else "0",
                                   fill=ui.C["muted"], font=ui.font(8))
                canvas.create_text(x + bar_w / 2, h - 12, text=day, fill=ui.C["muted"], font=ui.font(9))
            canvas.create_line(10, h - pad_b, w - 10, h - pad_b, fill=ui.C["border"])

        canvas.bind("<Configure>", draw)
