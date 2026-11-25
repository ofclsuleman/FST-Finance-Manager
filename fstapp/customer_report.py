"""Customer ledger for one customer and one date range.

One row per invoice. Each product is a line inside the row, with its name, description and amount.
Totals, Received, Remaining and Status are shown per invoice. A summary at the top gives the
opening balance, the total billed in the period, the amount received in the period and what
remains at the end of the period.

Invoices are included when they were dated in the period, or when a payment on them was received
in the period, so a payment is never left out of the summary.

The PDF is drawn with Pillow (already required by the app), so no extra package is needed.
"""
import csv
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

ALL_FROM = "0000-00-00"
ALL_TO = "9999-12-31"

CSV_COLUMNS = ["Date", "Invoice no", "Product", "Description", "Amount", "Total", "Received", "Remaining", "Status"]


# ---------------------------------------------------------------- data


def _status(total, received_all):
    due = round(total - received_all, 2)
    if due <= 0.005:
        return "Paid"
    if received_all > 0.005:
        return "Partly paid"
    return "Unpaid"


def collect(db, customer_id, date_from, date_to):
    """The ledger for one customer in the period.

    opening  = what the customer owed before the period starts
    billed   = total of the invoices dated in the period
    received = payments received in the period (on any of this customer's invoices)
    closing  = opening + billed - received (what remains at the end of the period)
    """
    party = db.one("SELECT * FROM customers WHERE id=?", (customer_id,))

    billed_before = db.scalar(
        "SELECT IFNULL(SUM(total),0) FROM sales WHERE customer_id=? AND date(created_at) < ?",
        (customer_id, date_from))
    paid_before = db.scalar(
        """SELECT IFNULL(SUM(p.amount),0) FROM payments p JOIN sales s ON s.id = p.invoice_id
           WHERE p.kind='sale' AND s.customer_id=? AND substr(p.paid_at,1,10) < ?""",
        (customer_id, date_from))
    opening = round((billed_before or 0) - (paid_before or 0), 2)

    invoices = db.query(
        """SELECT * FROM sales WHERE customer_id=?
           AND (date(created_at) BETWEEN ? AND ?
                OR id IN (SELECT invoice_id FROM payments WHERE kind='sale'
                          AND substr(paid_at,1,10) BETWEEN ? AND ?))
           ORDER BY created_at, id""",
        (customer_id, date_from, date_to, date_from, date_to))

    out = []
    adjustments = False
    billed = 0.0
    for inv in invoices:
        day = inv["created_at"][:10]
        in_period_billing = date_from <= day <= date_to
        if in_period_billing:
            billed += inv["total"]
        if inv["discount"] or inv["tax"]:
            adjustments = True
        received_period = db.scalar(
            """SELECT IFNULL(SUM(amount),0) FROM payments WHERE kind='sale' AND invoice_id=?
               AND substr(paid_at,1,10) BETWEEN ? AND ?""", (inv["id"], date_from, date_to)) or 0
        items = db.query(
            """SELECT si.product_name, si.description AS line_desc, p.description AS product_desc,
                      si.qty, si.line_total
               FROM sale_items si LEFT JOIN products p ON p.id = si.product_id
               WHERE si.sale_id=? ORDER BY si.id""", (inv["id"],))
        lines = [{"product": it["product_name"],
                  "description": it["line_desc"] or it["product_desc"] or "",
                  "qty": it["qty"], "amount": it["line_total"]} for it in items]
        out.append({
            "invoice_no": inv["invoice_no"],
            "date": day,
            "total": inv["total"],
            "received": round(received_period, 2),
            "remaining": round(inv["total"] - inv["paid"], 2),
            "status": _status(inv["total"], inv["paid"]),
            "lines": lines,
            "method": inv["payment_method"] or "",
        })

    received = db.scalar(
        """SELECT IFNULL(SUM(p.amount),0) FROM payments p JOIN sales s ON s.id = p.invoice_id
           WHERE p.kind='sale' AND s.customer_id=? AND substr(p.paid_at,1,10) BETWEEN ? AND ?""",
        (customer_id, date_from, date_to)) or 0
    billed = round(billed, 2)
    received = round(received, 2)
    return {
        "party": party,
        "invoices": out,
        "opening": opening,
        "billed": billed,
        "received": received,
        "closing": round(opening + billed - received, 2),
        "outstanding_now": db.customer_due(customer_id),
        "adjustments": adjustments,
        "first_date": out[0]["date"] if out else None,
        "date_from": date_from,
        "date_to": date_to,
    }


def period_text(data):
    start, end = data["date_from"], data["date_to"]
    frm = start if start != ALL_FROM else (data["first_date"] or "beginning")
    to = end if end != ALL_TO else datetime.now().strftime("%Y-%m-%d")
    return f"From {frm}  To {to}"


def _money(v):
    return f"{v:,.2f}"


# ---------------------------------------------------------------- CSV


def write_csv(path, data, business, currency):
    party = data["party"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Business", business])
        w.writerow(["Customer", party["name"]])
        w.writerow(["Phone", party["phone"] or ""])
        w.writerow(["Period", period_text(data)])
        w.writerow(["Currency", currency])
        w.writerow(["Opening balance", f"{data['opening']:.2f}"])
        w.writerow(["Total billed in period", f"{data['billed']:.2f}"])
        w.writerow(["Received in period", f"{data['received']:.2f}"])
        w.writerow(["Remaining at end of period", f"{data['closing']:.2f}"])
        w.writerow(["Outstanding now (all invoices)", f"{data['outstanding_now']:.2f}"])
        w.writerow([])
        w.writerow(CSV_COLUMNS)
        for inv in data["invoices"]:
            for n, line in enumerate(inv["lines"] or [{"product": "", "description": "", "amount": None}]):
                first = n == 0
                w.writerow([
                    inv["date"], inv["invoice_no"], line["product"], line["description"],
                    "" if line["amount"] is None else f"{line['amount']:.2f}",
                    f"{inv['total']:.2f}" if first else "",
                    f"{inv['received']:.2f}" if first else "",
                    f"{inv['remaining']:.2f}" if first else "",
                    inv["status"] if first else "",
                ])
        w.writerow(["Totals", "", "", "", "",
                    f"{sum(i['total'] for i in data['invoices']):.2f}",
                    f"{sum(i['received'] for i in data['invoices']):.2f}",
                    f"{sum(i['remaining'] for i in data['invoices']):.2f}", ""])


# ---------------------------------------------------------------- PDF

# Landscape A4 at 150 dpi.
A4_W, A4_H, DPI = 1754, 1240, 150
MARGIN = 70
CONTENT_W = A4_W - 2 * MARGIN
INK, MUTED, RULE, HEAD_BG, ACCENT = (15, 23, 42), (100, 116, 139), (203, 213, 225), (238, 242, 247), (37, 99, 235)
GREEN, AMBER, SUB = (22, 128, 61), (180, 83, 9), (71, 85, 105)
WHITE = (255, 255, 255)
# Date | Invoice no | Products (name, description, amount) | Total | Received | Remaining | Status
WIDTHS = [150, 300, 560, 150, 150, 160, 0]
WIDTHS[-1] = CONTENT_W - sum(WIDTHS[:-1])
HEADERS = ["Date", "Invoice no", "Products", "Total", "Received", "Remaining", "Status"]
ALIGNS = ["l", "l", "l", "r", "r", "r", "c"]
LINE_H = 30


def _font(size, bold=False):
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


class _Doc:
    def __init__(self):
        self.pages = []
        self.new_page()

    def new_page(self):
        self.img = Image.new("RGB", (A4_W, A4_H), "white")
        self.draw = ImageDraw.Draw(self.img)
        self.pages.append(self.img)
        self.y = MARGIN

    def room(self, height):
        if self.y + height > A4_H - MARGIN - 40:
            self.new_page()

    def text(self, x, y, s, size=24, bold=False, color=INK, anchor="la"):
        self.draw.text((x, y), s, font=_font(size, bold), fill=color, anchor=anchor)

    def header(self, xs):
        size, line_h = 21, 30
        self.room(line_h + 26)
        self.draw.rectangle((MARGIN, self.y, A4_W - MARGIN, self.y + line_h + 14), fill=HEAD_BG)
        for h, x, w, a in zip(HEADERS, xs, WIDTHS, ALIGNS):
            px = x + 14 if a == "l" else (x + w - 14 if a == "r" else x + w / 2)
            self.text(px, self.y + 9, h, size, True, INK, {"l": "la", "r": "ra", "c": "ma"}[a])
        self.y += line_h + 26


def _fit(text, font, width):
    while font.getlength(text) > width and len(text) > 8:
        text = text[:-4].rstrip(", ") + "..."
    return text


def _status_pill(doc, x, y, w, status):
    colour = {"Paid": GREEN, "Partly paid": AMBER, "Unpaid": AMBER}[status]
    doc.draw.rounded_rectangle((x + 12, y, x + w - 12, y + 30), radius=10, fill=colour)
    doc.draw.text((x + w / 2, y + 15), status, font=_font(18, True), fill=WHITE, anchor="mm")


def write_pdf(path, data, business, currency):
    party = data["party"]
    doc = _Doc()
    generated = datetime.now().strftime("%d %b %Y, %H:%M")
    xs = []
    x = MARGIN
    for w in WIDTHS:
        xs.append(x)
        x += w

    # Company name, then customer and period
    doc.text(MARGIN, doc.y, business, 46, True, ACCENT)
    doc.y += 62
    doc.text(MARGIN, doc.y, "Customer ledger", 28, False, MUTED)
    doc.y += 40
    doc.text(MARGIN, doc.y, f"Customer: {party['name']}", 36, True, INK)
    doc.y += 50
    doc.text(MARGIN, doc.y, f"Phone: {party['phone'] or '-'}      {period_text(data)}      Currency: {currency}",
             22, False, MUTED)
    doc.y += 32
    doc.text(MARGIN, doc.y, f"Generated {generated}", 20, False, MUTED)
    doc.y += 36
    doc.draw.line((MARGIN, doc.y, A4_W - MARGIN, doc.y), fill=RULE, width=2)
    doc.y += 22

    # Summary tiles
    tiles = [("Opening balance", data["opening"], INK),
             ("Total billed in period", data["billed"], INK),
             ("Received in period", data["received"], GREEN),
             ("Remaining at end", data["closing"], AMBER)]
    gap = 20
    tile_w = (CONTENT_W - 3 * gap) // 4
    doc.room(130)
    for i, (label, value, color) in enumerate(tiles):
        tx = MARGIN + i * (tile_w + gap)
        doc.draw.rounded_rectangle((tx, doc.y, tx + tile_w, doc.y + 104), radius=14, fill=HEAD_BG)
        doc.text(tx + 18, doc.y + 14, label, 20, False, MUTED)
        doc.text(tx + 18, doc.y + 48, _money(value), 30, True, color)
    doc.y += 128

    # Ledger: one row per invoice, products inside
    if not data["invoices"]:
        doc.text(MARGIN, doc.y, "No invoices or payments in this period.", 24, False, MUTED)
        doc.y += 40
    else:
        doc.header(xs)
        name_font, desc_font, amt_font = _font(21), _font(21, True), _font(21)
        for inv in data["invoices"]:
            lines = inv["lines"] or [{"product": "", "description": "", "amount": None}]
            row_h = len(lines) * LINE_H + 16
            if doc.y + row_h > A4_H - MARGIN - 40:
                doc.new_page()
                doc.header(xs)
            top = doc.y + 8
            doc.text(xs[0] + 14, top, inv["date"], 21, False, INK)
            doc.text(xs[1] + 14, top, inv["invoice_no"], 21, False, INK)
            doc.text(xs[3] + WIDTHS[3] - 14, top, _money(inv["total"]), 21, False, INK, "ra")
            doc.text(xs[4] + WIDTHS[4] - 14, top, _money(inv["received"]) if inv["received"] else "-", 21,
                     False, GREEN if inv["received"] else INK, "ra")
            doc.text(xs[5] + WIDTHS[5] - 14, top, _money(inv["remaining"]), 21, False, INK, "ra")
            _status_pill(doc, xs[6], top, WIDTHS[6], inv["status"])
            for k, line in enumerate(lines):
                ly = doc.y + 8 + k * LINE_H
                px = xs[2] + 14
                if line["product"]:
                    lead = f"{line['product']}  ·  "
                    doc.text(px, ly, lead, 21, False, MUTED)
                    px += name_font.getlength(lead)
                    room = xs[2] + WIDTHS[2] - 130 - px
                    desc = _fit(line["description"], desc_font, room)
                    doc.text(px, ly, desc, 21, True, INK)
                if line["amount"] is not None:
                    doc.text(xs[2] + WIDTHS[2] - 14, ly, _money(line["amount"]), 21, False, SUB, "ra")
            doc.y += row_h
            doc.draw.line((MARGIN, doc.y, A4_W - MARGIN, doc.y), fill=RULE, width=1)

        # Totals row
        total_total = sum(i["total"] for i in data["invoices"])
        total_received = sum(i["received"] for i in data["invoices"])
        total_remaining = sum(i["remaining"] for i in data["invoices"])
        doc.room(60)
        doc.y += 8
        doc.draw.rectangle((MARGIN, doc.y, A4_W - MARGIN, doc.y + 50), fill=HEAD_BG)
        doc.text(MARGIN + 14, doc.y + 13, "Totals", 21, True, INK)
        doc.text(xs[3] + WIDTHS[3] - 14, doc.y + 13, _money(total_total), 21, True, INK, "ra")
        doc.text(xs[4] + WIDTHS[4] - 14, doc.y + 13, _money(total_received), 21, True, GREEN, "ra")
        doc.text(xs[5] + WIDTHS[5] - 14, doc.y + 13, _money(total_remaining), 21, True, AMBER, "ra")
        doc.y += 66

    if data["adjustments"]:
        doc.room(40)
        doc.text(MARGIN, doc.y, "Invoice totals include discount and tax where they were applied.", 20, False, MUTED)

    total = len(doc.pages)
    for i, page in enumerate(doc.pages, start=1):
        d = ImageDraw.Draw(page)
        d.text((A4_W - MARGIN, A4_H - 40), f"{business}  ·  Page {i} of {total}", font=_font(18),
               fill=MUTED, anchor="ra")

    doc.pages[0].save(path, "PDF", resolution=DPI, save_all=True, append_images=doc.pages[1:])
