"""Party names must not carry the phone number from the picker label."""
import os
import tempfile
import unittest

from fstapp.config import name_part
from fstapp.database import Database
from fstapp.documents import invoice_image

USER = {"first_name": "Ali", "last_name": "", "business_name": "Shop", "email": "a@b.com", "phone": "",
        "currency": "PKR", "password": "4821", "question": "q", "answer": "x"}


class NamePartTests(unittest.TestCase):
    def test_label_keeps_only_name(self):
        self.assertEqual(name_part("Atif Yaqoub  ·  0323-0455683"), "Atif Yaqoub")

    def test_plain_name_passes_through(self):
        self.assertEqual(name_part("  Ali Traders "), "Ali Traders")
        self.assertEqual(name_part(None), "")


class LegacyNameTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(os.path.join(tempfile.mkdtemp(), "names.db"))
        self.db.create_user(USER)
        self.pid = self.db.add_product({"name": "Stamp", "cost_price": 0, "sale_price": 600, "stock": 5,
                                        "reorder_level": 1})

    def test_old_rows_are_cleaned_once(self):
        # simulate a row saved by an older version, with the label stored as the name
        no = self.db.save_invoice("sale", [{"product_id": self.pid, "name": "Stamp", "qty": 1, "price": 600}],
                                  party_name="Atif Yaqoub  ·  0323-0455683", party_phone="0323-0455683", paid=0)
        self.assertEqual(self.db.one("SELECT customer_name FROM sales WHERE invoice_no=?", (no,))["customer_name"],
                         "Atif Yaqoub  ·  0323-0455683")
        self.db.set_setting("party_names_cleaned", "0")
        self.db._clean_party_names()
        self.assertEqual(self.db.one("SELECT customer_name FROM sales WHERE invoice_no=?", (no,))["customer_name"],
                         "Atif Yaqoub")

    def test_image_shows_name_and_phone_once(self):
        no = self.db.save_invoice("sale", [{"product_id": self.pid, "name": "Stamp", "qty": 1, "price": 600}],
                                  party_name="Atif Yaqoub  ·  0323-0455683", party_phone="0323-0455683", paid=0)
        inv_id = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (no,))["id"]
        _, info = invoice_image(self.db, USER, "sale", inv_id)
        self.assertEqual(info["party_name"], "Atif Yaqoub")
        self.assertEqual(info["party_phone"], "0323-0455683")


if __name__ == "__main__":
    unittest.main()
