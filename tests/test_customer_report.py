"""Customer ledger: one row per invoice with products inside, summary, CSV and PDF."""
import csv
import os
import tempfile
import unittest

from fstapp import customer_report as cr
from fstapp.database import Database

USER = {"first_name": "Ali", "last_name": "", "business_name": "Shop", "email": "a@b.com", "phone": "",
        "currency": "PKR", "password": "4821", "question": "q", "answer": "x"}
ALL = ("0000-00-00", "9999-12-31")


class CustomerReportTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Database(os.path.join(self.dir, "cr.db"))
        self.db.create_user(USER)
        self.shirt = self.db.add_product({"name": "Shirt", "cost_price": 60, "sale_price": 100, "stock": 500,
                                          "reorder_level": 2, "description": "Cotton, blue"})
        self.cust = self.db.add_contact("customers", {"name": "Ahmed", "phone": "0300-1234567"})
        # invoice 1 (2 Nov): 2 lines of 100 each, 50 paid on the day
        self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 2, "price": 100,
                                       "desc": "Large size"}],
                             party_id=self.cust, party_name="Ahmed", paid=50, method="JazzCash",
                             entry_date="2026-11-02")
        # nine more invoices (3 Nov), 100 each, unpaid
        for _ in range(9):
            self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 1, "price": 100}],
                                 party_id=self.cust, party_name="Ahmed", paid=0, method="Cash",
                                 entry_date="2026-11-03")
        # 120 received on 10 Nov, applied to the oldest unpaid invoice (invoice 1)
        self.db.receive_customer_payment(self.cust, 120, method="Cash", day="2026-11-10", note="Part payment")

    def test_summary_for_all_time(self):
        d = cr.collect(self.db, self.cust, *ALL)
        self.assertEqual(d["opening"], 0)
        self.assertEqual(d["billed"], 1100.0)
        self.assertEqual(d["received"], 170.0)
        self.assertEqual(d["closing"], 930.0)
        self.assertEqual(d["outstanding_now"], 930.0)

    def test_one_row_per_invoice_with_products_and_status(self):
        invoices = cr.collect(self.db, self.cust, *ALL)["invoices"]
        self.assertEqual(len(invoices), 10)
        first = invoices[0]
        self.assertEqual((first["date"], first["total"], first["received"], first["remaining"]),
                         ("2026-11-02", 200.0, 170.0, 30.0))
        self.assertEqual(first["status"], "Partly paid")
        self.assertEqual(first["lines"][0]["description"], "Large size")
        self.assertEqual(invoices[1]["status"], "Unpaid")

    def test_period_includes_old_invoice_paid_in_period(self):
        d = cr.collect(self.db, self.cust, "2026-11-03", "2026-11-30")
        self.assertEqual(d["opening"], 150.0, "200 billed on 2 Nov, 50 received before the period")
        self.assertEqual(d["billed"], 900.0, "only the nine invoices dated 3 Nov")
        self.assertEqual(d["received"], 120.0, "the payment received on 10 Nov")
        self.assertEqual(d["closing"], 930.0)
        self.assertEqual(len(d["invoices"]), 10, "invoice 1 is shown because its payment is in the period")
        first = d["invoices"][0]
        self.assertEqual(first["received"], 120.0)

    def test_csv_has_summary_and_columns(self):
        path = os.path.join(self.dir, "d.csv")
        cr.write_csv(path, cr.collect(self.db, self.cust, *ALL), "Shop", "PKR")
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        self.assertIn(["Remaining at end of period", "930.00"], rows)
        header = rows.index(cr.CSV_COLUMNS)
        self.assertEqual(rows[header + 1][0], "2026-11-02")
        self.assertTrue(rows[header + 1][1].startswith("INV-"))
        self.assertEqual(rows[-1][0], "Totals")
        self.assertEqual(rows[-1][5], "1100.00")

    def test_pdf_is_written_and_multi_page(self):
        for _ in range(14):
            self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 1, "price": 10}],
                                 party_id=self.cust, party_name="Ahmed", paid=0, method="Cash",
                                 entry_date="2026-11-04")
        path = os.path.join(self.dir, "d.pdf")
        cr.write_pdf(path, cr.collect(self.db, self.cust, *ALL), "Shop", "PKR")
        with open(path, "rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")
        self.assertGreater(os.path.getsize(path), 5000)

    def test_empty_period_still_makes_a_pdf(self):
        other = self.db.add_contact("customers", {"name": "Empty Shop"})
        path = os.path.join(self.dir, "e.pdf")
        cr.write_pdf(path, cr.collect(self.db, other, "2020-01-01", "2020-01-31"), "Shop", "PKR")
        self.assertTrue(os.path.getsize(path) > 0)


if __name__ == "__main__":
    unittest.main()
