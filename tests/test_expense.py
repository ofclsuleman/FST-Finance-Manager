"""Recording an expense from the Reports page posts a balanced entry that shows in the expense report."""
import os
import tempfile
import unittest

from fstapp.database import Database
from fstapp.ledger import CASH, COGS
from fstapp.report_engine import build

USER = {"first_name": "Ali", "last_name": "", "business_name": "Shop", "email": "a@b.com", "phone": "",
        "currency": "PKR", "password": "4821", "question": "q", "answer": "x"}


class ExpenseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.path.join(tempfile.mkdtemp(), "exp.db"))
        self.db.create_user(USER)

    def test_expense_appears_in_report_and_ledger_balances(self):
        expense = next(a for a in self.db.accounts() if a["type"] == "expense" and a["code"] != COGS)
        self.db.post_simple("2026-11-10", "Electricity", expense["code"], CASH, 750.0)
        report = build(self.db, "exp", "2026-11-01", "2026-11-30", "Shop")
        self.assertEqual(report["summary"][0][1], "750.00")
        rows = self.db.query("SELECT IFNULL(SUM(debit),0) d, IFNULL(SUM(credit),0) c FROM journal_lines")
        self.assertEqual(round(rows[0]["d"] - rows[0]["c"], 2), 0)


if __name__ == "__main__":
    unittest.main()
