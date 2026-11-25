"""Tests for WhatsApp sharing and invoice images (no display needed)."""
import os
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fstapp import documents  # noqa: E402
from fstapp.database import Database  # noqa: E402
from fstapp.share import normalise_phone, whatsapp_url  # noqa: E402


class PhoneTests(unittest.TestCase):
    def test_local_numbers_get_country_code(self):
        self.assertEqual(normalise_phone("0300-1234567", "92"), "923001234567")
        self.assertEqual(normalise_phone("3001234567", "92"), "923001234567")

    def test_international_formats(self):
        self.assertEqual(normalise_phone("+92 300 1234567", "92"), "923001234567")
        self.assertEqual(normalise_phone("0092 300 1234567", "92"), "923001234567")
        self.assertEqual(normalise_phone("923001234567", "92"), "923001234567")

    def test_unusable_numbers_are_rejected(self):
        self.assertIsNone(normalise_phone("", "92"))
        self.assertIsNone(normalise_phone("abc", "92"))
        self.assertIsNone(normalise_phone("12", "92"))

    def test_other_country_code(self):
        self.assertEqual(normalise_phone("07700 900123", "44"), "447700900123")


class LinkTests(unittest.TestCase):
    def test_link_with_number_and_message(self):
        url = whatsapp_url("923001234567", "Invoice INV-1\nTotal: PKR 500")
        self.assertTrue(url.startswith("https://wa.me/923001234567?text="))
        self.assertEqual(parse_qs(urlparse(url).query)["text"][0], "Invoice INV-1\nTotal: PKR 500")

    def test_link_without_number_opens_chooser(self):
        url = whatsapp_url(None, "Hello")
        self.assertEqual(urlparse(url).path, "/")
        self.assertEqual(unquote(urlparse(url).query), "text=Hello")


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        documents.SHARE_DIR = os.path.join(self.tmp, "shares")
        self.db = Database(os.path.join(self.tmp, "t.db"))
        self.db.create_user({"first_name": "Ali", "last_name": "", "business_name": "Test Store",
                             "email": "a@b.c", "phone": "", "currency": "PKR", "password": "4821",
                             "question": "q", "answer": "x"})
        self.user = self.db.get_user(1)
        self.pid = self.db.add_product({"name": "Cotton shirt", "cost_price": 600, "sale_price": 1000,
                                        "stock": 20, "reorder_level": 3, "description": "Size M, blue"})
        self.cid = self.db.add_contact("customers", {"name": "Bilal Traders", "phone": "0301-2223344"})

    def tearDown(self):
        self.db.conn.close()

    def test_sale_invoice_image_is_png_with_contact(self):
        inv = self.db.save_invoice("sale", [{"product_id": self.pid, "name": "Cotton shirt", "qty": 2,
                                             "price": 1000, "desc": "Gift wrapped"}],
                                   party_id=self.cid, party_name="Bilal Traders", paid=500, tax_rate=10)
        sid = self.db.one("SELECT id FROM sales WHERE invoice_no=?", (inv,))["id"]
        path, info = documents.invoice_image(self.db, self.user, "sale", sid)
        with open(path, "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
        self.assertEqual(info["party_phone"], "0301-2223344")
        self.assertEqual(info["contact_table"], "customers")
        self.assertEqual(info["balance"], "PKR 1,700.00")
        self.assertIn(inv, documents.share_message(info, "Test Store"))

    def test_purchase_and_quotation_images(self):
        inv = self.db.save_invoice("purchase", [{"product_id": self.pid, "name": "Cotton shirt", "qty": 5, "price": 600}],
                                   paid=3000)
        pid = self.db.one("SELECT id FROM purchases WHERE invoice_no=?", (inv,))["id"]
        path, info = documents.invoice_image(self.db, self.user, "purchase", pid)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(info["contact_table"], "suppliers")
        self.db.save_quotation([{"name": "Consulting", "qty": 2, "price": 500, "desc": "Two hours"}],
                               self.cid, "Bilal Traders", "0301-2223344", "2026-12-01", tax_rate=5)
        qid = self.db.one("SELECT id FROM quotations")["id"]
        qpath, qinfo = documents.quotation_image(self.db, self.user, qid)
        self.assertTrue(qpath.endswith(".png") and os.path.getsize(qpath) > 1000)
        self.assertTrue(qinfo["number"].startswith("QUO-"))

    def test_missing_invoice_raises_clear_error(self):
        with self.assertRaises(ValueError):
            documents.invoice_image(self.db, self.user, "sale", 999)


if __name__ == "__main__":
    unittest.main()
