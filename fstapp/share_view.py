"""Share dialog: preview the image, choose a contact, open WhatsApp with the image ready to paste."""
import os
import shutil
import tkinter as tk
import webbrowser
from tkinter import filedialog

from . import ui_kit as ui
from .documents import share_message
from .share import copy_image, normalise_phone, whatsapp_url


class ShareDialog:
    def __init__(self, app, png_path, info):
        self.app = app
        self.path = png_path
        self.info = info
        self.win = tk.Toplevel(app.root)
        self.win.title("Share on WhatsApp")
        self.win.configure(bg=ui.C["card"])
        self.win.geometry("640x760")
        self.win.transient(app.root)
        self._build()

    def _build(self):
        w = self.win
        cc = self.app.db.get_setting("whatsapp_country_code", "92")
        head = tk.Frame(w, bg=ui.C["card"], padx=22, pady=16)
        head.pack(fill="x")
        tk.Label(head, text=f"Send {self.info['title']} {self.info['number']}", font=ui.font(15, True),
                 bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(head, text="The invoice is sent as an image. Choose who to send it to.",
                 font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"]).pack(anchor="w", pady=(2, 0))

        preview = tk.Frame(w, bg=ui.C["card"], padx=22)
        preview.pack(fill="x")
        try:
            self._img = tk.PhotoImage(master=w, file=self.path)
            factor = max(1, self._img.width() // 560)
            tk.Label(preview, image=self._img.subsample(factor), bg=ui.C["card"], bd=0).pack()
        except tk.TclError:
            tk.Label(preview, text="(preview not available)", bg=ui.C["card"], fg=ui.C["muted"]).pack()

        body = ui.card(w, pad=18)
        body.pack(fill="both", expand=True, padx=16, pady=12)
        table = self.info["contact_table"]
        pick_wrap = tk.Frame(body, bg=ui.C["card"])
        pick_wrap.pack(fill="x")
        tk.Label(pick_wrap, text="Send to (type a name to search saved contacts)", font=ui.font(9),
                 bg=ui.C["card"], fg=ui.C["muted"], anchor="w").pack(fill="x")
        self.picker = ui.Picker(pick_wrap, lambda term: self.app.db.contact_options(table, term), width=44,
                                on_pick=self._on_pick)
        self.picker.pack(fill="x", ipady=4)
        self.picker.set(self.info["party_name"])

        phone_wrap, self.phone = ui.field(body, f"WhatsApp number (country code {cc} is added automatically)",
                                          width=40, value=self.info["party_phone"], bg=ui.C["card"])
        phone_wrap.pack(fill="x", pady=(12, 0))
        msg_wrap, self.message = ui.field(body, "Message sent with the image", width=40,
                                          value=share_message(self.info, self.app.user["business_name"]),
                                          bg=ui.C["card"])
        msg_wrap.pack(fill="x", pady=(12, 0))

        steps = ui.card(w, pad=14)
        steps.pack(fill="x", padx=16)
        tk.Label(steps, text="How it works", font=ui.font(10, True), bg=ui.C["card"], fg=ui.C["fg"]).pack(anchor="w")
        tk.Label(steps, text="1.  Press 'Copy image and open WhatsApp'. The image is copied and WhatsApp opens.\n"
                             "2.  In the chat, press Ctrl+V (⌘V on a Mac). The image appears in the message box.\n"
                             "3.  Press Send.",
                 font=ui.font(9), bg=ui.C["card"], fg=ui.C["muted"], justify="left").pack(anchor="w", pady=(4, 0))

        foot = tk.Frame(w, bg=ui.C["card"], padx=16, pady=16)
        foot.pack(fill="x", side="bottom")
        ui.Button(foot, "Close", w.destroy, "secondary", bg=ui.C["card"]).pack(side="right")
        ui.Button(foot, "Save image file", self._save_file, "secondary", bg=ui.C["card"]).pack(side="left")
        ui.Button(foot, "Copy image and open WhatsApp", self._send, "primary", bg=ui.C["card"]).pack(side="right", padx=8)

    def _on_pick(self, label, value):
        if value:
            self.picker.set(value["name"])
            self.phone.delete(0, "end")
            self.phone.insert(0, value["phone"] or "")

    def _send(self):
        cc = self.app.db.get_setting("whatsapp_country_code", "92")
        raw = self.phone.get().strip()
        phone = normalise_phone(raw, cc) if raw else None
        if raw and not phone:
            ui.error("That phone number does not look right.\nExample: 0300-1234567")
            return
        message = self.message.get().strip()
        copied = copy_image(self.path)
        webbrowser.open(whatsapp_url(phone, message))
        if copied:
            self.app.notify("Image copied. In WhatsApp press Ctrl+V (⌘V on a Mac), then Send.", 9000)
        else:
            ui.info("The image could not be copied automatically.\n\n"
                    f"It is saved at:\n{self.path}\n\n"
                    "In WhatsApp, click the attach button (📎), choose Photos or Document, "
                    "and select that file.")

    def _save_file(self):
        dest = filedialog.asksaveasfilename(parent=self.win, defaultextension=".png",
                                            initialfile=os.path.basename(self.path),
                                            filetypes=[("PNG image", "*.png")])
        if dest:
            shutil.copyfile(self.path, dest)
            ui.info("Image saved.")
