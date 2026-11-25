"""Ledger CSV export: every movement with reference, description, debit, credit and balances."""
import csv
import os
import tempfile
import unittest

from fstapp.database import Database
from fstapp.ledger_export import write_all_ledgers_csv, write_statement_csv

USER = {"first_name": "Ali", "last_name": "", "business_name": "Shop", "email": "a@b.com", "phone": "",
        "currency": "PKR", "password": "4821", "question": "q", "answer": "x"}


class LedgerExportTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Database(os.path.join(self.dir, "exp.db"))
        self.db.create_user(USER)
        self.shirt = self.db.add_product({"name": "Shirt", "cost_price": 60, "sale_price": 100,
                                          "stock": 50, "reorder_level": 2})
        self.cust = self.db.add_contact("customers", {"name": "Ahmed", "phone": "0300-1234567"})
        self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 2, "price": 100}],
                             party_id=self.cust, party_name="Ahmed", paid=0, method="Cash", entry_date="2026-11-02")
        self.db.receive_customer_payment(self.cust, 120, method="Cash", day="2026-11-10")

    def read(self, path):
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.reader(f))

    def test_statement_has_details_and_balances(self):
        party = self.db.one("SELECT * FROM customers WHERE id=?", (self.cust,))
        st = self.db.party_statement("customer", self.cust, "0000-00-00", "9999-12-31")
        path = os.path.join(self.dir, "st.csv")
        write_statement_csv(path, "Shop", "customer", party, st, "0000-00-00", "9999-12-31", "beginning to today", "PKR")
        rows = self.read(path)
        self.assertIn(["Name", "Ahmed"], rows)
        self.assertIn(["Phone", "0300-1234567"], rows)
        header = rows[rows.index(["Party", "Phone", "Date", "Reference", "Description", "Debit", "Credit", "Balance"])]
        self.assertTrue(header)
        body = rows[rows.index(header) + 1:]
        self.assertEqual(body[0][4], "Opening balance")
        self.assertEqual(body[-1][4], "Closing balance")
        self.assertEqual(body[-1][7], "80.00", "200 charged, 120 received")
        self.assertTrue(any(r[3].startswith("INV-") and r[5] == "200.00" for r in body))
        self.assertTrue(any(r[6] == "120.00" and r[2] == "2026-11-10" for r in body))

    def test_all_customers_file_names_each_party(self):
        blocks = self.db.party_ledger_blocks("customer", "0000-00-00", "9999-12-31")
        self.assertEqual(len(blocks), 1)
        path = os.path.join(self.dir, "all.csv")
        write_all_ledgers_csv(path, "Shop", "customer", blocks, "0000-00-00", "9999-12-31", "beginning to today", "PKR")
        rows = self.read(path)
        self.assertIn(["Total closing balance", "80.00"], rows)
        data = rows[rows.index(["Party", "Phone", "Date", "Reference", "Description", "Debit", "Credit", "Balance"]) + 1:]
        self.assertTrue(all(r[0] == "Ahmed" for r in data))


if __name__ == "__main__":
    unittest.main()
