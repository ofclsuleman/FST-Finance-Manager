"""Image dialog: preview an invoice or quotation and copy it to the clipboard.

The image can be pasted anywhere (WhatsApp, email, Word, Messages, etc.).
The caption text can be copied separately.
"""
import os
import shutil
import tkinter as tk
from tkinter import filedialog

from . import ui_kit as ui
from .documents import share_message
from .share import copy_image


class ImageDialog:
    def __init__(self, app, png_path, info):
        self.app = app
        self.path = png_path
        self.info = info
        self.win = tk.Toplevel(app.root)
        self.win.title("Invoice image")
        self.win.configure(bg=ui.C["card"])
        self.win.geometry("640x700")
        self.win.transient(app.root)
        self._build()

    def _build(self):
        w = self.win
        head = tk.Frame(w, bg=ui.C["card"], padx=22, pady=16)
        head.pack(fill="x")
        tk.Label(head, text=f"{self.info['title']} {self.info['number']}", font=ui.font(15, True),
                 bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(head, text="Copy the image, then paste it (Ctrl+V, or ⌘V on a Mac) wherever you need it.",
                 font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(2, 0))

        preview = tk.Frame(w, bg=ui.C["card"], padx=22)
        preview.pack(fill="x")
        try:
            self._img = tk.PhotoImage(master=w, file=self.path)
            factor = max(1, self._img.width() // 560)
            tk.Label(preview, image=self._img.subsample(factor), bg=ui.C["card"], bd=0).pack()
        except tk.TclError:
            tk.Label(preview, text="(preview not available)", bg=ui.C["card"], fg=ui.C["muted"]).pack()

        caption = ui.card(w, pad=16)
        caption.pack(fill="x", padx=16, pady=12)
        row = tk.Frame(caption, bg=ui.C["card"])
        row.pack(fill="x")
        tk.Label(row, text="Caption text (optional, for messages)", font=ui.font(9), bg=ui.C["card"],
                 fg=ui.C["muted"], anchor="w").pack(side="left")
        ui.Button(row, "Copy text", self._copy_text, "ghost", bg=ui.C["card"]).pack(side="right")
        self.text = tk.Text(caption, height=4, wrap="word", font=ui.font(10), relief="flat",
                            bg=ui.C["entry"], fg=ui.C["fg"], padx=8, pady=6)
        self.text.insert("1.0", share_message(self.info, self.app.user["business_name"]))
        self.text.pack(fill="x", pady=(6, 0))

        steps = ui.card(w, pad=14)
        steps.pack(fill="x", padx=16)
        tk.Label(steps, text="How to use it", font=ui.font(10, True), bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(steps, text="1.  Press 'Copy image to clipboard'.\n"
                             "2.  Open WhatsApp, email, Word or any other app.\n"
                             "3.  Press Ctrl+V (⌘V on a Mac) to paste the image.",
                 font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], justify="left").pack(anchor="w", pady=(4, 0))

        foot = tk.Frame(w, bg=ui.C["card"], padx=16, pady=16)
        foot.pack(fill="x", side="bottom")
        self.status = tk.Label(foot, text="", font=ui.font(9, True), bg=ui.C["card"], fg=ui.C["success"])
        self.status.pack(side="left")
        ui.Button(foot, "Close", w.destroy, "secondary", bg=ui.C["card"]).pack(side="right")
        ui.Button(foot, "Save image file", self._save_file, "secondary", bg=ui.C["card"]).pack(side="right", padx=8)
        ui.Button(foot, "Copy image to clipboard", self._copy, "primary", bg=ui.C["card"]).pack(side="right")

    def _copy(self):
        if copy_image(self.path):
            self.status.configure(text="Image copied. Paste it with Ctrl+V (⌘V on a Mac).")
        else:
            ui.info("The image could not be copied automatically.\n\n"
                    f"It is saved at:\n{self.path}\n\n"
                    "Use 'Save image file' to keep a copy, then attach it in your app.")

    def _copy_text(self):
        text = self.text.get("1.0", "end").strip()
        self.win.clipboard_clear()
        self.win.clipboard_append(text)
        self.status.configure(text="Caption text copied.")

    def _save_file(self):
        dest = filedialog.asksaveasfilename(parent=self.win, defaultextension=".png",
                                            initialfile=os.path.basename(self.path),
                                            filetypes=[("PNG image", "*.png")])
        if dest:
            shutil.copyfile(self.path, dest)
            ui.info("Image saved.")
