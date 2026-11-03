"""Main window: left sidebar navigation, top bar, content area and status bar.

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
from .pages.parties import PartyPage
from .pages.inventory import InventoryPage
from .pages.quotes import QuotationPage
from .pages.reports import ReportsPage
from .pages.settings import SettingsPage, AboutPage

NAV = [
    ("Home", "Dashboard", HomePage),
    ("Sales", "Sales", lambda app: InvoicePage(app, "sale")),
    ("Purchase", "Purchase", lambda app: InvoicePage(app, "purchase")),
    ("Customer", "Customers", lambda app: PartyPage(app, "customers")),
    ("Supplier", "Suppliers", lambda app: PartyPage(app, "suppliers")),
    ("Inventory", "Inventory", InventoryPage),
    ("Quotation", "Quotations", QuotationPage),
    ("Reports", "Reports", ReportsPage),
    ("Settings", "Settings", SettingsPage),
    ("About Us", "About Us", AboutPage),
]


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
        self.side = tk.Frame(self.root, bg=ui.C["side"], width=236)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        right = tk.Frame(self.root, bg=ui.C["bg"])
        right.pack(side="left", fill="both", expand=True)
        self._build_topbar(right)
        self.content = tk.Frame(right, bg=ui.C["bg"])
        self.content.pack(fill="both", expand=True, padx=24, pady=(4, 0))
        self.status = tk.Label(right, text="", anchor="w", font=ui.font(9),
                               bg=ui.C["card"], fg=ui.C["muted"], padx=14, pady=5)
        self.status.pack(fill="x", side="bottom")
        self._build_sidebar()

    def _build_sidebar(self):
        for w in self.side.winfo_children():
            w.destroy()
        top = tk.Frame(self.side, bg=ui.C["side"])
        top.pack(fill="x", padx=18, pady=(20, 14))
        logo = logo_image(self.root, 8)
        if logo:
            tk.Label(top, image=logo, bg=ui.C["side"], bd=0).pack(side="left")
        brand = tk.Frame(top, bg=ui.C["side"])
        brand.pack(side="left", padx=10)
        tk.Label(brand, text="FST", font=ui.font(15, True), bg=ui.C["side"],
                 fg=ui.C["side_title"]).pack(anchor="w")
        tk.Label(brand, text="Finance Management", font=ui.font(8), bg=ui.C["side"],
                 fg=ui.C["side_fg"]).pack(anchor="w")

        tk.Frame(self.side, bg=ui.C["side_hover"], height=1).pack(fill="x", padx=18, pady=6)
        self.nav_items = {}
        for key, label, _ in NAV:
            item = tk.Label(self.side, text=f"   {label}", anchor="w", font=ui.font(10),
                            cursor="hand2", padx=12, pady=9, bd=0)
            item.pack(fill="x", padx=12, pady=1)
            item.bind("<Button-1>", lambda e, k=key: self.go(k))
            item.bind("<Enter>", lambda e, w=item, k=key: self._nav_hover(w, k, True))
            item.bind("<Leave>", lambda e, w=item, k=key: self._nav_hover(w, k, False))
            self.nav_items[key] = item
        self._paint_nav()

        foot = tk.Frame(self.side, bg=ui.C["side"])
        foot.pack(side="bottom", fill="x", padx=18, pady=18)
        initial = (self.user["first_name"] or "U")[0].upper()
        avatar = tk.Label(foot, text=initial, font=ui.font(11, True), bg=ui.C["accent"],
                          fg="#FFFFFF", width=3, height=1)
        avatar.pack(side="left")
        who = tk.Frame(foot, bg=ui.C["side"])
        who.pack(side="left", padx=10)
        tk.Label(who, text=f"{self.user['first_name']} {self.user['last_name'] or ''}".strip(),
                 font=ui.font(10, True), bg=ui.C["side"], fg=ui.C["side_title"]).pack(anchor="w")
        tk.Label(who, text=self.user["business_name"], font=ui.font(8), bg=ui.C["side"],
                 fg=ui.C["side_fg"]).pack(anchor="w")

    def _nav_hover(self, widget, key, on):
        if key != self.current_name:
            widget.configure(bg=ui.C["side_hover"] if on else ui.C["side"])

    def _paint_nav(self):
        for key, item in self.nav_items.items():
            active = key == self.current_name
            item.configure(bg=ui.C["side_active"] if active else ui.C["side"],
                           fg=ui.C["side_active_fg"] if active else ui.C["side_fg"],
                           font=ui.font(10, active))

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
        other = "Dark mode" if self.db.get_setting("theme", "light") == "light" else "Light mode"
        ui.Button(right, other, self.toggle_theme, "secondary", bg=ui.C["bg"]).pack(side="left", padx=4)
        ui.Button(right, "Logout", self.logout, "secondary", bg=ui.C["bg"]).pack(side="left", padx=4)

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
        self.current_page.build(frame)
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
        """Rebuild sidebar, top bar and the visible page (theme or profile changed)."""
        self._leave()
        self.current_page = None
        self._build_frame()
        self.go(self.current_name or "Home")

    def toggle_theme(self):
        new = "dark" if self.db.get_setting("theme", "light") == "light" else "light"
        self.db.set_setting("theme", new)
        ui.set_theme(new)
        ui.style_ttk(self.root)
        self.refresh_chrome()

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
