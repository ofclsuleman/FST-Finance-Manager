"""SQLite data layer. All business rules (totals, stock, balances) live here."""
import os
import shutil
import sqlite3
from datetime import datetime, timedelta

from .config import BACKUP_DIR, DB_PATH
from .security import hash_password, verify_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL, last_name TEXT,
    business_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
    phone TEXT, address TEXT, currency TEXT NOT NULL,
    password_hash TEXT NOT NULL, created_at TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS quotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, quote_no TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    customer_name TEXT, customer_phone TEXT, items_json TEXT NOT NULL,
    subtotal REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, tax REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL, valid_until TEXT, status TEXT NOT NULL DEFAULT 'Draft',
    note TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(created_at);
CREATE INDEX IF NOT EXISTS idx_sales_cust ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_purch_supp ON purchases(supplier_id);
"""

DEFAULT_SETTINGS = {
    "invoice_prefix": "INV", "purchase_prefix": "PUR", "quote_prefix": "QUO",
    "default_tax_rate": "0", "low_stock_default": "5",
}

# Table names are fixed in code (never user input), so f-strings below are safe.
PARTY = {
    "customers": ("customers", "sales", "sale_items", "customer_id"),
    "suppliers": ("suppliers", "purchases", "purchase_items", "supplier_id"),
}
KIND = {
    "sale": ("sales", "sale_items", "customer", "INV"),
    "purchase": ("purchases", "purchase_items", "supplier", "PUR"),
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _like(term):
    return f"%{term.strip()}%"


class Database:
    def __init__(self, path=DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            self.conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        self.conn.commit()

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

    # ------------------------------------------------------------ accounts
    def create_user(self, d):
        with self.conn:
            self.conn.execute(
                """INSERT INTO users (first_name, last_name, business_name, email, phone, address,
                   currency, password_hash, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (d["first_name"], d.get("last_name") or None, d["business_name"],
                 d["email"].lower(), d.get("phone") or None, d.get("address") or None,
                 d["currency"], hash_password(d["password"]), _now()))

    def authenticate(self, email, password):
        row = self.one("SELECT * FROM users WHERE email=?", (email.strip().lower(),))
        if row and verify_password(password, row["password_hash"]):
            return row
        return None

    def get_user(self, user_id):
        return self.one("SELECT * FROM users WHERE id=?", (user_id,))

    def update_profile(self, user_id, d):
        with self.conn:
            self.conn.execute(
                """UPDATE users SET first_name=?, last_name=?, business_name=?, phone=?,
                   address=?, currency=? WHERE id=?""",
                (d["first_name"], d.get("last_name") or None, d["business_name"],
                 d.get("phone") or None, d.get("address") or None, d["currency"], user_id))

    def change_password(self, user_id, new_password):
        with self.conn:
            self.conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                              (hash_password(new_password), user_id))

    # ------------------------------------------------------------ contacts
    def contacts(self, table, term=""):
        return self.query(
            f"""SELECT id, name, phone, email, business_name, address FROM {table}
                WHERE name LIKE ? OR IFNULL(phone,'') LIKE ? OR IFNULL(business_name,'') LIKE ?
                ORDER BY name""", (_like(term),) * 3)

    def contact_options(self, table, term="", limit=25):
        """(label, value) pairs for the type-to-search pickers."""
        rows = self.query(
            f"""SELECT id, name, phone FROM {table} WHERE name LIKE ? OR IFNULL(phone,'') LIKE ?
                ORDER BY name LIMIT ?""", (_like(term), _like(term), limit))
        return [((f"{r['name']}  ·  {r['phone']}" if r["phone"] else r["name"]), r) for r in rows]

    def add_contact(self, table, d):
        with self.conn:
            cur = self.conn.execute(
                f"INSERT INTO {table} (name, phone, email, business_name, address, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (d["name"], d.get("phone") or None, d.get("email") or None,
                 d.get("business_name") or None, d.get("address") or None, _now()))
        return cur.lastrowid

    def update_contact(self, table, cid, d):
        with self.conn:
            self.conn.execute(
                f"UPDATE {table} SET name=?, phone=?, email=?, business_name=?, address=? WHERE id=?",
                (d["name"], d.get("phone") or None, d.get("email") or None,
                 d.get("business_name") or None, d.get("address") or None, cid))

    def upsert_contact(self, table, d):
        """Return the id of an existing contact with the same name and phone, or create one."""
        row = self.one(f"SELECT id FROM {table} WHERE name=? AND IFNULL(phone,'')=?",
                       (d["name"], d.get("phone") or ""))
        return row["id"] if row else self.add_contact(table, d)

    def delete_contacts(self, table, ids):
        with self.conn:
            self.conn.executemany(f"DELETE FROM {table} WHERE id=?", [(i,) for i in ids])

    def contact_balances(self, table):
        """id -> outstanding amount (receivable for customers, payable for suppliers)."""
        party, inv, _, col = PARTY[table]
        rows = self.query(f"""SELECT {col} AS pid, SUM(total - paid) AS due FROM {inv}
                              WHERE {col} IS NOT NULL GROUP BY {col}""")
        return {r["pid"]: r["due"] or 0 for r in rows}

    # ------------------------------------------------------------ products
    def products(self, term="", low_only=False):
        return self.query(
            """SELECT * FROM products WHERE (name LIKE ? OR IFNULL(sku,'') LIKE ?
               OR IFNULL(category,'') LIKE ?) AND (? = 0 OR stock <= reorder_level)
               ORDER BY stock <= reorder_level DESC, name""",
            (_like(term), _like(term), _like(term), 1 if low_only else 0))

    def product_options(self, term="", limit=30):
        rows = self.query("""SELECT * FROM products WHERE name LIKE ? OR IFNULL(sku,'') LIKE ?
                             ORDER BY name LIMIT ?""", (_like(term), _like(term), limit))
        return [(f"{r['name']}  (stock {r['stock']:g})", r) for r in rows]

    def add_product(self, d):
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO products (sku, name, category, unit, cost_price, sale_price,
                   stock, reorder_level, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (d.get("sku") or None, d["name"], d.get("category") or None, d.get("unit") or "pcs",
                 d["cost_price"], d["sale_price"], d["stock"], d["reorder_level"], _now()))
        return cur.lastrowid

    def update_product(self, pid, d):
        with self.conn:
            self.conn.execute(
                """UPDATE products SET sku=?, name=?, category=?, unit=?, cost_price=?,
                   sale_price=?, stock=?, reorder_level=? WHERE id=?""",
                (d.get("sku") or None, d["name"], d.get("category") or None, d.get("unit") or "pcs",
                 d["cost_price"], d["sale_price"], d["stock"], d["reorder_level"], pid))

    def delete_products(self, ids):
        with self.conn:
            self.conn.executemany("DELETE FROM products WHERE id=?", [(i,) for i in ids])

    def adjust_stock(self, ids, delta):
        with self.conn:
            self.conn.executemany("UPDATE products SET stock = stock + ? WHERE id=?",
                                  [(delta, i) for i in ids])

    def _product_for_line(self, name, price, kind):
        """Find a product by name, or create it (zero stock) so typed items are never lost."""
        row = self.one("SELECT id FROM products WHERE name=? COLLATE NOCASE", (name,))
        if row:
            return row["id"]
        cost, sale = (price, 0) if kind == "purchase" else (0, price)
        cur = self.conn.execute(
            """INSERT INTO products (name, cost_price, sale_price, stock, reorder_level, created_at)
               VALUES (?,?,?,0,?,?)""",
            (name, cost, sale, float(self.get_setting("low_stock_default", 5)), _now()))
        return cur.lastrowid

    # ------------------------------------------------------------ invoices
    @staticmethod
    def _totals(items, discount, tax_rate):
        subtotal = sum(i["qty"] * i["price"] for i in items)
        discount = min(max(discount, 0), subtotal)
        tax = (subtotal - discount) * tax_rate / 100
        return subtotal, discount, round(tax, 2), round(subtotal - discount + tax, 2)

    def save_invoice(self, kind, items, party_id=None, party_name=None, party_phone=None,
                     discount=0.0, tax_rate=0.0, paid=None, method="Cash", note=""):
        """Save a sale or purchase atomically: header, lines, stock and payment."""
        table, item_table, _, default_prefix = KIND[kind]
        prefix = self.get_setting("invoice_prefix" if kind == "sale" else "purchase_prefix",
                                  default_prefix)
        subtotal, discount, tax, total = self._totals(items, discount, tax_rate)
        paid = total if paid is None else min(max(paid, 0), total)
        party_col = "customer_id" if kind == "sale" else "supplier_id"
        name_col = "customer_name" if kind == "sale" else "supplier_name"
        phone_col = "customer_phone" if kind == "sale" else "supplier_phone"
        with self.conn:
            inv_no = self._next_no(prefix, table)
            cur = self.conn.execute(
                f"""INSERT INTO {table} (invoice_no, {party_col}, {name_col}, {phone_col},
                    subtotal, discount, tax, total, paid, payment_method, note, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (inv_no, party_id, party_name or None, party_phone or None, subtotal, discount,
                 tax, total, paid, method, note or None, _now()))
            head_id = cur.lastrowid
            for i in items:
                pid = i.get("product_id") or self._product_for_line(i["name"], i["price"], kind)
                self.conn.execute(
                    f"""INSERT INTO {item_table} ({table[:-1]}_id, product_id, product_name, qty,
                        unit_price, line_total) VALUES (?,?,?,?,?,?)""",
                    (head_id, pid, i["name"], i["qty"], i["price"], i["qty"] * i["price"]))
                delta = -i["qty"] if kind == "sale" else i["qty"]
                self.conn.execute("UPDATE products SET stock = stock + ? WHERE id=?", (delta, pid))
        return inv_no

    def invoices(self, kind, date_from=None, date_to=None, term=""):
        table = KIND[kind][0]
        name_col = "customer_name" if kind == "sale" else "supplier_name"
        rows = self.query(
            f"""SELECT id, invoice_no, {name_col} AS party, total, paid, payment_method, created_at
                FROM {table}
                WHERE (? IS NULL OR date(created_at) >= ?) AND (? IS NULL OR date(created_at) <= ?)
                  AND (invoice_no LIKE ? OR IFNULL({name_col},'') LIKE ?)
                ORDER BY id DESC LIMIT 500""",
            (date_from, date_from, date_to, date_to, _like(term), _like(term)))
        for r in rows:
            r["due"] = round(r["total"] - r["paid"], 2)
            r["status"] = ("Paid" if r["due"] <= 0.005 else
                           "Partial" if r["paid"] > 0 else "Unpaid")
        return rows

    def invoice_detail(self, kind, inv_id):
        table, item_table = KIND[kind][0], KIND[kind][1]
        head = self.one(f"SELECT * FROM {table} WHERE id=?", (inv_id,))
        if head:
            head["items"] = self.query(
                f"SELECT * FROM {item_table} WHERE {table[:-1]}_id=? ORDER BY id", (inv_id,))
        return head

    def record_payment(self, kind, inv_id, amount):
        table = KIND[kind][0]
        with self.conn:
            self.conn.execute(f"UPDATE {table} SET paid = MIN(total, paid + ?) WHERE id=?",
                              (amount, inv_id))

    def delete_invoice(self, kind, inv_id):
        """Delete an invoice and reverse its stock movement."""
        table, item_table = KIND[kind][0], KIND[kind][1]
        with self.conn:
            for it in self.query(f"SELECT product_id, qty FROM {item_table} WHERE {table[:-1]}_id=?",
                                 (inv_id,)):
                if it["product_id"]:
                    delta = it["qty"] if kind == "sale" else -it["qty"]
                    self.conn.execute("UPDATE products SET stock = stock + ? WHERE id=?",
                                      (delta, it["product_id"]))
            self.conn.execute(f"DELETE FROM {table} WHERE id=?", (inv_id,))

    # ------------------------------------------------------------ quotations
    def save_quotation(self, items, customer_id, customer_name, customer_phone,
                       valid_until, discount=0.0, tax_rate=0.0, note=""):
        subtotal, discount, tax, total = self._totals(items, discount, tax_rate)
        import json
        with self.conn:
            qno = self._next_no(self.get_setting("quote_prefix", "QUO"), "quotations", "quote_no")
            self.conn.execute(
                """INSERT INTO quotations (quote_no, customer_id, customer_name, customer_phone,
                   items_json, subtotal, discount, tax, total, valid_until, status, note, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,'Draft',?,?)""",
                (qno, customer_id, customer_name or None, customer_phone or None,
                 json.dumps(items), subtotal, discount, tax, total, valid_until or None,
                 note or None, _now()))
        return qno

    def quotations(self, term=""):
        return self.query("""SELECT * FROM quotations WHERE quote_no LIKE ?
                             OR IFNULL(customer_name,'') LIKE ? ORDER BY id DESC LIMIT 300""",
                          (_like(term), _like(term)))

    def set_quotation_status(self, qid, status):
        with self.conn:
            self.conn.execute("UPDATE quotations SET status=? WHERE id=?", (status, qid))

    # ------------------------------------------------------------ dashboard & reports
    def dashboard(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "today_sales": self.scalar("SELECT SUM(total) FROM sales WHERE date(created_at)=?", (today,)),
            "today_purchases": self.scalar("SELECT SUM(total) FROM purchases WHERE date(created_at)=?", (today,)),
            "receivable": self.scalar("SELECT SUM(total-paid) FROM sales"),
            "payable": self.scalar("SELECT SUM(total-paid) FROM purchases"),
            "stock_value": self.scalar("SELECT SUM(stock*cost_price) FROM products WHERE stock>0"),
            "low_count": self.scalar("SELECT COUNT(*) FROM products WHERE stock <= reorder_level"),
            "customers": self.scalar("SELECT COUNT(*) FROM customers"),
            "products": self.scalar("SELECT COUNT(*) FROM products"),
        }

    def sales_by_day(self, days=7):
        start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        rows = self.query("""SELECT date(created_at) d, SUM(total) t FROM sales
                             WHERE date(created_at) >= ? GROUP BY d""", (start,))
        found = {r["d"]: r["t"] for r in rows}
        out = []
        for n in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - n)).strftime("%Y-%m-%d")
            out.append((d[5:], found.get(d, 0) or 0))
        return out

    def report(self, date_from, date_to):
        rng = ("date(created_at) BETWEEN ? AND ?", (date_from, date_to))
        sales = self.one(f"SELECT COUNT(*) n, SUM(total) t, SUM(paid) p, SUM(tax) x FROM sales WHERE {rng[0]}", rng[1])
        purchases = self.one(f"SELECT COUNT(*) n, SUM(total) t, SUM(paid) p FROM purchases WHERE {rng[0]}", rng[1])
        cost = self.scalar(f"""SELECT SUM(si.qty * IFNULL(p.cost_price,0)) FROM sale_items si
                               JOIN sales s ON s.id = si.sale_id
                               LEFT JOIN products p ON p.id = si.product_id
                               WHERE date(s.created_at) BETWEEN ? AND ?""", rng[1])
        top = self.query(f"""SELECT si.product_name name, SUM(si.qty) qty, SUM(si.line_total) revenue
                             FROM sale_items si JOIN sales s ON s.id = si.sale_id
                             WHERE date(s.created_at) BETWEEN ? AND ?
                             GROUP BY si.product_name ORDER BY revenue DESC LIMIT 10""", rng[1])
        revenue = (sales["t"] or 0) - (sales["x"] or 0)
        return {
            "sales_count": sales["n"] or 0, "sales_total": sales["t"] or 0,
            "tax_collected": sales["x"] or 0, "collected": sales["p"] or 0,
            "outstanding": (sales["t"] or 0) - (sales["p"] or 0),
            "purchase_count": purchases["n"] or 0, "purchases_total": purchases["t"] or 0,
            "paid_to_suppliers": purchases["p"] or 0,
            "gross_profit": revenue - cost, "top_products": top,
        }

    # ------------------------------------------------------------ backup
    def backup(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        dest = os.path.join(BACKUP_DIR, f"fst_backup_{datetime.now():%Y%m%d_%H%M%S}.db")
        target = sqlite3.connect(dest)
        try:
            self.conn.backup(target)
        finally:
            target.close()
        return dest
