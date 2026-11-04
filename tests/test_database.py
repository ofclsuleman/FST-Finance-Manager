"""Business-logic tests (no display needed).

Run from the project folder:  python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fstapp import database as dbmod  # noqa: E402
from fstapp import report_engine  # noqa: E402
from fstapp.database import Database  # noqa: E402
from fstapp.security import is_valid_pin  # noqa: E402

ALL = ("0000-00-00", "9999-12-31")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        dbmod.BACKUP_DIR = os.path.join(self.tmp, "backups")
        self.db = Database(os.path.join(self.tmp, "t.db"))
        self.db.create_user({"first_name": "Ali", "last_name": "", "business_name": "Test Co",
                             "email": "ali@x.com", "phone": "", "currency": "PKR", "password": "4821",
                             "question": "What is your first pet's name?", "answer": "Tommy"})

    def tearDown(self):
        self.db.conn.close()

    def add_product(self, name="Widget", stock=10, reorder=5, cost=60, sale=100, desc=None):
        return self.db.add_product({"name": name, "sku": None, "category": "", "unit": "pcs", "cost_price": cost,
                                    "sale_price": sale, "stock": stock, "reorder_level": reorder, "description": desc})

    def stock_of(self, pid):
        return self.db.one("SELECT stock FROM products WHERE id=?", (pid,))["stock"]

    def trial_balanced(self):
        tb = self.db.trial_balance(*ALL)
        return abs(sum(r["dr"] for r in tb) - sum(r["cr"] for r in tb)) < 0.01


class AccountTests(Base):
    def test_pin_rules(self):
        self.assertTrue(is_valid_pin("4821"))
        self.assertFalse(is_valid_pin("482"))
        self.assertFalse(is_valid_pin("48215"))
        self.assertFalse(is_valid_pin("48a1"))

    def test_login_with_pin(self):
        self.assertEqual(self.db.authenticate("ALI@x.com", "4821")["business_name"], "Test Co")
        self.assertIsNone(self.db.authenticate("ali@x.com", "0000"))

    def test_session_auto_login_and_sign_out(self):
        token = self.db.create_session(self.db.find_user_by_email("ali@x.com")["id"])
        self.assertEqual(self.db.session_user(token)["email"], "ali@x.com")
        self.db.end_session(token)
        self.assertIsNone(self.db.session_user(token))
        self.assertIsNone(self.db.session_user(None))

    def test_forgot_password_with_recovery_answer(self):
        uid = self.db.find_user_by_email("ali@x.com")["id"]
        self.assertFalse(self.db.verify_recovery_answer(uid, "Rocky"))
        self.assertTrue(self.db.verify_recovery_answer(uid, "  tommy "))  # case and spacing ignored
        token = self.db.create_session(uid)
        self.db.reset_pin(uid, "1111")
        self.assertIsNone(self.db.session_user(token))           # reset signs out every session
        self.assertIsNotNone(self.db.authenticate("ali@x.com", "1111"))
        self.assertIsNone(self.db.authenticate("ali@x.com", "4821"))


    def test_legacy_account_can_set_recovery_then_reset(self):
        uid = self.db.find_user_by_email("ali@x.com")["id"]
        self.db.conn.execute("UPDATE users SET security_question=NULL, security_answer_hash=NULL WHERE id=?", (uid,))
        self.db.conn.commit()
        self.assertFalse(self.db.verify_recovery_answer(uid, "Tommy"))
        self.db.set_recovery(uid, "What is your mother's maiden name?", "Khan")
        self.assertTrue(self.db.verify_recovery_answer(uid, "khan"))
        self.assertEqual(self.db.get_user(uid)["security_question"], "What is your mother's maiden name?")


class InvoiceTests(Base):
    def test_saved_customer_appears_in_picker(self):
        cid = self.db.add_contact("customers", {"name": "Bilal Traders", "phone": "0301"})
        labels = [label for label, _ in self.db.contact_options("customers", "Bil")]
        self.assertEqual(len(labels), 1)
        self.assertIn(cid, [v["id"] for _, v in self.db.contact_options("customers", "")])

    def test_description_is_saved_on_each_line(self):
        pid = self.add_product(desc="Blue, size M")
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 100,
                                             "desc": "Gift wrapped"}])
        sale_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        self.assertEqual(self.db.invoice_detail("sale", sale_id)["items"][0]["description"], "Gift wrapped")
        self.assertEqual(self.db.one("SELECT description FROM products WHERE id=?", (pid,))["description"], "Blue, size M")

    def test_discount_tax_partial_payment_and_balances(self):
        pid = self.add_product()
        cid = self.db.add_contact("customers", {"name": "Sara"})
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 3, "price": 100}],
                                   party_id=cid, party_name="Sara", discount=50, tax_rate=10, paid=100)
        row = self.db.one("SELECT * FROM sales WHERE invoice_no=?", (inv,))
        self.assertEqual((row["subtotal"], row["tax"], row["total"]), (300, 25, 275))
        self.assertEqual(row["paid"], 100)
        self.assertEqual(self.db.contact_balances("customers")[cid], 175)
        self.assertEqual([r["status"] for r in self.db.invoices("sale") if r["invoice_no"] == inv], ["Partial"])

    def test_payments_are_history_and_capped_at_due(self):
        pid = self.add_product()
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 100}], paid=0)
        sid = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        self.db.record_payment("sale", sid, 40, method="Bank Transfer")
        applied = self.db.record_payment("sale", sid, 1000)
        self.assertEqual(applied, 60)
        self.assertEqual(len(self.db.payments("sale", sid)), 2)
        with self.assertRaises(ValueError):
            self.db.record_payment("sale", sid, 10)

    def test_credit_sale_records_no_payment(self):
        pid = self.add_product()
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 100}],
                                   paid=100, method="Credit")
        sid = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        self.assertEqual(self.db.payments("sale", sid), [])
        self.assertEqual(self.db.one("SELECT paid FROM sales WHERE id=?", (sid,))["paid"], 0)

    def test_zero_stock_sale_allowed_and_purchase_restocks(self):
        pid = self.add_product(stock=2)
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 5, "price": 100}])
        self.assertEqual(self.stock_of(pid), -3)
        self.db.save_invoice("purchase", [{"product_id": pid, "name": "Widget", "qty": 10, "price": 60}])
        self.assertEqual(self.stock_of(pid), 7)

    def test_delete_invoice_reverses_stock_and_journal(self):
        pid = self.add_product(stock=10)
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 4, "price": 100}], paid=100)
        sid = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        self.db.delete_invoice("sale", sid)
        self.assertEqual(self.stock_of(pid), 10)
        self.assertEqual(self.db.invoices("sale"), [])
        self.assertTrue(self.trial_balanced())

    def test_entry_date_drives_invoice_date_and_ledger(self):
        pid = self.add_product(stock=10)
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 100}],
                                   paid=100, entry_date="2026-10-15")
        row = self.db.one("SELECT created_at FROM sales WHERE invoice_no=?", (inv,))
        self.assertTrue(row["created_at"].startswith("2026-10-15T"))
        entry = self.db.one("SELECT entry_date FROM journal_entries WHERE ref_no=?", (inv,))
        self.assertEqual(entry["entry_date"], "2026-10-15")
        self.assertEqual(len(self.db.invoices("sale", "2026-10-15", "2026-10-15")), 1)
        self.assertEqual(len(self.db.invoices("sale", "2026-11-04", "2026-11-04")), 0)

    def test_invoice_payment_posts_on_invoice_date(self):
        """Regression: payments taken when saving an invoice must be dated the invoice date."""
        pid = self.add_product(stock=10, cost=60, sale=1000)
        cid = self.db.add_contact("customers", {"name": "Bilal"})
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Shirt", "qty": 4, "price": 1000}],
                             party_id=cid, party_name="Bilal", tax_rate=10, paid=2000, entry_date="2026-10-10")
        self.db.save_invoice("purchase", [{"product_id": pid, "name": "Shirt", "qty": 10, "price": 600}],
                             paid=6000, method="Bank Transfer", entry_date="2026-10-02")
        oct_bs = self.db.balance_sheet("2026-10-31")
        self.assertTrue(oct_bs["balanced"])
        ar = dict(self.reconcile_rows("2026-10-31"))
        self.assertAlmostEqual(ar["Accounts receivable (customers)"], 2400)   # 4400 billed - 2000 received
        self.assertAlmostEqual(ar["Accounts payable (suppliers)"], 0)         # 6000 bought - 6000 paid

    def reconcile_rows(self, as_of):
        return self.db.balance_sheet(as_of)["assets"] + self.db.balance_sheet(as_of)["liabilities"]

    def test_ledger_receivable_matches_invoice_balances(self):
        pid = self.add_product(stock=50, cost=10, sale=100)
        cid = self.db.add_contact("customers", {"name": "Hira"})
        self.db.save_invoice("sale", [{"product_id": pid, "name": "A", "qty": 3, "price": 100}],
                             party_id=cid, party_name="Hira", tax_rate=5, paid=50, entry_date="2026-09-01")
        self.db.save_invoice("sale", [{"product_id": pid, "name": "A", "qty": 1, "price": 100}],
                             party_id=cid, party_name="Hira", paid=0, entry_date="2026-09-20")
        sid = self.db.one("SELECT id FROM sales ORDER BY id LIMIT 1")["id"]
        self.db.record_payment("sale", sid, 100, method="Cash")
        invoice_due = self.db.scalar("SELECT SUM(total - paid) FROM sales")
        ar = dict(self.reconcile_rows(ALL[1]))["Accounts receivable (customers)"]
        self.assertAlmostEqual(ar, invoice_due, places=2)

    def test_invalid_entry_date_is_rejected(self):
        pid = self.add_product(stock=10)
        with self.assertRaises(ValueError):
            self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 1}],
                                 entry_date="15/10/2026")

    def test_unknown_product_is_created_on_sale(self):
        self.db.save_invoice("sale", [{"product_id": None, "name": "New Item", "qty": 1, "price": 250}])
        row = self.db.one("SELECT sale_price, stock FROM products WHERE name='New Item'")
        self.assertEqual((row["sale_price"], row["stock"]), (250, -1))

    def test_invoice_numbers_are_unique(self):
        pid = self.add_product(stock=100)
        a = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 1}])
        b = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 1}])
        self.assertTrue(a != b and b.endswith("-0002"))

    def test_quotation_numbering_and_status(self):
        qno = self.db.save_quotation([{"name": "Consulting", "qty": 2, "price": 500}], None, "Zain", "0302", "2026-12-01")
        self.assertTrue(qno.startswith("QUO-"))
        qid = self.db.one("SELECT id FROM quotations WHERE quote_no=?", (qno,))["id"]
        self.db.set_quotation_status(qid, "Accepted")
        self.assertEqual(self.db.quotations()[0]["status"], "Accepted")

    def test_low_stock_filter_and_backup(self):
        self.add_product("Plenty", stock=50)
        self.add_product("Almost out", stock=3)
        self.assertEqual([p["name"] for p in self.db.products(low_only=True)], ["Almost out"])
        self.assertTrue(os.path.exists(self.db.backup()))


class LedgerTests(Base):
    def test_journal_balances_through_full_cycle(self):
        pid = self.add_product(stock=10, cost=60, sale=100)
        cid = self.db.add_contact("customers", {"name": "Bilal"})
        sid_name = self.db.add_contact("suppliers", {"name": "Star"})
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 3, "price": 100}],
                                   party_id=cid, party_name="Bilal", tax_rate=10, paid=100)
        pinv = self.db.save_invoice("purchase", [{"product_id": pid, "name": "Widget", "qty": 10, "price": 60}],
                                    party_id=sid_name, party_name="Star", paid=0)
        self.db.save_invoice("sale", [{"product_id": None, "name": "Service", "qty": 1, "price": 50}], paid=0, method="Credit")
        sale_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        self.db.record_payment("sale", sale_id, 500, method="Bank Transfer")
        purchase_id = self.db.one("SELECT id FROM purchases WHERE invoice_no=?", (pinv,))["id"]
        self.db.record_payment("purchase", purchase_id, 200, method="Cash")
        self.assertTrue(self.trial_balanced())
        self.assertTrue(self.db.balance_sheet(ALL[1])["balanced"])
        self.assertEqual(self.db.contact_balances("customers")[cid], 0)

    def test_profit_and_loss_figures(self):
        pid = self.add_product(stock=20, cost=60, sale=100)
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 5, "price": 100}], paid=500)
        self.db.post_simple(datetime.now().strftime("%Y-%m-%d"), "Rent", "6100", "1000", 200)
        pl = self.db.profit_and_loss(*ALL)
        self.assertEqual(pl["revenue"], 500)
        self.assertEqual(pl["cogs"], 300)
        self.assertEqual(pl["gross"], 200)
        self.assertEqual(pl["net"], 0)   # 200 gross profit less 200 rent

    def test_quick_entry_and_manual_delete(self):
        self.db.post_simple("2026-11-01", "Owner capital", "1000", "3000", 10000)
        bs = self.db.balance_sheet(ALL[1])
        self.assertTrue(bs["balanced"])
        self.assertEqual(bs["total_assets"], 10000)
        eid = self.db.one("SELECT id FROM journal_entries WHERE memo='Owner capital'")["id"]
        self.db.delete_manual_entry(eid)
        self.assertEqual(self.db.balance_sheet(ALL[1])["total_assets"], 0)
        pid = self.add_product()
        inv = self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 1}])
        sale_entry = self.db.one("SELECT id FROM journal_entries WHERE ref_no=?", (inv,))["id"]
        with self.assertRaises(ValueError):
            self.db.delete_manual_entry(sale_entry)

    def test_party_statement_running_balance(self):
        pid = self.add_product(stock=10)
        cid = self.db.add_contact("customers", {"name": "Hira"})
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 100}],
                             party_id=cid, party_name="Hira", paid=0)
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 1, "price": 50}],
                             party_id=cid, party_name="Hira", paid=20)
        st = self.db.party_statement("customer", cid, *ALL)
        self.assertEqual(st["closing"], 130)
        self.assertEqual([round(r["balance"], 2) for r in st["rows"]][-1], 130)

    def test_all_reports_build(self):
        pid = self.add_product(stock=10)
        cid = self.db.add_contact("customers", {"name": "Hira"})
        self.db.save_invoice("sale", [{"product_id": pid, "name": "Widget", "qty": 2, "price": 100}],
                             party_id=cid, party_name="Hira", tax_rate=5, paid=0)
        for key, _, _ in report_engine.REPORTS:
            r = report_engine.build(self.db, key, *ALL, "Test Co")
            self.assertTrue(r["headers"], key)
            self.assertTrue(r["rows"], key)
            for cells, style in r["rows"]:
                self.assertLessEqual(len(cells), len(r["headers"]), key)
        tb = report_engine.build(self.db, "tb", *ALL, "Test Co")
        self.assertIn("agree", tb["note"])
        self.assertIn("balanced", report_engine.build(self.db, "bs", *ALL, "Test Co")["note"].lower())


if __name__ == "__main__":
    unittest.main()
