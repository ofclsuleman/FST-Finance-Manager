"""Render invoices and quotations as PNG images for sharing.

Uses Pillow (pip install pillow). Pillow is imported inside the functions so the
rest of the app still starts if it is missing; the share buttons then explain
what to install.
"""
import json
import os

from .config import DATA_DIR

SHARE_DIR = os.path.join(DATA_DIR, "shares")
W, M = 1000, 40
ACCENT = (37, 99, 235)
INK = (15, 23, 42)
MUTED = (100, 116, 139)
HEAD = (238, 242, 247)
ALT = (248, 250, 252)
LINE = (226, 232, 240)
WHITE = (255, 255, 255)
REGULAR = ["DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc", "Calibri.ttf"]
BOLD = ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf", "Calibri Bold.ttf"]
_fonts = {}


def _font(size, bold=False):
    from PIL import ImageFont
    key = (size, bold)
    if key not in _fonts:
        font = None
        for name in (BOLD if bold else REGULAR):
            try:
                font = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        if font is None:
            try:
                font = ImageFont.load_default(size=size)
            except TypeError:  # very old Pillow
                font = ImageFont.load_default()
        _fonts[key] = font
    return _fonts[key]


def _wrap(text, font, max_w):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if not cur or font.getlength(trial) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def render_document(path, *, business, title, number, date, meta, columns, rows, totals, footer):
    """Draw a one-page document and save it as PNG.

    meta:    [(label, value)] shown under the header
    columns: [(header, weight, align)]; the first column holds the item name and description
    rows:    [(item_name, description, [cell text for each remaining column])]
    totals:  [(label, value, strong)]
    footer:  [line]
    """
    from PIL import Image, ImageDraw

    usable = W - 2 * M
    weight_sum = sum(c[1] for c in columns)
    widths = [usable * c[1] / weight_sum for c in columns]
    f_body, f_small, f_head = _font(20), _font(16), _font(15, True)

    # Lay out the table first so the canvas can be sized exactly.
    row_layouts = []
    for item, desc, cells in rows:
        name_lines = _wrap(item, _font(20), widths[0] - 20)
        desc_lines = _wrap(desc, f_small, widths[0] - 20) if desc else []
        h = 16 + len(name_lines) * 28 + len(desc_lines) * 22 + 14
        row_layouts.append((name_lines, desc_lines, cells, max(h, 52)))
    canvas_h = 150 + len(meta) * 30 + 20 + 42 + sum(r[3] for r in row_layouts) + 24 + len(totals) * 34 + 60 + len(footer) * 24 + 60

    img = Image.new("RGB", (W, canvas_h), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 130], fill=ACCENT)
    d.text((M, 26), business, font=_font(30, True), fill=WHITE)
    d.text((M, 72), title, font=_font(20), fill=WHITE)
    d.text((W - M, 26), number, font=_font(24, True), fill=WHITE, anchor="ra")
    d.text((W - M, 72), date, font=_font(18), fill=WHITE, anchor="ra")

    y = 150
    for label, value in meta:
        d.text((M, y), label, font=_font(18), fill=MUTED)
        d.text((M + 170, y), value, font=_font(20, True), fill=INK)
        y += 30
    y += 20

    head_h = 42
    d.rectangle([M, y, W - M, y + head_h], fill=HEAD)
    x = M
    for (header, _, align), w in zip(columns, widths):
        _cell(d, header, x, y, w, head_h, f_head, MUTED, align)
        x += w
    y += head_h

    for i, (name_lines, desc_lines, cells, h) in enumerate(row_layouts):
        if i % 2:
            d.rectangle([M, y, W - M, y + h], fill=ALT)
        ty = y + 12
        for ln in name_lines:
            d.text((M + 10, ty), ln, font=f_body, fill=INK)
            ty += 28
        for ln in desc_lines:
            d.text((M + 10, ty), ln, font=f_small, fill=MUTED)
            ty += 22
        x = M + widths[0]
        for (_, _, align), w, cell in zip(columns[1:], widths[1:], cells):
            _cell(d, cell, x, y, w, h, f_body, INK, align)
            x += w
        y += h
        d.line([M, y, W - M, y], fill=LINE)

    y += 24
    for label, value, strong in totals:
        f = _font(22, True) if strong else _font(19)
        d.text((W - M - 380, y), label, font=f, fill=INK if strong else MUTED)
        d.text((W - M, y), value, font=f, fill=ACCENT if strong else INK, anchor="ra")
        y += 34

    y += 26
    d.line([M, y, W - M, y], fill=LINE)
    y += 16
    for line in footer:
        d.text((M, y), line, font=_font(16), fill=MUTED)
        y += 24

    img = img.crop((0, 0, W, y + 30))
    img.save(path, "PNG", optimize=True)
    return path


def _cell(d, text, x, y, w, h, font, fill, align):
    if align == "r":
        d.text((x + w - 10, y + h / 2), str(text), font=font, fill=fill, anchor="rm")
    else:
        d.text((x + 10, y + h / 2), str(text), font=font, fill=fill, anchor="lm")


def _path(number):
    os.makedirs(SHARE_DIR, exist_ok=True)
    safe = "".join(ch for ch in number if ch.isalnum() or ch in "-_")
    return os.path.join(SHARE_DIR, f"{safe}.png")


def invoice_image(db, user, kind, inv_id):
    """Render a sale or purchase invoice. Returns (png_path, info dict)."""
    head = db.invoice_detail(kind, inv_id)
    if not head:
        raise ValueError("This invoice no longer exists.")
    is_sale = kind == "sale"
    cur = user["currency"]
    party = (head.get("customer_name") if is_sale else head.get("supplier_name")) or ""
    phone = (head.get("customer_phone") if is_sale else head.get("supplier_phone")) or ""
    linked_id = head.get("customer_id") if is_sale else head.get("supplier_id")
    if not phone and linked_id:  # invoice linked to a saved contact: use that contact's number
        table = "customers" if is_sale else "suppliers"
        contact = db.one(f"SELECT name, phone FROM {table} WHERE id=?", (linked_id,))
        if contact:
            phone = contact["phone"] or ""
            party = party or contact["name"]
    due = round(head["total"] - head["paid"], 2)
    status = "Paid" if due <= 0.005 else ("Partly paid" if head["paid"] > 0 else "Unpaid")
    title = "Sales invoice" if is_sale else "Purchase invoice"

    rows = [(it["product_name"], it.get("description") or "",
             [f"{it['qty']:g}", f"{it['unit_price']:,.2f}", f"{it['line_total']:,.2f}"]) for it in head["items"]]
    totals = [("Subtotal", f"{head['subtotal']:,.2f}", False)]
    if head["discount"]:
        totals.append(("Discount", f"-{head['discount']:,.2f}", False))
    if head["tax"]:
        totals.append(("Tax", f"{head['tax']:,.2f}", False))
    totals += [("Total", f"{cur} {head['total']:,.2f}", True),
               ("Paid", f"{head['paid']:,.2f}", False),
               ("Balance due", f"{max(due, 0):,.2f}", True)]
    meta = [("Customer" if is_sale else "Supplier", party or ("Walk-in customer" if is_sale else "-"))]
    if phone:
        meta.append(("Phone", phone))
    meta.append(("Status", status))
    path = render_document(
        _path(head["invoice_no"]), business=user["business_name"], title=title, number=head["invoice_no"],
        date=head["created_at"][:10], meta=meta,
        columns=[("Item", 3.2, "l"), ("Qty", 1, "r"), ("Price", 1.4, "r"), ("Amount", 1.6, "r")],
        rows=rows, totals=totals,
        footer=[f"Payment method: {head['payment_method'] or '-'}", "Thank you for your business."])
    info = {"title": title, "number": head["invoice_no"], "party_name": party, "party_phone": phone,
            "total": f"{cur} {head['total']:,.2f}", "balance": f"{cur} {max(due, 0):,.2f}" if due > 0.005 else "",
            "contact_table": "customers" if is_sale else "suppliers"}
    return path, info


def quotation_image(db, user, quote_id):
    """Render a quotation. Returns (png_path, info dict)."""
    q = db.one("SELECT * FROM quotations WHERE id=?", (quote_id,))
    if not q:
        raise ValueError("This quotation no longer exists.")
    cur = user["currency"]
    items = json.loads(q["items_json"])
    rows = [(i["name"], i.get("desc", ""), [f"{i['qty']:g}", f"{i['price']:,.2f}", f"{i['qty'] * i['price']:,.2f}"])
            for i in items]
    totals = [("Subtotal", f"{q['subtotal']:,.2f}", False)]
    if q["discount"]:
        totals.append(("Discount", f"-{q['discount']:,.2f}", False))
    if q["tax"]:
        totals.append(("Tax", f"{q['tax']:,.2f}", False))
    totals.append(("Total", f"{cur} {q['total']:,.2f}", True))
    meta = [("Customer", q["customer_name"] or "Customer")]
    if q["customer_phone"]:
        meta.append(("Phone", q["customer_phone"]))
    meta += [("Valid until", q["valid_until"] or "-"), ("Status", q["status"])]
    path = render_document(
        _path(q["quote_no"]), business=user["business_name"], title="Quotation", number=q["quote_no"],
        date=q["created_at"][:10], meta=meta,
        columns=[("Item", 3.2, "l"), ("Qty", 1, "r"), ("Price", 1.4, "r"), ("Amount", 1.6, "r")],
        rows=rows, totals=totals,
        footer=["Prices are valid until the date shown above.", "Thank you for your enquiry."])
    info = {"title": "Quotation", "number": q["quote_no"], "party_name": q["customer_name"] or "",
            "party_phone": q["customer_phone"] or "", "total": f"{cur} {q['total']:,.2f}", "balance": "",
            "contact_table": "customers"}
    return path, info


def share_message(info, business):
    """Short text sent with the image, so the chat has context even without opening it."""
    lines = [f"{info['title']} {info['number']} from {business}", f"Total: {info['total']}"]
    if info.get("balance"):
        lines.append(f"Balance due: {info['balance']}")
    lines.append("Thank you.")
    return "\n".join(lines)
