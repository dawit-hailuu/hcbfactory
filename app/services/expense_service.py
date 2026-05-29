"""Expenses module: track operating expenses beyond raw materials."""
from app.database.db import get_connection
from app.utils import clock


CATEGORIES = ["Labor", "Utilities", "Rent", "Transport", "Maintenance", "Materials", "Other"]


def record_expense(category: str, amount: float, description: str = None,
                   expense_date: str = None, user_id: int = None):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    if category not in CATEGORIES:
        # don't reject, but normalize
        category = "Other"
    from app.services import voucher_service, audit_service
    conn = get_connection()
    try:
        voucher_no = voucher_service.next_voucher("EV", conn=conn)
        conn.execute(
            """INSERT INTO expenses
                 (category, amount, description, expense_date, user_id,
                  created_at, voucher_no)
               VALUES (?,?,?,?,?,?,?)""",
            (category, amount, description, expense_date or clock.today(),
             user_id, clock.now(), voucher_no),
        )
        conn.commit()
        audit_service.log(
            user_id, "expense_create",
            f"{voucher_no} {category} amount={amount} desc={description or '-'}"
        )
        return voucher_no
    finally:
        conn.close()


def list_expenses(limit: int = 500, date_from: str = None, date_to: str = None):
    conn = get_connection()
    try:
        where, params = [], []
        if date_from:
            where.append("e.expense_date >= ?"); params.append(date_from)
        if date_to:
            where.append("e.expense_date <= ?"); params.append(date_to)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = conn.execute(
            f"""SELECT e.*, u.username AS user_name
                  FROM expenses e
             LEFT JOIN users u ON u.id = e.user_id
                {clause}
              ORDER BY e.id DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_expense(expense_id: int, user_id: int = None):
    from app.services import audit_service
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            conn.commit()
            audit_service.log(user_id, "expense_delete",
                              f"id={expense_id} amt={row['amount']} cat={row['category']}")
    finally:
        conn.close()


def expense_summary(date_from: str, date_to: str):
    """Per-category totals."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT category, SUM(amount) AS total, COUNT(*) AS count
                 FROM expenses
                WHERE expense_date BETWEEN ? AND ?
             GROUP BY category
             ORDER BY total DESC""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def total_expenses(date_from: str, date_to: str) -> float:
    conn = get_connection()
    try:
        r = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS s FROM expenses WHERE expense_date BETWEEN ? AND ?",
            (date_from, date_to),
        ).fetchone()
        return r["s"] or 0
    finally:
        conn.close()
