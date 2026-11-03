"""Password hashing and the optional "Remember Password" session file."""
import base64
import hashlib
import hmac
import json
import os
import secrets

from .config import DATA_DIR, SESSION_PATH

_ITERATIONS = 200_000


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return base64.b64encode(salt + digest).decode()


def verify_password(password, stored):
    raw = base64.b64decode(stored.encode())
    salt, digest = raw[:16], raw[16:]
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(digest, test)


class SessionStore:
    """Remembers login details on this computer.

    The password is base64-encoded, which is obfuscation, not encryption.
    For real protection, replace this with the OS keyring (`keyring` package).
    """

    @staticmethod
    def save(email, password):
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = {"email": email, "password": base64.b64encode(password.encode()).decode()}
        with open(SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    @staticmethod
    def load():
        try:
            with open(SESSION_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d["email"], base64.b64decode(d["password"].encode()).decode()
        except Exception:
            return None

    @staticmethod
    def clear():
        try:
            os.remove(SESSION_PATH)
        except OSError:
            pass
