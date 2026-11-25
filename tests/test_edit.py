"""Editing and deleting saved sales and purchases: stock, ledger and numbering must stay correct."""
import os
import tempfile
import unittest

from fstapp.database import Database

USER = {"first_name": "Ali", "last_name": "", "business_name": "Shop", "email": "a@b.com", "phone": "",
        "currency": "PKR", "password": "4821", "question": "q", "answer": "x"}


class EditInvoiceTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.path.join(tempfile.mkdtemp(), "edit.db"))
        self.db.create_user(USER)
        self.shirt = self.db.add_product({"name": "Shirt", "cost_price": 60, "sale_price": 100,
                                          "stock": 10, "reorder_level": 2})

    def stock(self):
        return self.db.scalar("SELECT stock FROM products WHERE id=?", (self.shirt,))

    def ledger_balanced(self):
        rows = self.db.query("SELECT IFNULL(SUM(debit),0) AS d, IFNULL(SUM(credit),0) AS c FROM journal_lines")
        return round(rows[0]["d"] - rows[0]["c"], 2) == 0

    def test_edit_keeps_number_and_fixes_stock(self):
        inv_no = self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 2, "price": 100}],
                                      paid=200, method="Cash", entry_date="2026-11-01")
        inv_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv_no,))["id"]
        self.assertEqual(self.stock(), 8)

        returned = self.db.replace_invoice("sale", inv_id, [{"product_id": self.shirt, "name": "Shirt", "qty": 3,
                                                             "price": 100}],
                                           paid=300, method="Cash", entry_date="2026-11-02")
        self.assertEqual(returned, inv_no)
        self.assertEqual(self.stock(), 7, "old 2 units reversed, new 3 units taken")
        head = self.db.one("SELECT * FROM sales WHERE invoice_no=?", (inv_no,))
        self.assertEqual(head["total"], 300)
        self.assertEqual(head["created_at"][:10], "2026-11-02")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM sales"), 1, "no duplicate invoice")
        self.assertTrue(self.ledger_balanced())

    def test_edit_changes_party_and_payment(self):
        inv_no = self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 1, "price": 100}],
                                      paid=0, method="Credit", entry_date="2026-11-01")
        inv_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv_no,))["id"]
        self.db.replace_invoice("sale", inv_id, [{"product_id": self.shirt, "name": "Shirt", "qty": 1, "price": 100}],
                                party_name="Ali Traders", paid=100, method="JazzCash", entry_date="2026-11-01")
        head = self.db.one("SELECT * FROM sales WHERE invoice_no=?", (inv_no,))
        self.assertEqual(head["customer_name"], "Ali Traders")
        self.assertEqual(head["paid"], 100)
        self.assertEqual(head["payment_method"], "JazzCash")
        self.assertEqual(len(self.db.payments("sale", head["id"])), 1, "one payment row, not duplicated")
        self.assertTrue(self.ledger_balanced())

    def test_edit_purchase_reverses_stock_the_other_way(self):
        inv_no = self.db.save_invoice("purchase", [{"product_id": self.shirt, "name": "Shirt", "qty": 5, "price": 60}],
                                      paid=300, entry_date="2026-11-01")
        inv_id = self.db.one("SELECT id FROM purchases WHERE invoice_no=?", (inv_no,))["id"]
        self.assertEqual(self.stock(), 15)
        self.db.replace_invoice("purchase", inv_id, [{"product_id": self.shirt, "name": "Shirt", "qty": 2, "price": 60}],
                                paid=120, entry_date="2026-11-01")
        self.assertEqual(self.stock(), 12)
        self.assertTrue(self.ledger_balanced())

    def test_delete_restores_stock_and_ledger(self):
        inv_no = self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 4, "price": 100}],
                                      paid=400)
        inv_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv_no,))["id"]
        self.db.delete_invoice("sale", inv_id)
        self.assertEqual(self.stock(), 10)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM journal_entries"), 0)
        self.assertTrue(self.ledger_balanced())

    def test_edit_missing_invoice_raises(self):
        with self.assertRaises(ValueError):
            self.db.replace_invoice("sale", 9999, [{"name": "X", "qty": 1, "price": 1}])


if __name__ == "__main__":
    unittest.main()
