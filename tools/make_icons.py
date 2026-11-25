"""
Generates the FST application icons using only the Python standard library.

Outputs (written to ../assets/):
  icon.png   - 256x256 PNG (used by Tkinter window / taskbar on Linux & macOS)
  icon.ico   - multi-size Windows icon (16, 32, 48, 64, 128, 256)
  icon.svg   - scalable vector source of the same design

Design: rounded blue tile, white geometric "F" and a gold coin (finance cue).
"""

import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")

BG_TOP = (59, 130, 246)      # #3B82F6
BG_BOTTOM = (30, 64, 175)    # #1E40AF
WHITE = (255, 255, 255)
GOLD = (245, 158, 11)        # #F59E0B
GOLD_EDGE = (217, 119, 6)    # #D97706


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def render(size):
    """Return raw RGBA rows (with filter bytes) for a size x size icon."""
    s = float(size)
    radius = s * 0.20
    rows = []

    def in_tile(x, y):
        cx = min(max(x, radius), s - radius)
        cy = min(max(y, radius), s - radius)
        return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2

    def in_f(u, v):
        stem = 0.28 <= u <= 0.41 and 0.24 <= v <= 0.76
        top = 0.28 <= u <= 0.70 and 0.24 <= v <= 0.37
        mid = 0.28 <= u <= 0.62 and 0.45 <= v <= 0.57
        return stem or top or mid

    cx, cy, cr = 0.74, 0.74, 0.15
    for y in range(size):
        row = bytearray([0])  # PNG filter type: none
        py = y + 0.5
        bg = _lerp(BG_TOP, BG_BOTTOM, py / s)
        for x in range(size):
            px = x + 0.5
            if not in_tile(px, py):
                row += b"\x00\x00\x00\x00"
                continue
            u, v = px / s, py / s
            color = bg
            if in_f(u, v):
                color = WHITE
            d2 = (u - cx) ** 2 + (v - cy) ** 2
            if d2 <= cr ** 2:
                color = GOLD_EDGE if d2 > (cr * 0.78) ** 2 else GOLD
            row += bytes((color[0], color[1], color[2], 255))
        rows.append(bytes(row))
    return b"".join(rows)


def png_bytes(size):
    raw = render(size)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def write_ico(path, sizes):
    images = [(s, png_bytes(s)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    directory = b""
    blobs = b""
    for size, data in images:
        dim = 0 if size >= 256 else size  # 0 means 256 in ICO directory
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    with open(path, "wb") as f:
        f.write(header + directory + blobs)


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#3B82F6"/>
      <stop offset="1" stop-color="#1E40AF"/>
    </linearGradient>
  </defs>
  <rect width="256" height="256" rx="51" fill="url(#bg)"/>
  <path fill="#FFFFFF" d="M72 61h30v134H72z"/>
  <path fill="#FFFFFF" d="M72 61h110v27H72z"/>
  <path fill="#FFFFFF" d="M72 116h88v26H72z"/>
  <circle cx="190" cy="190" r="38" fill="#D97706"/>
  <circle cx="190" cy="190" r="29" fill="#F59E0B"/>
</svg>
"""


def main():
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, "icon.png"), "wb") as f:
        f.write(png_bytes(256))
    write_ico(os.path.join(ASSETS, "icon.ico"), [16, 32, 48, 64, 128, 256])
    with open(os.path.join(ASSETS, "icon.svg"), "w", encoding="utf-8") as f:
        f.write(SVG)
    print("Icons written to", ASSETS)


if __name__ == "__main__":
    main()
