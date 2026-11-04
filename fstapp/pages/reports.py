"""Financial reports: one document layout for every statement.

Left: the list of reports. Right: a report sheet with header block, summary
tiles, the statement table, notes, and export (CSV or printable text).
"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog

from .. import ui_kit as ui
from ..csv_io import write_csv
from ..report_engine import ALL_TIME_FROM, FAR_FUTURE, REPORTS, build


class ReportsPage:
    def __init__(self, app):
        self.app = app
        today = datetime.now()
        self.key = "pl"
        self.date_from = today.replace(day=1).strftime("%Y-%m-%d")
        self.date_to = today.strftime("%Y-%m-%d")
        self.report = None

    def build(self, parent):
        ui.page_header(parent, "Financial reports",
                       "Statements prepared from the ledger and your invoices. Pick a report, set the period, and export."
                       ).pack(fill="x", pady=(0, 10))
        self._period_bar(parent)

        body = tk.Frame(parent, bg=ui.C["bg"])
        body.pack(fill="both", expand=True, pady=(10, 0))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        nav = ui.card(body, pad=10)
        nav.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        tk.Label(nav, text="STATEMENTS", font=ui.font(8, True), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", padx=8, pady=(4, 6))
        self.nav_buttons = {}
        for key, label, _ in REPORTS:
            btn = tk.Label(nav, text=label, font=ui.font(10), anchor="w", cursor="hand2", padx=12, pady=7, width=22)
            btn.pack(fill="x", pady=1)
            btn.bind("<Button-1>", lambda e, k=key: self.select(k))
            self.nav_buttons[key] = btn
        self._paint_nav()

        self.sheet = ui.card(body, pad=22)
        self.sheet.grid(row=0, column=1, sticky="nsew")
        self.run()

    def _period_bar(self, parent):
        bar = ui.card(parent, pad=12)
        bar.pack(fill="x")
        self.from_wrap, self.from_e = ui.field(bar, "From", width=13, value=self.date_from, bg=ui.C["card"])
        self.from_wrap.pack(side="left", padx=(0, 8))
        self.to_wrap, self.to_e = ui.field(bar, "To / as at", width=13, value=self.date_to, bg=ui.C["card"])
        self.to_wrap.pack(side="left", padx=(0, 10))
        ui.Button(bar, "Apply", self.apply_dates, "primary", bg=ui.C["card"]).pack(side="left", pady=(14, 0))
        for label, mode in [("This month", "month"), ("Last 30 days", 30), ("This year", "year"), ("All time", "all")]:
            ui.Button(bar, label, lambda m=mode: self.quick(m), "ghost", bg=ui.C["card"]).pack(side="left", padx=3, pady=(14, 0))

    # ------------------------------------------------------------ state
    def select(self, key):
        self.key = key
        self._paint_nav()
        self.run()

    def _paint_nav(self):
        for key, btn in self.nav_buttons.items():
            active = key == self.key
            btn.configure(bg=ui.C["accent"] if active else ui.C["card"],
                          fg=ui.C["accent_fg"] if active else ui.C["fg"],
                          font=ui.font(10, active))

    def quick(self, mode):
        today = datetime.now()
        if mode == "month":
            start = today.replace(day=1)
        elif mode == "year":
            start = today.replace(month=1, day=1)
        elif mode == "all":
            ui.set_entry(self.from_e, ALL_TIME_FROM)
            ui.set_entry(self.to_e, today.strftime("%Y-%m-%d"))
            self.apply_dates()
            return
        else:
            start = today - timedelta(days=mode - 1)
        ui.set_entry(self.from_e, start.strftime("%Y-%m-%d"))
        ui.set_entry(self.to_e, today.strftime("%Y-%m-%d"))
        self.apply_dates()

    def apply_dates(self):
        try:
            start = datetime.strptime(self.from_e.get().strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
            end = datetime.strptime(self.to_e.get().strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            ui.error("Dates must look like 2026-11-01 (year-month-day).")
            return
        if start > end:
            ui.error("The 'From' date must be before the 'To' date.")
            return
        self.date_from, self.date_to = start, end
        self.run()

    # ------------------------------------------------------------ render
    def run(self):
        db = self.app.db
        self.report = build(db, self.key, self.date_from, self.date_to, self.app.user["business_name"])
        for w in self.sheet.winfo_children():
            w.destroy()
        r = self.report
        head = tk.Frame(self.sheet, bg=ui.C["card"])
        head.pack(fill="x")
        tk.Label(head, text=self.app.user["business_name"].upper(), font=ui.font(9, True),
                 bg=ui.C["card"], fg=ui.C["accent"]).pack(anchor="w")
        tk.Label(head, text=r["title"].split(" — ")[-1], font=ui.font(20, True), bg=ui.C["card"],
                 fg=ui.C["fg"]).pack(anchor="w", pady=(2, 0))
        tk.Label(head, text=f"{r['subtitle']}   ·   Generated {datetime.now():%d %b %Y, %H:%M}",
                 font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w")
        tk.Frame(self.sheet, bg=ui.C["border"], height=1).pack(fill="x", pady=12)

        if r["summary"]:
            tiles = tk.Frame(self.sheet, bg=ui.C["card"])
            tiles.pack(fill="x", pady=(0, 12))
            for i, (label, value) in enumerate(r["summary"]):
                box = ui.stat_card(tiles, label, value, ui.C["accent"])
                box.grid(row=0, column=i, padx=(0 if i == 0 else 8, 0), sticky="nsew")
                tiles.columnconfigure(i, weight=1, uniform="tiles")

        cols = [(f"c{i}", h, 150 if i else 240, "e" if a == "r" else "w") for i, (h, a) in enumerate(zip(r["headers"], r["aligns"]))]
        table = ui.Table(self.sheet, cols, height=min(max(len(r["rows"]), 6), 18))
        table.pack(fill="both", expand=True)
        table.tree.tag_configure("section", font=ui.font(10, True), foreground=ui.C["accent"])
        table.tree.tag_configure("total", font=ui.font(10, True), background=ui.C["head"])
        width = len(r["headers"])
        table.set_rows([(i, tuple(list(cells) + [""] * (width - len(cells))), style)
                        for i, (cells, style) in enumerate(r["rows"])])

        if r["note"]:
            tk.Label(self.sheet, text=r["note"], font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"],
                     wraplength=900, justify="left").pack(anchor="w", pady=(10, 0))

        foot = tk.Frame(self.sheet, bg=ui.C["card"])
        foot.pack(fill="x", pady=(14, 0))
        ui.Button(foot, "Export to Excel (CSV)", self.export_csv, "primary", bg=ui.C["card"]).pack(side="left")
        ui.Button(foot, "Save as printable text", self.export_text, "secondary", bg=ui.C["card"]).pack(side="left", padx=8)

    # ------------------------------------------------------------ export
    def _default_name(self, ext):
        return f"{self.key}_{self.date_from}_to_{self.date_to}.{ext}"

    def export_csv(self):
        r = self.report
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=self._default_name("csv"),
                                            filetypes=[("CSV file (opens in Excel)", "*.csv")])
        if not path:
            return
        width = len(r["headers"])
        rows = [[cells[i] if i < len(cells) else "" for i in range(width)] for cells, _ in r["rows"]]
        write_csv(path, r["headers"], rows)
        ui.info("Report exported.")

    def export_text(self):
        r = self.report
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=self._default_name("txt"),
                                            filetypes=[("Text file", "*.txt")])
        if not path:
            return
        width = len(r["headers"])
        col_w = [max([len(str(r["headers"][i]))] + [len(str(c[i])) for c, _ in r["rows"] if i < len(c)])
                 for i in range(width)]
        col_w = [min(w, 42) for w in col_w]
        def line(cells):
            out = []
            for i, cell in enumerate(cells):
                text = str(cell)[:col_w[i]]
                right = r["aligns"][i] == "r"
                out.append(text.rjust(col_w[i]) if right else text.ljust(col_w[i]))
            return "  ".join(out).rstrip()
        total_w = sum(col_w) + 2 * (width - 1)
        lines = [self.app.user["business_name"].upper(), r["title"].split(" — ")[-1],
                 r["subtitle"], f"Generated {datetime.now():%d %b %Y %H:%M}", "=" * total_w, line(r["headers"]), "-" * total_w]
        for cells, style in r["rows"]:
            padded = list(cells) + [""] * (width - len(cells))
            if style == "total":
                lines.append("-" * total_w)
            lines.append(line(padded))
            if style == "total":
                lines.append("-" * total_w)
        lines += ["", r["note"]] if r["note"] else []
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        ui.info("Printable report saved. Open it and print from any text editor.")

    def on_search(self):
        self.from_e.focus_set()
