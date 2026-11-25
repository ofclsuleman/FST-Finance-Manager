"""Sales & purchase list queries (no display needed)."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fstapp.database import Database  # noqa: E402


class EntriesQueryTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.path.join(tempfile.mkdtemp(), "e.db"))
        self.db.create_user({"first_name": "A", "last_name": "", "business_name": "B", "email": "a@b.c",
                             "phone": "", "currency": "PKR", "password": "4821", "question": "q", "answer": "x"})
        self.shirt = self.db.add_product({"name": "Shirt", "cost_price": 600, "sale_price": 1000, "stock": 50,
                                          "reorder_level": 3})
        self.cid = self.db.add_contact("customers", {"name": "Bilal", "phone": "0301"})
        self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 2, "price": 1000,
                                       "desc": "Blue"}, {"product_id": None, "name": "Socks", "qty": 1, "price": 200}],
                             party_id=self.cid, party_name="Bilal", paid=0, entry_date="2026-09-05")
        self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 1, "price": 1000}],
                             paid=1000, entry_date="2026-10-20")
        self.db.save_invoice("purchase", [{"product_id": self.shirt, "name": "Shirt", "qty": 10, "price": 600}],
                             paid=0, entry_date="2026-10-02")

    def tearDown(self):
        self.db.conn.close()

    def test_all_entries_are_listed_without_a_date_limit(self):
        sales = self.db.invoices("sale", None, None, "", limit=100000)
        self.assertEqual(len(sales), 2)
        self.assertEqual({s["item_count"] for s in sales}, {2, 1})

    def test_date_range_filters(self):
        self.assertEqual(len(self.db.invoices("sale", "2026-10-01", "2026-10-31", "", limit=100000)), 1)
        self.assertEqual(len(self.db.invoices("purchase", "2026-10-01", "2026-10-31", "", limit=100000)), 1)

    def test_search_matches_invoice_party_and_product(self):
        self.assertEqual(len(self.db.invoices("sale", None, None, "Bilal", limit=100000)), 1)
        self.assertEqual(len(self.db.invoice_lines("sale", None, None, "Socks")), 1)
        self.assertEqual(len(self.db.invoice_lines("sale", None, None, "")), 3)

    def test_line_items_carry_description_and_invoice_link(self):
        lines = self.db.invoice_lines("sale", "2026-09-01", "2026-09-30", "")
        self.assertEqual(len(lines), 2)
        shirt = [l for l in lines if l["product_name"] == "Shirt"][0]
        self.assertEqual(shirt["description"], "Blue")
        self.assertEqual(shirt["qty"], 2)
        self.assertTrue(shirt["invoice_no"].startswith("INV-"))
        self.assertTrue(any(l["invoice_id"] == shirt["invoice_id"] for l in lines))

    def test_status_is_computed(self):
        statuses = sorted(s["status"] for s in self.db.invoices("sale", None, None, "", limit=100000))
        self.assertEqual(statuses, ["Paid", "Unpaid"])


if __name__ == "__main__":
    unittest.main()
