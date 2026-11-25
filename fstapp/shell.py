"""Main window: dark top bar with the menu centred, then the page area and status bar.

Pages are built lazily when opened and rebuilt on theme change. Their data
(e.g. an unfinished invoice) lives on the page object, so it survives rebuilds.
"""
import tkinter as tk
from datetime import datetime

from . import ui_kit as ui
from .auth_view import logo_image
from .config import APP_NAME, APP_VERSION
from .pages.home import HomePage
from .pages.invoices import InvoicePage
from .pages.parties import PartiesPage
from .pages.inventory import InventoryPage
from .pages.quotes import QuotationPage
from .pages.ledger import LedgerPage
from .pages.entries import EntriesPage
from .pages.settings import SettingsPage, AboutPage

NAV = [
    ("Home", "Dashboard", HomePage),
    ("Sales", "Sales", lambda app: InvoicePage(app, "sale")),
    ("Purchase", "Purchase", lambda app: InvoicePage(app, "purchase")),
    ("Entries", "Sales & Purchase List", lambda app: EntriesPage(app)),
    ("Parties", "Customers & Suppliers", lambda app: PartiesPage(app)),
    ("Inventory", "Inventory", InventoryPage),
    ("Quotation", "Quotations", QuotationPage),
    ("Ledger", "Ledger", LedgerPage),
    ("Settings", "Settings", SettingsPage),
    ("About Us", "About Us", AboutPage),
]

HEADER_H = 60


class MainWindow:
    def __init__(self, root, db, user, on_logout):
        self.root = root
        self.db = db
        self.user = user
        self.on_logout = on_logout
        self.current_name = None
        self.current_page = None
        self.pages = {key: factory(self) for key, _, factory in NAV}
        self.root.title(f"{APP_NAME}")
        self.root.geometry("1280x800")
        self.root.minsize(1100, 700)
        self.root.configure(bg=ui.C["bg"])
        self._bind_shortcuts()
        self._build_frame()
        self.go("Home")

    # ---------------------------------------------------------- frame
    def _build_frame(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=ui.C["bg"])
        self.header = tk.Frame(self.root, bg=ui.C["side"], height=HEADER_H, relief="raised", bd=3)
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)
        body = tk.Frame(self.root, bg=ui.C["bg"])
        body.pack(side="top", fill="both", expand=True)
        self._build_topbar(body)
        self.content = tk.Frame(body, bg=ui.C["bg"])
        self.content.pack(fill="both", expand=True, padx=24, pady=(4, 0))
        self.status = tk.Label(body, text="", anchor="w", font=ui.font(9),
                               bg=ui.C["card"], fg=ui.C["muted"], padx=14, pady=5)
        self.status.pack(fill="x", side="bottom")
        self._build_header()

    def _build_header(self):
        """Dark bar: brand on the left, menu centred, logout on the right."""
        bar = self.header
        for w in bar.winfo_children():
            w.destroy()
        bar.grid_columnconfigure(1, weight=1)

        brand = tk.Frame(bar, bg=ui.C["side"])
        brand.grid(row=0, column=0, sticky="w", padx=(20, 0))
        logo = logo_image(self.root, 8)
        if logo:
            tk.Label(brand, image=logo, bg=ui.C["side"], bd=0).pack(side="left", padx=(0, 8))
        tk.Label(brand, text="FST", font=ui.font(14, True), bg=ui.C["side"],
                 fg=ui.C["side_title"]).pack(side="left")

        nav = tk.Frame(bar, bg=ui.C["side"])
        nav.grid(row=0, column=1)
        self.nav_items = {}
        for key, label, _ in NAV:
            cell = tk.Frame(nav, bg=ui.C["side"], cursor="hand2")
            cell.pack(side="left", padx=1)
            text = tk.Label(cell, text=label, font=ui.font(10), bg=ui.C["side"],
                            fg=ui.C["side_fg"], padx=9, cursor="hand2")
            text.pack(pady=(4, 0))
            dot = tk.Frame(cell, width=5, height=5, bg=ui.C["side"])
            dot.pack(pady=(3, 0))
            for w in (cell, text, dot):
                w.bind("<Button-1>", lambda e, k=key: self.go(k))
                w.bind("<Enter>", lambda e, k=key: self._nav_hover(k, True))
                w.bind("<Leave>", lambda e, k=key: self._nav_hover(k, False))
            self.nav_items[key] = (text, dot)
        self._paint_nav()

        right = tk.Frame(bar, bg=ui.C["side"])
        right.grid(row=0, column=2, sticky="e", padx=(0, 20))
        ui.Button(right, "Logout", self.logout, "secondary", bg=ui.C["side"]).pack(side="left", padx=4)

    def _nav_hover(self, key, on):
        if key != self.current_name:
            text, _ = self.nav_items[key]
            text.configure(fg=ui.C["side_title"] if on else ui.C["side_fg"])

    def _paint_nav(self):
        for key, (text, dot) in self.nav_items.items():
            active = key == self.current_name
            text.configure(fg=ui.C["side_title"] if active else ui.C["side_fg"], font=ui.font(10, active))
            dot.configure(bg=ui.C["accent"] if active else ui.C["side"])

    def _build_topbar(self, parent):
        bar = tk.Frame(parent, bg=ui.C["bg"])
        bar.pack(fill="x", padx=24, pady=(18, 10))
        left = tk.Frame(bar, bg=ui.C["bg"])
        left.pack(side="left")
        self.crumb = tk.Label(left, text="", font=ui.font(9), bg=ui.C["bg"], fg=ui.C["muted"])
        self.crumb.pack(anchor="w")
        tk.Label(left, text=f"{self.user['business_name']}  ·  {self.user['currency']}",
                 font=ui.font(11, True), bg=ui.C["bg"], fg=ui.C["fg"]).pack(anchor="w")

        right = tk.Frame(bar, bg=ui.C["bg"])
        right.pack(side="right")
        tk.Label(right, text=datetime.now().strftime("%a, %d %b %Y"), font=ui.font(9),
                 bg=ui.C["bg"], fg=ui.C["muted"]).pack(side="left", padx=12)
        from . import photo
        try:
            self._avatar_img = photo.circle_image(self.user.get("photo"), 32, self.root)
        except Exception:
            self._avatar_img = None
        if self._avatar_img:
            tk.Label(right, image=self._avatar_img, bg=ui.C["bg"], bd=0).pack(side="left", padx=(0, 8))
        else:
            initial = (self.user["first_name"] or "U")[0].upper()
            tk.Label(right, text=initial, font=ui.font(10, True), bg=ui.C["accent"],
                     fg="#FFFFFF", width=3, height=1).pack(side="left", padx=(0, 8))
        tk.Label(right, text=f"{self.user['first_name']} {self.user['last_name'] or ''}".strip(),
                 font=ui.font(10, True), bg=ui.C["bg"], fg=ui.C["fg"]).pack(side="left")

    # ---------------------------------------------------------- navigation
    def _leave(self):
        if self.current_page and hasattr(self.current_page, "leave"):
            self.current_page.leave()

    def go(self, key):
        self._leave()
        self.current_name = key
        self.current_page = self.pages[key]
        for w in self.content.winfo_children():
            w.destroy()
        frame = tk.Frame(self.content, bg=ui.C["bg"])
        frame.pack(fill="both", expand=True, pady=(4, 16))
        if getattr(self.current_page, "fit_window", False):
            self.current_page.build(frame)
        else:  # long pages scroll on short windows instead of being cut off
            self.current_page.build(ui.scroll_body(frame))
        label = dict((k, lbl) for k, lbl, _ in NAV)[key]
        self.crumb.configure(text=f"FST  /  {label}")
        self._paint_nav()

    def refresh_current(self):
        """Re-draw the visible page so new data (e.g. a new customer) appears everywhere."""
        if self.current_name:
            self.go(self.current_name)

    def notify(self, text, ms=4000):
        self.status.configure(text="  " + text)
        self.root.after(ms, lambda: self.status.configure(text=""))

    # ---------------------------------------------------------- actions
    def refresh_chrome(self):
        """Rebuild header, top bar and the visible page (theme or profile changed)."""
        self._leave()
        self.current_page = None
        self._build_frame()
        self.go(self.current_name or "Home")

    def logout(self):
        if ui.ask("Do you want to sign out?"):
            self.unbind_shortcuts()
            self.on_logout()

    def _bind_shortcuts(self):
        for i, (key, _, _) in enumerate(NAV[:9], start=1):
            self.root.bind(f"<Control-Key-{i}>", lambda e, k=key: self.go(k))
        self.root.bind("<Control-s>", lambda e: self._shortcut("on_save"))
        self.root.bind("<Control-n>", lambda e: self._shortcut("on_new"))
        self.root.bind("<Control-f>", lambda e: self._shortcut("on_search"))

    def unbind_shortcuts(self):
        for i in range(1, 10):
            self.root.unbind(f"<Control-Key-{i}>")
        for seq in ("<Control-s>", "<Control-n>", "<Control-f>"):
            self.root.unbind(seq)

    def _shortcut(self, method):
        fn = getattr(self.current_page, method, None)
        if fn:
            fn()
            return "break"
