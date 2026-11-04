"""SQLite data layer. Business rules live here; the ledger is in ledger.py.

Every sale, purchase and payment is posted to the double-entry journal in the
same transaction that saves it, so the books can never drift from the invoices.
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

from .config import BACKUP_DIR, DB_PATH
from .ledger import AR, AP, CAPITAL, DEFAULT_ACCOUNTS, LedgerMixin, today  # noqa: F401
from .security import hash_password, new_token, normalise_answer, token_hash, verify_password

SESSION_DAYS = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL, last_name TEXT,
    business_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
    phone TEXT, address TEXT, currency TEXT NOT NULL,
    password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT,
    email TEXT, business_name TEXT, address TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT,
    email TEXT, business_name TEXT, address TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT UNIQUE, name TEXT NOT NULL,
    category TEXT, unit TEXT DEFAULT 'pcs', cost_price REAL NOT NULL DEFAULT 0,
    sale_price REAL NOT NULL DEFAULT 0, stock REAL NOT NULL DEFAULT 0,
    reorder_level REAL NOT NULL DEFAULT 5, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    customer_name TEXT, customer_phone TEXT,
    subtotal REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL, paid REAL NOT NULL DEFAULT 0, payment_method TEXT,
    note TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL, qty REAL NOT NULL, unit_price REAL NOT NULL, line_total REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    supplier_name TEXT, supplier_phone TEXT,
    subtotal REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL, paid REAL NOT NULL DEFAULT 0, payment_method TEXT,
    note TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT NOT NULL, qty REAL NOT NULL, unit_price REAL NOT NULL, line_total REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, invoice_id INTEGER NOT NULL,
    amount REAL NOT NULL, method TEXT, paid_at TEXT NOT NULL, note TEXT
);
CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, quote_no TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    customer_name TEXT, customer_phone TEXT, items_json TEXT NOT NULL,
    subtotal REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL, valid_until TEXT, status TEXT NOT NULL DEFAULT 'Draft',
    note TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    type TEXT NOT NULL, system INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, entry_date TEXT NOT NULL, ref_type TEXT NOT NULL,
    ref_id INTEGER, ref_no TEXT, memo TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    debit REAL NOT NULL DEFAULT 0, credit REAL NOT NULL DEFAULT 0,
    party_type TEXT, party_id INTEGER, memo TEXT
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(created_at);
CREATE INDEX IF NOT EXISTS idx_jl_account ON journal_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_jl_party ON journal_lines(party_type, party_id);
CREATE INDEX IF NOT EXISTS idx_je_date ON journal_entries(entry_date);
"""

# Columns added after version 2. Existing databases are upgraded in place.
MIGRATIONS = {
    "users": {"security_question": "TEXT", "security_answer_hash": "TEXT"},
    "products": {"description": "TEXT"},
    "sale_items": {"description": "TEXT"},
    "purchase_items": {"description": "TEXT"},
}

DEFAULT_SETTINGS = {
    "invoice_prefix": "INV", "purchase_prefix": "PUR", "quote_prefix": "QUO",
    "default_tax_rate": "0", "low_stock_default": "5", "whatsapp_country_code": "92",
}

PARTY = {"customers": ("customers", "sales", "customer_id"), "suppliers": ("suppliers", "purchases", "supplier_id")}
KIND = {"sale": ("sales", "sale_items", "customer", "INV", "customer_id"),
        "purchase": ("purchases", "purchase_items", "supplier", "PUR", "supplier_id")}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _like(term):
    return f"%{term.strip()}%"


class Database(LedgerMixin):
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        for k, v in DEFAULT_SETTINGS.items():
            self.conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        self.conn.commit()
        self._setup_ledger()
        self._backfill_ledger()

    def _migrate(self):
        for table, cols in MIGRATIONS.items():
            existing = {r["name"] for r in self.query(f"PRAGMA table_info({table})")}
            for col, typ in cols.items():
                if col not in existing:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        self.conn.commit()

    def _backfill_ledger(self):
        """Post invoices created before the ledger existed (runs once)."""
        if self.get_setting("ledger_backfilled") == "1":
            return
        with self.conn:
            for s in self.query("SELECT * FROM sales s WHERE NOT EXISTS (SELECT 1 FROM journal_entries "
                                "WHERE ref_type='sale' AND ref_id=s.id)"):
                cogs = self._cogs(s["id"], "sale")
                net = s["subtotal"] - s["discount"]
                self.post_sale(s["id"], s["invoice_no"], s["created_at"][:10], s["total"], net,
                               s["tax"], cogs, s["customer_id"])
            for p in self.query("SELECT * FROM purchases p WHERE NOT EXISTS (SELECT 1 FROM journal_entries "
                                "WHERE ref_type='purchase' AND ref_id=p.id)"):
                self.post_purchase(p["id"], p["invoice_no"], p["created_at"][:10], p["total"], p["supplier_id"])
            for kind, table, col in (("sale", "sales", "customer_id"), ("purchase", "purchases", "supplier_id")):
                for inv in self.query(f"SELECT * FROM {table} WHERE paid > 0 AND id NOT IN "
                                      f"(SELECT invoice_id FROM payments WHERE kind=?)", (kind,)):
                    self._record_payment_row(kind, inv, inv["paid"], inv["payment_method"], "Opening payment",
                                             update_invoice=False, day=inv["created_at"][:10])
            self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ledger_backfilled', '1')")

    def _cogs(self, sale_id, kind):
        return self.scalar("""SELECT IFNULL(SUM(si.qty * IFNULL(p.cost_price,0)),0)
                              FROM sale_items si LEFT JOIN products p ON p.id = si.product_id
                              WHERE si.sale_id=?""", (sale_id,))

    # ------------------------------------------------------------ helpers
    def query(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def scalar(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return row[0] if row and row[0] is not None else 0

    def get_setting(self, key, default=None):
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key, value):
        with self.conn:
            self.conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def _next_no(self, prefix, table, column="invoice_no"):
        day = datetime.now().strftime("%Y%m%d")
        base = f"{prefix}-{day}-"
        seq = self.scalar(f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?", (base + "%",)) + 1
        while self.one(f"SELECT 1 FROM {table} WHERE {column}=?", (f"{base}{seq:04d}",)):
            seq += 1
        return f"{base}{seq:04d}"

    # ------------------------------------------------------------ accounts & sessions
    def create_user(self, d):
        with self.conn:
            self.conn.execute(
                """INSERT INTO users (first_name, last_name, business_name, email, phone, address, currency,
                   password_hash, security_question, security_answer_hash, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (d["first_name"], d.get("last_name") or None, d["business_name"], d["email"].lower(),
                 d.get("phone") or None, d.get("address") or None, d["currency"],
                 hash_password(d["password"]), d.get("question"),
                 hash_password(normalise_answer(d["answer"])) if d.get("answer") else None, _now()))

    def find_user_by_email(self, email):
        return self.one("SELECT * FROM users WHERE email=?", (email.strip().lower(),))

    def authenticate(self, email, password):
        row = self.find_user_by_email(email)
        if row and verify_password(password, row["password_hash"]):
            return row
        return None

    def get_user(self, user_id):
        return self.one("SELECT * FROM users WHERE id=?", (user_id,))

    def update_profile(self, user_id, d):
        with self.conn:
            self.conn.execute(
                """UPDATE users SET first_name=?, last_name=?, business_name=?, phone=?, address=?, currency=?
                   WHERE id=?""",
                (d["first_name"], d.get("last_name") or None, d["business_name"], d.get("phone") or None,
                 d.get("address") or None, d["currency"], user_id))

    def change_password(self, user_id, new_secret):
        with self.conn:
            self.conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_secret), user_id))

    def verify_recovery_answer(self, user_id, answer):
        row = self.get_user(user_id)
        return bool(row and row["security_answer_hash"] and
                    verify_password(normalise_answer(answer), row["security_answer_hash"]))

    def set_recovery(self, user_id, question, answer):
        with self.conn:
            self.conn.execute("UPDATE users SET security_question=?, security_answer_hash=? WHERE id=?",
                              (question, hash_password(normalise_answer(answer)), user_id))

    def reset_pin(self, user_id, new_pin):
        """Used by 'Forgot password'. Also signs out every existing session."""
        with self.conn:
            self.conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_pin), user_id))
            self.conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

    def create_session(self, user_id):
        token = new_token()
        expires = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                              (token_hash(token), user_id, _now(), expires))
        return token

    def session_user(self, token):
        if not token:
            return None
        row = self.one("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                          WHERE s.token_hash=? AND s.expires_at > ?""", (token_hash(token), _now()))
        return row

    def end_session(self, token):
        if token:
            with self.conn:
                self.conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))

    # ------------------------------------------------------------ contacts
    def contacts(self, table, term=""):
        return self.query(
            f"""SELECT id, name, phone, email, business_name, address FROM {table}
                WHERE name LIKE ? OR IFNULL(phone,'') LIKE ? OR IFNULL(business_name,'') LIKE ?
                ORDER BY name""", (_like(term),) * 3)

    def contact_options(self, table, term="", limit=25):
        rows = self.query(
            f"""SELECT id, name, phone FROM {table} WHERE name LIKE ? OR IFNULL(phone,'') LIKE ?
                ORDER BY name LIMIT ?""", (_like(term), _like(term), limit))
        return [((f"{r['name']}  ·  {r['phone']}" if r["phone"] else r["name"]), r) for r in rows]

    def add_contact(self, table, d):
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO {table} (name, phone, email, business_name, address, created_at) VALUES (?,?,?,?,?,?)",
                (d["name"], d.get("phone") or None, d.get("email") or None, d.get("business_name") or None,
                 d.get("address") or None, _now()))
        return cur.lastrowid

    def update_contact(self, table, cid, d):
        with self.conn:
            self.conn.execute(
                f"UPDATE {table} SET name=?, phone=?, email=?, business_name=?, address=? WHERE id=?",
                (d["name"], d.get("phone") or None, d.get("email") or None, d.get("business_name") or None,
                 d.get("address") or None, cid))

    def upsert_contact(self, table, d):
        row = self.one(f"SELECT id FROM {table} WHERE name=? AND IFNULL(phone,'')=?",
                       (d["name"], d.get("phone") or ""))
        return row["id"] if row else self.add_contact(table, d)

    def delete_contacts(self, table, ids):
        with self.conn:
            self.conn.executemany(f"DELETE FROM {table} WHERE id=?", [(i,) for i in ids])

    def contact_balances(self, table):
        _, inv, col = PARTY[table]
        rows = self.query(f"""SELECT {col} AS pid, SUM(total - paid) AS due FROM {inv}
                              WHERE {col} IS NOT NULL GROUP BY {col}""")
        return {r["pid"]: r["due"] or 0 for r in rows}

    # ------------------------------------------------------------ products
    def products(self, term="", low_only=False):
        return self.query(
            """SELECT * FROM products WHERE (name LIKE ? OR IFNULL(sku,'') LIKE ? OR IFNULL(category,'') LIKE ?)
               AND (? = 0 OR stock <= reorder_level) ORDER BY stock <= reorder_level DESC, name""",
            (_like(term), _like(term), _like(term), 1 if low_only else 0))

    def product_options(self, term="", limit=30):
        rows = self.query("""SELECT * FROM products WHERE name LIKE ? OR IFNULL(sku,'') LIKE ?
                             ORDER BY name LIMIT ?""", (_like(term), _like(term), limit))
        return [(f"{r['name']}  (stock {r['stock']:g})", r) for r in rows]

    def add_product(self, d):
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO products (sku, name, category, unit, cost_price, sale_price, stock,
                   reorder_level, description, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (d.get("sku") or None, d["name"], d.get("category") or None, d.get("unit") or "pcs",
                 d["cost_price"], d["sale_price"], d["stock"], d["reorder_level"],
                 d.get("description") or None, _now()))
        return cur.lastrowid

    def update_product(self, pid, d):
        with self.conn:
            self.conn.execute(
                """UPDATE products SET sku=?, name=?, category=?, unit=?, cost_price=?, sale_price=?,
                   stock=?, reorder_level=?, description=? WHERE id=?""",
                (d.get("sku") or None, d["name"], d.get("category") or None, d.get("unit") or "pcs",
                 d["cost_price"], d["sale_price"], d["stock"], d["reorder_level"],
                 d.get("description") or None, pid))

    def delete_products(self, ids):
        with self.conn:
            self.conn.executemany("DELETE FROM products WHERE id=?", [(i,) for i in ids])

    def adjust_stock(self, ids, delta):
        with self.conn:
            self.conn.executemany("UPDATE products SET stock = stock + ? WHERE id=?", [(delta, i) for i in ids])

    def _product_for_line(self, name, price, kind, description=None):
        row = self.one("SELECT id FROM products WHERE name=? COLLATE NOCASE", (name,))
        if row:
            return row["id"]
        cost, sale = (price, 0) if kind == "purchase" else (0, price)
        cur = self.conn.execute(
            """INSERT INTO products (name, cost_price, sale_price, stock, reorder_level, description, created_at)
               VALUES (?,?,?,0,?,?,?)""",
            (name, cost, sale, float(self.get_setting("low_stock_default", 5)), description or None, _now()))
        return cur.lastrowid

    # ------------------------------------------------------------ invoices
    @staticmethod
    def _totals(items, discount, tax_rate):
        subtotal = sum(i["qty"] * i["price"] for i in items)
        discount = min(max(discount, 0), subtotal)
        tax = round((subtotal - discount) * tax_rate / 100, 2)
        return subtotal, discount, tax, round(subtotal - discount + tax, 2)

    def save_invoice(self, kind, items, party_id=None, party_name=None, party_phone=None,
                     discount=0.0, tax_rate=0.0, paid=None, method="Cash", note="", entry_date=None):
        """Save a sale or purchase atomically: header, lines, stock, journal and payment.

        entry_date (YYYY-MM-DD) is the date of the transaction. It defaults to today
        and drives the invoice date, the ledger date and every report.
        """
        day = entry_date or today()
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date '{day}'. Use YYYY-MM-DD.")
        stamp = f"{day}T{datetime.now():%H:%M:%S}"
        table, item_table, _, default_prefix, party_col = KIND[kind]
        prefix = self.get_setting("invoice_prefix" if kind == "sale" else "purchase_prefix", default_prefix)
        subtotal, discount, tax, total = self._totals(items, discount, tax_rate)
        if method == "Credit":
            paid = 0
        paid = total if paid is None else min(max(paid, 0), total)
        name_col = "customer_name" if kind == "sale" else "supplier_name"
        phone_col = "customer_phone" if kind == "sale" else "supplier_phone"
        with self.conn:
            inv_no = self._next_no(prefix, table)
            cur = self.conn.execute(
                f"""INSERT INTO {table} (invoice_no, {party_col}, {name_col}, {phone_col}, subtotal, discount,
                    tax, total, paid, payment_method, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (inv_no, party_id, party_name or None, party_phone or None, subtotal, discount, tax, total,
                 0, method, note or None, stamp))
            head_id = cur.lastrowid
            cogs = 0.0
            for i in items:
                pid = i.get("product_id") or self._product_for_line(i["name"], i["price"], kind, i.get("desc"))
                self.conn.execute(
                    f"""INSERT INTO {item_table} ({table[:-1]}_id, product_id, product_name, qty, unit_price,
                        line_total, description) VALUES (?,?,?,?,?,?,?)""",
                    (head_id, pid, i["name"], i["qty"], i["price"], i["qty"] * i["price"], i.get("desc") or None))
                delta = -i["qty"] if kind == "sale" else i["qty"]
                self.conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (delta, pid))
                if kind == "sale":
                    cogs += i["qty"] * self.scalar("SELECT cost_price FROM products WHERE id=?", (pid,))
            if kind == "sale":
                self.post_sale(head_id, inv_no, day, total, subtotal - discount, tax, round(cogs, 2), party_id)
            else:
                self.post_purchase(head_id, inv_no, day, total, party_id)
            if paid > 0:
                self._record_payment_row(kind, {"id": head_id, "invoice_no": inv_no, "customer_id": party_id,
                                                "supplier_id": party_id}, paid, method, "", day=day)
        return inv_no

    def _record_payment_row(self, kind, inv, amount, method, note, update_invoice=True, day=None):
        """Insert a payment, update the invoice and post it. Caller holds the transaction.

        day is the date the money changed hands (defaults to today). It is used for
        both the payment record and the ledger posting, so statements match.
        """
        day = day or today()
        table = KIND[kind][0]
        party_id = inv.get(KIND[kind][4])
        method = method if method and method != "Credit" else "Cash"
        cur = self.conn.execute("INSERT INTO payments (kind, invoice_id, amount, method, paid_at, note) VALUES (?,?,?,?,?,?)",
                                (kind, inv["id"], amount, method, f"{day}T{datetime.now():%H:%M:%S}", note or None))
        pid = cur.lastrowid
        if update_invoice:
            self.conn.execute(f"UPDATE {table} SET paid = MIN(total, paid + ?) WHERE id=?", (amount, inv["id"]))
        self.post_payment(kind, pid, inv["invoice_no"], day, amount, method, party_id)
        return pid

    def record_payment(self, kind, inv_id, amount, method=None, note=""):
        table = KIND[kind][0]
        head = self.one(f"SELECT * FROM {table} WHERE id=?", (inv_id,))
        if not head:
            raise ValueError("Invoice not found")
        due = round(head["total"] - head["paid"], 2)
        if due <= 0.005:
            raise ValueError("This invoice is already fully paid")
        amount = min(amount, due)
        with self.conn:
            self._record_payment_row(kind, head, amount, method or head["payment_method"], note)
        return amount

    def payments(self, kind, inv_id):
        return self.query("SELECT * FROM payments WHERE kind=? AND invoice_id=? ORDER BY id", (kind, inv_id))

    def invoices(self, kind, date_from=None, date_to=None, term="", limit=500):
        table = KIND[kind][0]
        name_col = "customer_name" if kind == "sale" else "supplier_name"
        rows = self.query(
            f"""SELECT i.id, i.invoice_no, i.{name_col} AS party, i.total, i.paid, i.payment_method, i.created_at,
                       (SELECT COUNT(*) FROM {KIND[kind][1]} it WHERE it.{table[:-1]}_id = i.id) AS item_count
                FROM {table} i
                WHERE (? IS NULL OR date(i.created_at) >= ?) AND (? IS NULL OR date(i.created_at) <= ?)
                  AND (i.invoice_no LIKE ? OR IFNULL(i.{name_col},'') LIKE ?)
                ORDER BY i.created_at DESC, i.id DESC LIMIT ?""",
            (date_from, date_from, date_to, date_to, _like(term), _like(term), limit))
        for r in rows:
            r["due"] = round(r["total"] - r["paid"], 2)
            r["status"] = "Paid" if r["due"] <= 0.005 else ("Partial" if r["paid"] > 0 else "Unpaid")
        return rows

    def invoice_lines(self, kind, date_from=None, date_to=None, term=""):
        """One row per product line of every saved invoice (newest first)."""
        table, item_table, _, _, _ = KIND[kind]
        name_col = "customer_name" if kind == "sale" else "supplier_name"
        return self.query(
            f"""SELECT it.id AS line_id, h.id AS invoice_id, h.invoice_no, h.{name_col} AS party,
                       h.created_at, it.product_name, it.description, it.qty, it.unit_price, it.line_total
                FROM {item_table} it JOIN {table} h ON h.id = it.{table[:-1]}_id
                WHERE (? IS NULL OR date(h.created_at) >= ?) AND (? IS NULL OR date(h.created_at) <= ?)
                  AND (h.invoice_no LIKE ? OR IFNULL(h.{name_col},'') LIKE ? OR it.product_name LIKE ?)
                ORDER BY h.created_at DESC, it.id""",
            (date_from, date_from, date_to, date_to, _like(term), _like(term), _like(term)))

    def invoice_detail(self, kind, inv_id):
        table, item_table = KIND[kind][0], KIND[kind][1]
        head = self.one(f"SELECT * FROM {table} WHERE id=?", (inv_id,))
        if head:
            head["items"] = self.query(f"SELECT * FROM {item_table} WHERE {table[:-1]}_id=? ORDER BY id", (inv_id,))
        return head

    def delete_invoice(self, kind, inv_id):
        """Delete an invoice, reverse its stock and remove its journal entries."""
        table, item_table = KIND[kind][0], KIND[kind][1]
        with self.conn:
            for it in self.query(f"SELECT product_id, qty FROM {item_table} WHERE {table[:-1]}_id=?", (inv_id,)):
                if it["product_id"]:
                    delta = it["qty"] if kind == "sale" else -it["qty"]
                    self.conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (delta, it["product_id"]))
            for p in self.query("SELECT id FROM payments WHERE kind=? AND invoice_id=?", (kind, inv_id)):
                self._unpost(f"{kind}_payment", p["id"])
            self.conn.execute("DELETE FROM payments WHERE kind=? AND invoice_id=?", (kind, inv_id))
            self._unpost(kind, inv_id)
            self.conn.execute(f"DELETE FROM {table} WHERE id=?", (inv_id,))

    # ------------------------------------------------------------ quotations
    def save_quotation(self, items, customer_id, customer_name, customer_phone, valid_until,
                       discount=0.0, tax_rate=0.0, note=""):
        subtotal, discount, tax, total = self._totals(items, discount, tax_rate)
        with self.conn:
            qno = self._next_no(self.get_setting("quote_prefix", "QUO"), "quotations", "quote_no")
            self.conn.execute(
                """INSERT INTO quotations (quote_no, customer_id, customer_name, customer_phone, items_json,
                   subtotal, discount, tax, total, valid_until, status, note, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,'Draft',?,?)""",
                (qno, customer_id, customer_name or None, customer_phone or None, json.dumps(items), subtotal,
                 discount, tax, total, valid_until or None, note or None, _now()))
        return qno

    def quotations(self, term=""):
        return self.query("""SELECT * FROM quotations WHERE quote_no LIKE ? OR IFNULL(customer_name,'') LIKE ?
                             ORDER BY id DESC LIMIT 300""", (_like(term), _like(term)))

    def set_quotation_status(self, qid, status):
        with self.conn:
            self.conn.execute("UPDATE quotations SET status=? WHERE id=?", (status, qid))

    # ------------------------------------------------------------ dashboard & backup
    def dashboard(self):
        day = today()
        return {
            "today_sales": self.scalar("SELECT SUM(total) FROM sales WHERE date(created_at)=?", (day,)),
            "today_purchases": self.scalar("SELECT SUM(total) FROM purchases WHERE date(created_at)=?", (day,)),
            "receivable": self.scalar("SELECT SUM(total-paid) FROM sales"),
            "payable": self.scalar("SELECT SUM(total-paid) FROM purchases"),
            "stock_value": self.scalar("SELECT SUM(stock*cost_price) FROM products WHERE stock>0"),
            "low_count": self.scalar("SELECT COUNT(*) FROM products WHERE stock <= reorder_level"),
            "customers": self.scalar("SELECT COUNT(*) FROM customers"),
            "products": self.scalar("SELECT COUNT(*) FROM products"),
        }

    def sales_by_day(self, days=7):
        start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        found = {r["d"]: r["t"] for r in self.query(
            "SELECT date(created_at) d, SUM(total) t FROM sales WHERE date(created_at) >= ? GROUP BY d", (start,))}
        out = []
        for n in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - n)).strftime("%Y-%m-%d")
            out.append((d[5:], found.get(d, 0) or 0))
        return out

    def backup(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        dest = os.path.join(BACKUP_DIR, f"fst_backup_{datetime.now():%Y%m%d_%H%M%S}.db")
        target = sqlite3.connect(dest)
        try:
            self.conn.backup(target)
        finally:
            target.close()
        return dest
