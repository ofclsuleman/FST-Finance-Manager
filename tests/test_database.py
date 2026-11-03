"""Business-logic tests. They run without a display (no Tkinter needed).

Run from the project folder:  python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fstapp import database as dbmod  # noqa: E402
from fstapp.database import Database  # noqa: E402


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        dbmod.BACKUP_DIR = os.path.join(self.tmp, "backups")
        self.db = Database(os.path.join(self.tmp, "t.db"))
        self.db.create_user({"first_name": "Ali", "last_name": "", "business_name": "Test Co",
                             "email": "ali@x.com", "phone": "", "currency": "PKR", "password": "secret1"})

    def tearDown(self):
        self.db.conn.close()

    def add_product(self, name="Widget", stock=10, reorder=5, cost=60, sale=100):
        return self.db.add_product({"name": name, "sku": None, "category": "", "unit": "pcs",
                                    "cost_price": cost, "sale_price": sale, "stock": stock,
                                    "reorder_level": reorder})

    def stock_of(self, pid):
        return self.db.one("SELECT stock FROM products WHERE id=?", (pid,))["stock"]

    # ---- accounts
    def test_login_and_wrong_password(self):
        self.assertEqual(self.db.authenticate("ALI@x.com", "secret1")["business_name"], "Test Co")
        self.assertIsNone(self.db.authenticate("ali@x.com", "wrong"))

    # ---- the "saved customer not showing in invoice" bug
    def test_saved_customer_appears_in_picker(self):
        cid = self.db.add_contact("customers", {"name": "Bilal Traders", "phone": "0301"})
        labels = [label for label, _ in self.db.contact_options("customers", "Bil")]
        self.assertEqual(len(labels), 1)
        self.assertIn("Bilal Traders", labels[0])
        values = [v for _, v in self.db.contact_options("customers", "")]
        self.assertIn(cid, [v["id"] for v in values])

    def test_invoice_links_to_saved_customer(self):
        pid = self.add_product()
        cid = self.db.add_contact("customers", {"name": "Bilal", "phone": "0301"})
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 2, "price": 100}],
                                   party_id=cid, party_name="Bilal", party_phone="0301")
        head = self.db.invoice_detail("sale", self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"])
        self.assertEqual(head["customer_id"], cid)
        self.assertEqual(head["total"], 200)

    def test_unlinked_invoice_is_allowed(self):
        pid = self.add_product()
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 100}])
        head = self.db.one("SELECT * FROM sales WHERE invoice_no=?", (inv,))
        self.assertIsNone(head["customer_id"])
        self.assertEqual(head["paid"], head["total"])

    def test_upsert_contact_is_idempotent(self):
        a = self.db.upsert_contact("suppliers", {"name": "Star Supply", "phone": "021"})
        b = self.db.upsert_contact("suppliers", {"name": "Star Supply", "phone": "021"})
        self.assertEqual(a, b)

    # ---- totals, tax, payments, balances
    def test_discount_tax_and_partial_payment(self):
        pid = self.add_product()
        cid = self.db.add_contact("customers", {"name": "Sara"})
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 3, "price": 100}],
                                   party_id=cid, party_name="Sara", discount=50, tax_rate=10, paid=100)
        row = self.db.one("SELECT * FROM sales WHERE invoice_no=?", (inv,))
        self.assertEqual(row["subtotal"], 300)
        self.assertEqual(row["tax"], 25)          # (300 - 50) * 10%
        self.assertEqual(row["total"], 275)
        self.assertEqual(row["paid"], 100)
        self.assertEqual(self.db.contact_balances("customers")[cid], 175)
        status = [r["status"] for r in self.db.invoices("sale") if r["invoice_no"] == inv][0]
        self.assertEqual(status, "Partial")

    def test_record_payment_clears_balance(self):
        pid = self.add_product()
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 100}], paid=0)
        sale_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        self.db.record_payment("sale", sale_id, 40)
        self.db.record_payment("sale", sale_id, 1000)  # capped at the total
        row = self.db.one("SELECT paid, total FROM sales WHERE id=?", (sale_id,))
        self.assertEqual(row["paid"], row["total"])
        self.assertEqual([r["status"] for r in self.db.invoices("sale") if r["id"] == sale_id], ["Paid"])

    # ---- stock rules
    def test_sale_reduces_stock_and_zero_stock_sale_is_allowed(self):
        pid = self.add_product(stock=2)
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 5, "price": 100}])
        self.assertEqual(self.stock_of(pid), -3)   # sold without an error

    def test_purchase_increases_stock(self):
        pid = self.add_product(stock=0)
        sid = self.db.add_contact("suppliers", {"name": "Star Supply"})
        self.db.save_invoice("purchase", [{"product_id": pid, "name": "Widget", "qty": 10, "price": 60}],
                             party_id=sid, party_name="Star Supply", paid=0)
        self.assertEqual(self.stock_of(pid), 10)
        self.assertEqual(self.db.contact_balances("suppliers")[sid], 600)

    def test_delete_invoice_restores_stock(self):
        pid = self.add_product(stock=10)
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 4, "price": 100}])
        sale_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        self.db.delete_invoice("sale", sale_id)
        self.assertEqual(self.stock_of(pid), 10)
        self.assertEqual(self.db.invoices("sale"), [])

    def test_unknown_product_is_created_on_sale(self):
        self.db.save_invoice("sale", [{"product_id": None, "name": "New Item", "qty": 1, "price": 250}])
        row = self.db.one("SELECT name, sale_price, stock FROM products WHERE name='New Item'")
        self.assertEqual((row["sale_price"], row["stock"]), (250, -1))

    def test_low_stock_filter(self):
        self.add_product("Plenty", stock=50, reorder=5)
        self.add_product("Almost out", stock=3, reorder=5)
        names = [p["name"] for p in self.db.products(low_only=True)]
        self.assertEqual(names, ["Almost out"])

    def test_invoice_numbers_are_unique_per_day(self):
        pid = self.add_product(stock=100)
        a = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 1}])
        b = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 1}])
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("INV-") and b.endswith("-0002"))

    # ---- quotations, reports, dashboard, backup
    def test_quotation_lifecycle(self):
        qno = self.db.save_quotation([{"name": "Consulting", "qty": 2, "price": 500}], None, "Zain", "0302",
                                     "2026-12-01", discount=0, tax_rate=0)
        self.assertTrue(qno.startswith("QUO-"))
        qid = self.db.one("SELECT id FROM quotations WHERE quote_no=?", (qno,))["id"]
        self.db.set_quotation_status(qid, "Accepted")
        self.assertEqual(self.db.quotations()[0]["status"], "Accepted")

    def test_report_and_dashboard(self):
        pid = self.add_product(stock=20, cost=60, sale=100)
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 5, "price": 100}], paid=300)
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        r = self.db.report(today, today)
        self.assertEqual(r["sales_total"], 500)
        self.assertEqual(r["collected"], 300)
        self.assertEqual(r["outstanding"], 200)
        self.assertEqual(r["gross_profit"], 500 - 5 * 60)
        self.assertEqual(len(self.db.sales_by_day(7)), 7)
        d = self.db.dashboard()
        self.assertEqual(d["today_sales"], 500)

    def test_backup_creates_file(self):
        path = self.db.backup()
        self.assertTrue(os.path.exists(path) and os.path.getsize(path) > 0)


if __name__ == "__main__":
    unittest.main()
