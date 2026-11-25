"""Editing an invoice keeps its receipts; each receipt can be edited or deleted; the ledger follows."""
import os
import tempfile
import unittest

from fstapp.database import Database
from tests.test_customer_report import USER


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.path.join(tempfile.mkdtemp(), "rc.db"))
        self.db.create_user(USER)
        self.shirt = self.db.add_product({"name": "Shirt", "cost_price": 60, "sale_price": 100, "stock": 500,
                                          "reorder_level": 2})
        self.cust = self.db.add_contact("customers", {"name": "Ahmed"})
        self.inv_no = self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 2, "price": 100}],
                                           party_id=self.cust, party_name="Ahmed", paid=0, method="Cash",
                                           entry_date="2026-11-02")
        self.inv_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (self.inv_no,))["id"]
        self.db.receive_customer_payment(self.cust, 50, method="Cash", day="2026-11-05", note="first")
        self.db.receive_customer_payment(self.cust, 30, method="JazzCash", day="2026-11-13", note="second")

    def receipts(self):
        # An edited invoice gets a new row id, so look it up by its number each time.
        inv_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (self.inv_no,))["id"]
        return self.db.query("SELECT * FROM payments WHERE kind='sale' AND invoice_id=? ORDER BY id", (inv_id,))

    def test_editing_the_invoice_keeps_each_receipt_and_its_date(self):
        self.db.replace_invoice("sale", self.inv_id,
                                [{"product_id": self.shirt, "name": "Shirt", "qty": 3, "price": 100}],
                                party_id=self.cust, party_name="Ahmed", method="Cash", entry_date="2026-11-02")
        rec = self.receipts()
        self.assertEqual([(r["amount"], r["method"], r["paid_at"][:10], r["note"]) for r in rec],
                         [(50.0, "Cash", "2026-11-05", "first"), (30.0, "JazzCash", "2026-11-13", "second")])
        inv = self.db.one("SELECT * FROM sales WHERE invoice_no=?", (self.inv_no,))
        self.assertEqual((inv["total"], inv["paid"]), (300.0, 80.0))
        self.assertEqual(self.db.customer_due(self.cust), 220.0)

    def test_edit_that_would_drop_below_received_is_refused_and_nothing_changes(self):
        with self.assertRaises(ValueError):
            self.db.replace_invoice("sale", self.inv_id,
                                    [{"product_id": self.shirt, "name": "Shirt", "qty": 1, "price": 50}],
                                    party_id=self.cust, party_name="Ahmed", entry_date="2026-11-02")
        inv = self.db.one("SELECT * FROM sales WHERE invoice_no=?", (self.inv_no,))
        self.assertEqual((inv["total"], inv["paid"]), (200.0, 80.0))
        self.assertEqual(len(self.receipts()), 2)

    def test_update_receipt_changes_amount_date_and_ledger(self):
        first = self.receipts()[0]
        self.db.update_payment(first["id"], 70, "2026-11-08", "Bank Transfer", "fixed")
        r = self.receipts()[0]
        self.assertEqual((r["amount"], r["method"], r["paid_at"][:10], r["note"]), (70.0, "Bank Transfer", "2026-11-08", "fixed"))
        inv = self.db.one("SELECT paid FROM sales WHERE invoice_no=?", (self.inv_no,))
        self.assertEqual(inv["paid"], 100.0)
        rows = self.db.query("SELECT IFNULL(SUM(debit),0) d, IFNULL(SUM(credit),0) c FROM journal_lines")
        self.assertEqual(round(rows[0]["d"] - rows[0]["c"], 2), 0)

    def test_update_receipt_refuses_more_than_total(self):
        with self.assertRaises(ValueError):
            self.db.update_payment(self.receipts()[0].__getitem__("id"), 999, "2026-11-08", "Cash")
        self.assertEqual(self.receipts()[0]["amount"], 50.0)

    def test_delete_receipt_lowers_paid_and_ledger(self):
        self.db.delete_payment(self.receipts()[1]["id"])
        inv = self.db.one("SELECT paid FROM sales WHERE invoice_no=?", (self.inv_no,))
        self.assertEqual(inv["paid"], 50.0)
        self.assertEqual(len(self.receipts()), 1)
        rows = self.db.query("SELECT IFNULL(SUM(debit),0) d, IFNULL(SUM(credit),0) c FROM journal_lines")
        self.assertEqual(round(rows[0]["d"] - rows[0]["c"], 2), 0)


if __name__ == "__main__":
    unittest.main()
