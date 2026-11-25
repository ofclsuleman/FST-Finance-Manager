"""Reports strip: billed, paid and remaining for the invoices in the chosen range."""
import os
import tempfile
import unittest

from fstapp.database import Database
from tests.test_customer_report import USER


class PeriodTotalsTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.path.join(tempfile.mkdtemp(), "pt.db"))
        self.db.create_user(USER)
        shirt = self.db.add_product({"name": "Shirt", "cost_price": 60, "sale_price": 100, "stock": 50,
                                     "reorder_level": 2})
        self.db.save_invoice("sale", [{"product_id": shirt, "name": "Shirt", "qty": 2, "price": 100}],
                             paid=50, method="Cash", entry_date="2026-11-02")
        self.db.save_invoice("sale", [{"product_id": shirt, "name": "Shirt", "qty": 1, "price": 100}],
                             paid=100, method="Cash", entry_date="2026-10-01")

    def test_only_invoices_in_range_are_counted(self):
        t = self.db.period_totals("2026-11-01", "2026-11-30")
        self.assertEqual(t["sales_count"], 1)
        self.assertEqual(t["sales_total"], 200.0)
        self.assertEqual(t["sales_paid"], 50.0)
        self.assertEqual(t["sales_due"], 150.0)

    def test_all_time_adds_everything(self):
        t = self.db.period_totals("0000-00-00", "9999-12-31")
        self.assertEqual(t["sales_total"], 300.0)
        self.assertEqual(t["sales_due"], 150.0)


if __name__ == "__main__":
    unittest.main()
