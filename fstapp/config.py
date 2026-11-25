"""Application-wide constants, paths and colour themes."""
import os
import sys

APP_NAME = "FST - Finance Management"
APP_VERSION = "3.0.0"

DATA_DIR = os.path.join(os.path.expanduser("~"), ".fst_finance")
DB_PATH = os.path.join(DATA_DIR, "fst_finance_v2.db")
SESSION_PATH = os.path.join(DATA_DIR, "session.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

CURRENCIES = ["PKR", "USD", "EUR", "GBP", "AED", "SAR", "INR", "CNY", "JPY", "CAD", "AUD"]
PAYMENT_METHODS = ["Cash", "JazzCash", "Bank Transfer", "Card", "Mobile Wallet", "Cheque", "Credit"]
UNITS = ["pcs", "kg", "g", "L", "mL", "m", "box", "dozen", "service"]
DEFAULT_LOW_STOCK = 5
WALK_IN = "Walk-in (no customer)"


def name_part(text):
    """The name from a picker label such as 'Ali Traders · 0300-1234567'. Plain names pass through."""
    return (text or "").split("·")[0].strip()

THEME_LABELS = {
    "midnight": "Midnight Indigo (dark)",
    "clean": "Clean Blue (light)",
    "sand": "Warm Sand (cream, teal bar)",
    "emerald": "Emerald Pro (dark green)",
}
DEFAULT_THEME = "midnight"
# Older builds stored "light" and "dark"; they map to the closest new theme.
LEGACY_THEMES = {"light": "clean", "dark": "midnight"}
THEMES = {
    "midnight": {
        "bg": "#0F111A", "card": "#181C2A", "fg": "#E8EBF5",
        "muted": "#8A92AA", "accent": "#818CF8", "accent_hover": "#6B7BF0",
        "accent_fg": "#FFFFFF", "entry": "#131621", "border": "#282E42",
        "row_alt": "#151926", "head": "#1E2334", "head_hover": "#282E44",
        "danger": "#F87171", "danger_hover": "#EF4444", "success": "#34D399",
        "warn": "#FBBF24", "chart": "#818CF8", "side": "#151824",
        "side_fg": "#8A92AA", "side_hover": "#1E2334", "side_active": "#818CF8",
        "side_active_fg": "#FFFFFF", "side_title": "#E8EBF5",
    },
    "clean": {
        "bg": "#F3F6FB", "card": "#FFFFFF", "fg": "#0F172A",
        "muted": "#64748B", "accent": "#2563EB", "accent_hover": "#1D4ED8",
        "accent_fg": "#FFFFFF", "entry": "#FFFFFF", "border": "#E2E8F0",
        "row_alt": "#F8FAFC", "head": "#F1F5F9", "head_hover": "#E2E8F0",
        "danger": "#DC2626", "danger_hover": "#B91C1C", "success": "#16A34A",
        "warn": "#D97706", "chart": "#3B82F6", "side": "#FFFFFF",
        "side_fg": "#64748B", "side_hover": "#F1F5F9", "side_active": "#2563EB",
        "side_active_fg": "#FFFFFF", "side_title": "#0F172A",
    },
    "sand": {
        "bg": "#F6F1E8", "card": "#FFFCF6", "fg": "#2C2A26",
        "muted": "#786E60", "accent": "#0F766E", "accent_hover": "#0D5F59",
        "accent_fg": "#FFFFFF", "entry": "#FFFFFF", "border": "#E8DECC",
        "row_alt": "#FAF6EE", "head": "#F3EADA", "head_hover": "#EADEC8",
        "danger": "#BE123C", "danger_hover": "#9F1239", "success": "#15803D",
        "warn": "#B45309", "chart": "#0F766E", "side": "#2C3E3A",
        "side_fg": "#BED6D0", "side_hover": "#384E48", "side_active": "#0F766E",
        "side_active_fg": "#FFFFFF", "side_title": "#FFFCF6",
    },
    "emerald": {
        "bg": "#090E0D", "card": "#101B19", "fg": "#E6F5F0",
        "muted": "#78A094", "accent": "#34D399", "accent_hover": "#10B981",
        "accent_fg": "#061410", "entry": "#0C1412", "border": "#1C342E",
        "row_alt": "#0D1614", "head": "#142420", "head_hover": "#1C302B",
        "danger": "#FB7185", "danger_hover": "#F43F5E", "success": "#34D399",
        "warn": "#FACC15", "chart": "#34D399", "side": "#0C1614",
        "side_fg": "#78A094", "side_hover": "#142420", "side_active": "#34D399",
        "side_active_fg": "#061410", "side_title": "#E6F5F0",
    },
}


def resource_path(*parts):
    """Path to a bundled file, both from source and when frozen by PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)
