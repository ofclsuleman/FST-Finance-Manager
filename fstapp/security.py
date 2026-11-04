"""Password hashing, 4-digit PIN rules, recovery questions and auto-login tokens."""
import base64
import hashlib
import hmac
import json
import os
import secrets

from .config import DATA_DIR, SESSION_PATH

ITERATIONS = 200_000
PIN_LENGTH = 4
SECURITY_QUESTIONS = [
    "What is your first pet's name?",
    "What is your mother's maiden name?",
    "In which city were you born?",
    "What was the name of your first school?",
    "What is your favourite food?",
]


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return base64.b64encode(salt + digest).decode()


def verify_password(password, stored):
    raw = base64.b64decode(stored.encode())
    salt, digest = raw[:16], raw[16:]
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return hmac.compare_digest(digest, test)


def is_valid_pin(value):
    """A PIN is exactly four digits, for example 4821."""
    return len(value) == PIN_LENGTH and value.isascii() and value.isdigit()


def normalise_answer(answer):
    return " ".join(answer.lower().split())


def new_token():
    return secrets.token_urlsafe(32)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class SessionFile:
    """Keeps only a random token on this computer, never the password.

    The matching hash lives in the database, so signing out or changing the PIN
    invalidates the token.
    """

    @staticmethod
    def save(token):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump({"token": token}, f)

    @staticmethod
    def load():
        try:
            with open(SESSION_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("token")
        except (OSError, ValueError):
            return None

    @staticmethod
    def clear():
        try:
            os.remove(SESSION_PATH)
        except OSError:
            pass
