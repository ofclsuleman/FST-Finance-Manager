"""WhatsApp helpers: phone numbers, chat links and copying an image to the clipboard.

WhatsApp does not let a desktop program attach a file to a chosen contact, so
the flow is: copy the image to the clipboard, open the chat, and paste (Ctrl+V).
"""
import subprocess
import sys
from urllib.parse import quote

DEFAULT_COUNTRY_CODE = "92"
_NO_WINDOW = 0x08000000  # Windows: do not flash a console window


def normalise_phone(raw, country_code=DEFAULT_COUNTRY_CODE):
    """Return digits in international format (no +), or None if it cannot be used.

    Examples with country code 92: '0300-1234567' -> '923001234567',
    '+92 300 1234567' -> '923001234567', '3001234567' -> '923001234567'.
    """
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = country_code + digits[1:]
    elif len(digits) <= 10 and country_code:
        digits = country_code + digits
    return digits if 8 <= len(digits) <= 15 else None


def whatsapp_url(phone, message):
    """Link that opens a chat with the number and a pre-filled message.

    Without a phone number it opens WhatsApp's own chooser so you can pick the contact.
    """
    base = f"https://wa.me/{phone}" if phone else "https://wa.me/"
    return f"{base}?text={quote(message)}"


def copy_image(path):
    """Put a PNG on the clipboard. Returns True on success, False if the platform needs a manual paste."""
    try:
        if sys.platform.startswith("win"):
            safe = path.replace("'", "''")
            script = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                      f"[System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('{safe}'))")
            result = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", script],
                                    capture_output=True, timeout=20, creationflags=_NO_WINDOW)
            return result.returncode == 0
        if sys.platform == "darwin":
            safe = path.replace("\\", "\\\\").replace('"', '\\"')
            script = f'set the clipboard to (read (POSIX file "{safe}") as «class PNGf»)'
            return subprocess.run(["osascript", "-e", script], capture_output=True, timeout=20).returncode == 0
        # Linux: Wayland first, then X11
        try:
            with open(path, "rb") as f:
                if subprocess.run(["wl-copy", "--type", "image/png"], stdin=f, timeout=20).returncode == 0:
                    return True
        except (OSError, subprocess.SubprocessError):
            pass
        return subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-i", path],
                              capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
