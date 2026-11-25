"""Profile picture: cropped to a square, stored in the database as PNG, shown as a circle."""
import io

from PIL import Image, ImageChops, ImageDraw

SIZE = 256          # stored size (px)
MAX_FILE = 10 * 1024 * 1024
FILE_TYPES = [("Pictures", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("All files", "*.*")]


def prepare(path):
    """Read an image file and return PNG bytes: centre-cropped square, SIZE x SIZE.
    Raises ValueError if the file is not a picture we can read."""
    try:
        img = Image.open(path)
        img.load()
    except Exception as ex:  # Pillow raises several error types for bad files
        raise ValueError("That file is not a picture this program can read.") from ex
    img = img.convert("RGBA")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def circle_image(data, size, master):
    """A round Tk image of the stored picture, or None if there is no picture."""
    if not data:
        return None
    from PIL import ImageTk  # imported here so the rest works without Tk
    img = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.LANCZOS)
    # Anti-aliased circle: draw large, shrink, then multiply with the picture's own alpha.
    big = size * 4
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return ImageTk.PhotoImage(img, master=master)
