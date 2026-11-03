"""FST - Finance Management: entry point.

Run:  python fst_finance.py
"""
import sys
import tkinter as tk

from fstapp import ui_kit as ui
from fstapp.auth_view import AuthView
from fstapp.config import APP_NAME, resource_path
from fstapp.database import Database
from fstapp.shell import MainWindow

LOGIN_SIZE = "1000x640"
APP_SIZE = "1280x800"


def apply_icon(root):
    """Window and taskbar icon. Cosmetic only, so a failure never blocks startup."""
    try:
        if sys.platform.startswith("win"):
            root.iconbitmap(resource_path("assets", "icon.ico"))
        else:
            root.iconphoto(True, tk.PhotoImage(master=root, file=resource_path("assets", "icon.png")))
    except tk.TclError:
        pass


def main():
    root = tk.Tk()
    root.title(APP_NAME)
    apply_icon(root)
    ui.init_fonts(root)
    db = Database()
    ui.set_theme(db.get_setting("theme", "light"))
    ui.style_ttk(root)

    def clear():
        for w in root.winfo_children():
            w.destroy()

    def show_login():
        clear()
        root.geometry(LOGIN_SIZE)
        root.minsize(900, 600)
        root.configure(bg=ui.C["bg"])
        AuthView(root, db, on_login=start_app)

    def start_app(user):
        clear()
        root.geometry(APP_SIZE)
        MainWindow(root, db, user, on_logout=show_login)

    show_login()
    root.mainloop()
    db.conn.close()


if __name__ == "__main__":
    sys.exit(main())
