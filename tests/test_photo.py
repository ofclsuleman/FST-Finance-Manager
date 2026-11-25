"""Profile picture: cropped to a square PNG, saved on the user, rejected when unreadable."""
import io
import os
import tempfile
import unittest

from PIL import Image

from fstapp import photo
from fstapp.database import Database

USER = {"first_name": "Ali", "last_name": "", "business_name": "Shop", "email": "a@b.com", "phone": "",
        "currency": "PKR", "password": "4821", "question": "q", "answer": "x"}


class PhotoTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = Database(os.path.join(self.dir, "photo.db"))
        self.db.create_user(USER)
        self.uid = self.db.find_user_by_email(USER["email"])["id"]

    def test_wide_picture_is_cropped_to_square_png(self):
        path = os.path.join(self.dir, "wide.jpg")
        Image.new("RGB", (640, 320), (200, 30, 30)).save(path)
        data = photo.prepare(path)
        img = Image.open(io.BytesIO(data))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size, (photo.SIZE, photo.SIZE))

    def test_unreadable_file_is_rejected(self):
        path = os.path.join(self.dir, "notes.txt")
        with open(path, "w") as f:
            f.write("not a picture")
        with self.assertRaises(ValueError):
            photo.prepare(path)

    def test_picture_saved_and_removed_on_user(self):
        path = os.path.join(self.dir, "p.png")
        Image.new("RGB", (100, 100), (0, 0, 255)).save(path)
        self.db.set_user_photo(self.uid, photo.prepare(path))
        self.assertTrue(self.db.get_user(self.uid)["photo"])
        self.db.set_user_photo(self.uid, None)
        self.assertIsNone(self.db.get_user(self.uid)["photo"])


if __name__ == "__main__":
    unittest.main()
