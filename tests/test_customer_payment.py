"""Customer lump-sum payments: applied oldest-first, dated on the day received, no items added."""
import os
import tempfile
import unittest

from fstapp.database import Database

USER = {"first_name": "Ali", "last_name": "", "business_name": "Shop", "email": "a@b.com", "phone": "",
        "currency": "PKR", "password": "4821", "question": "q", "answer": "x"}


class CustomerPaymentTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.path.join(tempfile.mkdtemp(), "pay.db"))
        self.db.create_user(USER)
        self.shirt = self.db.add_product({"name": "Shirt", "cost_price": 60, "sale_price": 100,
                                          "stock": 50, "reorder_level": 2})
        self.cust = self.db.add_contact("customers", {"name": "Ahmed"})
        # 10 invoices: 7 paid in full, 3 unpaid (100 each)
        for i in range(10):
            paid = 100 if i < 7 else 0
            self.db.save_invoice("sale", [{"product_id": self.shirt, "name": "Shirt", "qty": 1, "price": 100}],
                                 party_id=self.cust, party_name="Ahmed", paid=paid,
                                 method="Cash", entry_date=f"2026-11-0{i % 9 + 1}")

    def count(self, table):
        return self.db.scalar(f"SELECT COUNT(*) FROM {table}")

    def test_partial_payment_goes_to_oldest_debt_first(self):
        self.assertEqual(self.db.customer_due(self.cust), 300)
        items_before = self.count("sale_items")
        invoices_before = self.count("sales")

        applied = self.db.receive_customer_payment(self.cust, 150, method="Cash", day="2026-11-14")

        self.assertEqual(len(applied), 2, "first invoice cleared, second part-paid")
        self.assertEqual(applied[0][1], 100)
        self.assertEqual(applied[1][1], 50)
        self.assertEqual(self.db.customer_due(self.cust), 150, "debt reduced by what was received")
        self.assertEqual(self.count("sale_items"), items_before, "no items added")
        self.assertEqual(self.count("sales"), invoices_before, "no invoice created")

    def test_payment_is_dated_on_the_day_received(self):
        self.db.receive_customer_payment(self.cust, 150, method="Cash", day="2026-11-14")
        days = self.db.query("SELECT DISTINCT substr(paid_at,1,10) AS d FROM payments WHERE kind='sale' "
                             "AND paid_at LIKE '2026-11-14%'")
        self.assertEqual([r["d"] for r in days], ["2026-11-14"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM payments WHERE kind='sale' "
                                        "AND paid_at LIKE '2026-11-14%'"), 2)

    def test_full_payment_clears_all_debt(self):
        self.db.receive_customer_payment(self.cust, 300, method="JazzCash", day="2026-11-14")
        self.assertEqual(self.db.customer_due(self.cust), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM sales WHERE paid < total"), 0)

    def test_rejects_overpayment_and_bad_input(self):
        with self.assertRaises(ValueError):
            self.db.receive_customer_payment(self.cust, 999, day="2026-11-14")
        with self.assertRaises(ValueError):
            self.db.receive_customer_payment(self.cust, 0, day="2026-11-14")
        with self.assertRaises(ValueError):
            self.db.receive_customer_payment(self.cust, 10, day="14/11/2026")
        self.assertEqual(self.db.customer_due(self.cust), 300, "nothing changed after errors")

    def test_ledger_stays_balanced(self):
        self.db.receive_customer_payment(self.cust, 150, method="Cash", day="2026-11-14")
        rows = self.db.query("SELECT IFNULL(SUM(debit),0) AS d, IFNULL(SUM(credit),0) AS c FROM journal_lines")
        self.assertEqual(round(rows[0]["d"] - rows[0]["c"], 2), 0)


if __name__ == "__main__":
    unittest.main()
