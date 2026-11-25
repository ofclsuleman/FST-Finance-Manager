"""Reusable, theme-aware widgets. Pages are rebuilt on theme change, so colours
are read from C at build time."""
import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from .config import APP_NAME, DEFAULT_THEME, LEGACY_THEMES, THEMES

C = dict(THEMES[DEFAULT_THEME])
FAMILY = "Arial"
_PREFERRED = ["Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Helvetica", "Arial"]


def init_fonts(root):
    """Pick the first professional font installed on this computer."""
    global FAMILY
    available = set(tkfont.families(root))
    FAMILY = next((f for f in _PREFERRED if f in available), "Arial")


def font(size=10, bold=False):
    return (FAMILY, size, "bold") if bold else (FAMILY, size)


def theme_key(name):
    """The theme key for a saved name, including the two older light/dark names."""
    name = LEGACY_THEMES.get(name, name)
    return name if name in THEMES else DEFAULT_THEME


def set_theme(name):
    C.clear()
    C.update(THEMES[theme_key(name)])


def style_ttk(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure("Treeview", background=C["card"], fieldbackground=C["card"],
                foreground=C["fg"], rowheight=30, borderwidth=0, font=font(10))
    s.configure("Treeview.Heading", background=C["head"], foreground=C["muted"],
                font=font(9, True), relief="flat", padding=(8, 6))
    s.map("Treeview", background=[("selected", C["accent"])],
          foreground=[("selected", C["accent_fg"])])
    s.map("Treeview.Heading", background=[("active", C["head_hover"])])
    s.configure("TCombobox", fieldbackground=C["entry"], background=C["entry"],
                foreground=C["fg"], arrowcolor=C["muted"], padding=5)
    s.map("TCombobox", fieldbackground=[("readonly", C["entry"])],
          foreground=[("readonly", C["fg"])])
    s.configure("TScrollbar", background=C["card"], troughcolor=C["bg"],
                bordercolor=C["bg"], arrowcolor=C["muted"])
    root.option_add("*TCombobox*Listbox.font", font(10))
    root.option_add("*TCombobox*Listbox.background", C["entry"])
    root.option_add("*TCombobox*Listbox.foreground", C["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["accent"])


def _shade(hex_color, factor=0.9):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


class Button(tk.Label):
    """Flat button with hover feedback. kind: primary | secondary | danger | ghost."""

    def __init__(self, parent, text, command=None, kind="primary", bg=None):
        self.command = command
        self.kind = kind
        self._parent_bg = bg or C["card"]
        flat = kind == "ghost"
        super().__init__(parent, text=text, cursor="hand2", font=font(10, True),
                         padx=16, pady=8, bd=0 if flat else 2, relief="flat" if flat else "raised",
                         highlightthickness=0)
        self._paint(False)
        self.bind("<Button-1>", lambda e: self.command() if self.command else None)
        self.bind("<Enter>", lambda e: self._paint(True))
        self.bind("<Leave>", lambda e: self._paint(False))

    def _paint(self, hover):
        if self.kind == "primary":
            bg, fg = (C["accent_hover"] if hover else C["accent"]), C["accent_fg"]
        elif self.kind == "danger":
            bg, fg = (C["danger_hover"] if hover else C["danger"]), "#FFFFFF"
        elif self.kind == "ghost":
            bg, fg = (C["head"] if hover else self._parent_bg), C["accent"]
        else:
            bg, fg = (C["head_hover"] if hover else C["head"]), C["fg"]
        self.configure(bg=bg, fg=fg)


def card(parent, pad=18, bg=None):
    """Raised neumorphic panel: same surface colour as the page, with a soft raised edge."""
    return tk.Frame(parent, bg=bg or C["card"], relief="raised", bd=3, highlightthickness=0,
                    padx=pad, pady=pad)


def scroll_body(parent):
    """A page that scrolls when the window is short, so nothing is ever cut off.
    Returns the frame to build the page in."""
    outer = tk.Frame(parent, bg=C["bg"])
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, bd=0)
    bar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=C["bg"])
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

    def wheel(e):
        canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")

    inner.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
    inner.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
    return inner


def page_header(parent, title, subtitle=""):
    head = tk.Frame(parent, bg=C["bg"])
    tk.Label(head, text=title, font=font(20, True), bg=C["bg"], fg=C["fg"]).pack(anchor="w")
    if subtitle:
        tk.Label(head, text=subtitle, font=font(10), bg=C["bg"], fg=C["muted"]).pack(anchor="w")
    return head


def section_label(parent, text, bg=None):
    return tk.Label(parent, text=text, font=font(11, True), bg=bg or C["card"], fg=C["fg"])


def field(parent, label, width=20, show=None, value="", bg=None):
    bg = bg or C["card"]
    wrap = tk.Frame(parent, bg=bg)
    tk.Label(wrap, text=label, font=font(9), bg=bg, fg=C["muted"], anchor="w").pack(fill="x")
    entry = tk.Entry(wrap, width=width, font=font(10), bg=C["entry"], fg=C["fg"],
                     insertbackground=C["fg"], relief="sunken", bd=2, highlightthickness=0,
                     show=show or "")
    entry.pack(fill="x", ipady=6)
    if value:
        entry.insert(0, str(value))
    return wrap, entry


def set_entry(entry, value):
    entry.delete(0, "end")
    entry.insert(0, "" if value is None else str(value))


def date_field(parent, label, width=14, value="", bg=None):
    """Like field(), but with a Calendar button that fills the box with a clicked date.
    The box still accepts typing (YYYY-MM-DD), so both ways work."""
    bg = bg or C["card"]
    wrap = tk.Frame(parent, bg=bg)
    tk.Label(wrap, text=label, font=font(9), bg=bg, fg=C["muted"], anchor="w").pack(fill="x")
    row = tk.Frame(wrap, bg=bg)
    row.pack(fill="x")
    entry = tk.Entry(row, width=width, font=font(10), bg=C["entry"], fg=C["fg"],
                     insertbackground=C["fg"], relief="sunken", bd=2, highlightthickness=0)
    entry.pack(side="left", fill="x", expand=True, ipady=6)
    if value:
        entry.insert(0, str(value))
    Button(row, "Calendar", lambda: CalendarPopup(row, entry), "ghost", bg=bg).pack(side="left", padx=(6, 0))
    return wrap, entry


class CalendarPopup:
    """Small month calendar. Clicking a day writes it to the entry as YYYY-MM-DD."""

    def __init__(self, anchor, entry):
        self.entry = entry
        try:
            shown = datetime.strptime(entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            shown = date.today()
        self.year, self.month = shown.year, shown.month
        self.selected = shown
        self.win = tk.Toplevel(anchor)
        self.win.title("Pick a date")
        self.win.configure(bg=C["card"])
        self.win.transient(anchor.winfo_toplevel())
        self.win.resizable(False, False)
        self.win.geometry(f"+{anchor.winfo_rootx()}+{anchor.winfo_rooty() + anchor.winfo_height() + 4}")
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.body = tk.Frame(self.win, bg=C["card"], padx=12, pady=12)
        self.body.pack()
        self.render()

    def _step(self, months):
        total = self.year * 12 + (self.month - 1) + months
        self.year, self.month = divmod(total, 12)
        self.month += 1
        self.render()

    def pick(self, day):
        chosen = date(self.year, self.month, day)
        set_entry(self.entry, chosen.strftime("%Y-%m-%d"))
        self.win.destroy()

    def render(self):
        for w in self.body.winfo_children():
            w.destroy()
        head = tk.Frame(self.body, bg=C["card"])
        head.pack(fill="x", pady=(0, 8))
        nav = dict(font=font(12, True), bg=C["card"], fg=C["accent"], cursor="hand2", padx=8)
        tk.Label(head, text="‹", **nav).pack(side="left")
        tk.Label(head, text=calendar.month_name[self.month] + f" {self.year}", font=font(10, True),
                 bg=C["card"], fg=C["fg"], width=18).pack(side="left", expand=True)
        tk.Label(head, text="›", **nav).pack(side="right")
        head.winfo_children()[0].bind("<Button-1>", lambda e: self._step(-1))
        head.winfo_children()[-1].bind("<Button-1>", lambda e: self._step(1))

        grid = tk.Frame(self.body, bg=C["card"])
        grid.pack()
        for col, name in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            tk.Label(grid, text=name, font=font(9), bg=C["card"], fg=C["muted"], width=4).grid(row=0, column=col)
        for r, week in enumerate(calendar.monthcalendar(self.year, self.month), start=1):
            for col, day in enumerate(week):
                if not day:
                    tk.Label(grid, text="", bg=C["card"], width=4).grid(row=r, column=col, pady=2)
                    continue
                is_sel = self.selected == date(self.year, self.month, day)
                btn = tk.Button(grid, text=str(day), width=3, relief="flat", cursor="hand2", font=font(9, is_sel),
                                bg=C["accent"] if is_sel else C["entry"],
                                fg=C["accent_fg"] if is_sel else C["fg"],
                                activebackground=C["head_hover"], command=lambda d=day: self.pick(d))
                btn.grid(row=r, column=col, padx=1, pady=1)

        foot = tk.Frame(self.body, bg=C["card"])
        foot.pack(fill="x", pady=(8, 0))
        Button(foot, "Today", lambda: self._jump(date.today()), "ghost", bg=C["card"]).pack(side="left")
        Button(foot, "Close", self.win.destroy, "secondary", bg=C["card"]).pack(side="right")

    def _jump(self, d):
        self.year, self.month = d.year, d.month
        self.selected = d
        self.pick(d.day)


def stat_card(parent, label, value, color):
    box = card(parent, pad=16)
    tk.Frame(box, bg=color, width=4).place(x=0, y=0, relheight=1)
    tk.Label(box, text=label, font=font(9), bg=C["card"], fg=C["muted"]).pack(anchor="w")
    tk.Label(box, text=value, font=font(17, True), bg=C["card"], fg=C["fg"]).pack(anchor="w", pady=(4, 0))
    return box


class Picker(ttk.Combobox):
    """Type-to-search combobox that loads matches from the database.

    provider(term) -> list of (label, value). The value of the chosen label is
    available from selected(). Opening the dropdown lists everything.
    """

    def __init__(self, parent, provider, width=30, on_pick=None, placeholder=None):
        super().__init__(parent, width=width, font=font(10))
        self.provider = provider
        self.on_pick = on_pick
        self.placeholder = placeholder
        self._picked_label = None
        self._map = {}
        self.configure(postcommand=lambda: self._load(self.get()))
        self.bind("<KeyRelease>", self._on_key)
        self.bind("<<ComboboxSelected>>", self._on_select)
        # Mouse wheel steps through the options without opening the list.
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", self._wheel)
        self.bind("<Button-5>", self._wheel)

    def _wheel(self, event):
        """Wheel up = previous option, wheel down = next option."""
        up = event.num == 4 or getattr(event, "delta", 0) > 0
        options = list(self.provider(self._search_text("")))
        if not options:
            return "break"
        self._map = {label: value for label, value in options}
        labels = [label for label, _ in options]
        self["values"] = labels
        current = self.get().strip()
        if current in labels:
            index = labels.index(current) + (-1 if up else 1)
        else:
            index = 0 if not up else len(labels) - 1
        label = labels[max(0, min(len(labels) - 1, index))]
        self.set(label)
        self._on_select(None)
        return "break"

    def _search_text(self, text):
        """The text to search for. A placeholder or a label already chosen means 'show everything'."""
        text = (text or "").strip()
        if text and (text == self.placeholder or text == self._picked_label):
            return ""
        return text

    def _load(self, text):
        self._map = {label: value for label, value in self.provider(self._search_text(text))}
        self["values"] = list(self._map.keys())

    def set(self, value):
        self._picked_label = value
        super().set(value)

    def _on_key(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape", "Tab", "Shift_L"):
            return
        self._load(self.get())

    def _on_select(self, _event):
        self._picked_label = self.get()
        if self.on_pick:
            self.on_pick(self.get(), self._map.get(self.get()))

    def selected(self):
        """Return the stored value for the current text, or None if it was typed freely."""
        return self._map.get(self.get())

    def set_text(self, text):
        self.set(text)


class Table(tk.Frame):
    """Styled, striped Treeview. columns: list of (key, title, width, anchor)."""

    def __init__(self, parent, columns, height=10, on_double=None):
        super().__init__(parent, bg=C["card"])
        self.keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self.keys, show="headings",
                                 height=height, selectmode="extended")
        for key, title, width, anchor in columns:
            self.tree.heading(key, text=title, anchor=anchor)
            self.tree.column(key, width=width, anchor=anchor, stretch=True)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("odd", background=C["row_alt"])
        self.tree.tag_configure("warn", foreground=C["warn"])
        self.tree.tag_configure("bad", foreground=C["danger"])
        self.tree.tag_configure("good", foreground=C["success"])
        if on_double:
            self.tree.bind("<Double-1>", lambda e: on_double())

    def set_rows(self, rows):
        """rows: list of (iid, values, tag_or_None)."""
        self.tree.delete(*self.tree.get_children())
        for i, (iid, values, tag) in enumerate(rows):
            tags = [tag] if tag else []
            if i % 2:
                tags.append("odd")
            self.tree.insert("", "end", iid=str(iid), values=values, tags=tags)

    def selected_ids(self):
        return [int(i) for i in self.tree.selection()]

    def first_selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None


def ask(msg, title=APP_NAME):
    return messagebox.askyesno(title, msg)


def info(msg, title=APP_NAME):
    messagebox.showinfo(title, msg)


def error(msg, title=APP_NAME):
    messagebox.showerror(title, msg)


def prompt_value(parent, title, prompt, initial=""):
    """Small themed modal asking for one value. Returns the text or None."""
    result = {"v": None}
    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=C["card"])
    win.transient(parent)
    win.resizable(False, False)
    tk.Label(win, text=prompt, font=font(10), bg=C["card"], fg=C["fg"]).pack(padx=24, pady=(20, 8))
    entry = tk.Entry(win, font=font(11), bg=C["entry"], fg=C["fg"], insertbackground=C["fg"],
                     relief="flat", width=26)
    entry.pack(padx=24, ipady=6)
    entry.insert(0, initial)
    entry.focus_set()

    def ok(_=None):
        result["v"] = entry.get().strip()
        win.destroy()

    row = tk.Frame(win, bg=C["card"])
    row.pack(pady=16)
    Button(row, "Cancel", win.destroy, "secondary", bg=C["card"]).pack(side="left", padx=6)
    Button(row, "OK", ok, "primary", bg=C["card"]).pack(side="left", padx=6)
    entry.bind("<Return>", ok)
    win.grab_set()
    parent.wait_window(win)
    return result["v"]
