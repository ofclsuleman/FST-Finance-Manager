"""Application-wide constants, paths and colour themes."""
import os
import sys

APP_NAME = "FST - Finance Management"
APP_VERSION = "2.0.0"

DATA_DIR = os.path.join(os.path.expanduser("~"), ".fst_finance")
DB_PATH = os.path.join(DATA_DIR, "fst_finance_v2.db")
SESSION_PATH = os.path.join(DATA_DIR, "session.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

CURRENCIES = ["PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR", "CNY", "JPY", "CAD", "AUD"]
PAYMENT_METHODS = ["Cash", "Bank Transfer", "Card", "Mobile Wallet", "Cheque", "Credit"]
UNITS = ["pcs", "kg", "g", "L", "mL", "m", "box", "dozen", "service"]
DEFAULT_LOW_STOCK = 5
WALK_IN = "Walk-in (no customer)"

THEMES = {
    "light": {
        "bg": "#F3F5F9", "card": "#FFFFFF", "fg": "#0F172A", "muted": "#64748B",
        "accent": "#2563EB", "accent_hover": "#1D4ED8", "accent_fg": "#FFFFFF",
        "entry": "#FFFFFF", "border": "#E2E8F0", "row_alt": "#F8FAFC", "head": "#EEF2F7",
        "head_hover": "#E2E8F0", "danger": "#DC2626", "danger_hover": "#B91C1C",
        "success": "#059669", "warn": "#D97706", "chart": "#3B82F6",
        "side": "#0F172A", "side_fg": "#94A3B8", "side_hover": "#1E293B",
        "side_active": "#2563EB", "side_active_fg": "#FFFFFF", "side_title": "#FFFFFF",
    },
    "dark": {
        "bg": "#0B1120", "card": "#131C2E", "fg": "#E2E8F0", "muted": "#8A97AD",
        "accent": "#3B82F6", "accent_hover": "#2563EB", "accent_fg": "#FFFFFF",
        "entry": "#1B2740", "border": "#23304A", "row_alt": "#16213A", "head": "#1B2740",
        "head_hover": "#243455", "danger": "#F87171", "danger_hover": "#EF4444",
        "success": "#34D399", "warn": "#FBBF24", "chart": "#60A5FA",
        "side": "#070C18", "side_fg": "#7C8AA3", "side_hover": "#131C2E",
        "side_active": "#1E3A8A", "side_active_fg": "#FFFFFF", "side_title": "#FFFFFF",
    },
}


def resource_path(*parts):
    """Path to a bundled file, both from source and when frozen by PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)
