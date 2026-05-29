"""Local-time helper. All record timestamps go through here."""
from datetime import datetime, date


def today() -> str:
    """YYYY-MM-DD in local time. Used for production_date, sale_date, etc."""
    return datetime.now().strftime("%Y-%m-%d")


def today_date() -> date:
    """Local date as a datetime.date object."""
    return datetime.now().date()


def now() -> str:
    """YYYY-MM-DD HH:MM:SS in local time. Used for created_at."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
