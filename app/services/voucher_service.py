"""
Voucher number generator.

Each transactional table holds its own voucher prefix and the next number is
the max existing number + 1. This is simple, race-free for the single-user
offline case, and avoids a separate counter table that could drift.

Prefixes:
  SV  Sales Voucher
  RV  Receipt Voucher (customer payment in)
  EV  Expense Voucher
  PV  Production Voucher
  WV  Waste Voucher
  MV  Material/Purchase Voucher (raw material in)
"""
import re
from app.database.db import get_connection


PREFIX_TABLES = {
    "SV": ("sales",             None),
    "RV": ("customer_payments", None),
    "EV": ("expenses",          None),
    "PV": ("production",        None),
    "WV": ("waste",             None),
    "MV": ("stock_movements",   "movement='purchase'"),
}


def next_voucher(prefix: str, conn=None) -> str:
    """Return next available voucher number like 'SV-00042'.

    If `conn` is provided, runs in caller's transaction (use this when the
    voucher must be assigned in the same transaction that inserts the row,
    so two concurrent inserts can't get the same number).
    """
    if prefix not in PREFIX_TABLES:
        raise ValueError(f"unknown voucher prefix: {prefix}")
    table, extra_where = PREFIX_TABLES[prefix]
    where = f"voucher_no LIKE '{prefix}-%'"
    if extra_where:
        where += f" AND {extra_where}"

    own = conn is None
    if own:
        conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT voucher_no FROM {table} WHERE {where}"
        ).fetchall()
        max_n = 0
        for r in rows:
            v = r["voucher_no"]
            m = re.match(rf"^{prefix}-(\d+)$", v or "")
            if m:
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
        return f"{prefix}-{max_n + 1:05d}"
    finally:
        if own:
            conn.close()
