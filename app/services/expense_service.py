"""
Expenses module: track operating expenses beyond raw materials.
Uses double-entry Voucher, JournalEntry, and Expense models.
"""
from datetime import datetime
from app.database.db import get_session, get_connection
from app.database.models import Expense, Voucher, JournalEntry
from app.services import ledger_service

CATEGORIES = ["Labor", "Utilities", "Rent", "Transport", "Maintenance", "Materials", "Other"]

def record_expense(category: str, amount: float, description: str = None,
                   expense_date: str = None, user_id: int = None):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    if category not in CATEGORIES:
        category = "Other"

    session = get_session()
    try:
        # 1. Create EV Voucher
        v = ledger_service.create_voucher(
            session=session,
            voucher_type="EV",
            created_by_id=user_id or 1,
            note=description
        )
        session.flush()

        # 2. Write to Expense table
        exp = Expense(
            category=category,
            amount=amount,
            description=description,
            expense_date=expense_date if expense_date else datetime.now().strftime("%Y-%m-%d"),
            user_id=user_id,
            voucher_no=v.voucher_no
        )
        session.add(exp)

        # 3. Post double-entry postings
        # Debit Operating Expenses (GL-5101)
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-5101 Operating Expenses",
            debit=amount,
            credit=0.0
        )
        # Credit Cash on Hand (GL-1101)
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-1101 Cash on Hand",
            debit=0.0,
            credit=amount
        )

        session.commit()
        return v.voucher_no
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def list_expenses(limit: int = 500, date_from: str = None, date_to: str = None):
    conn = get_connection()
    try:
        where = []
        params = []
        if date_from:
            where.append("e.expense_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("e.expense_date <= ?")
            params.append(date_to)

        clause = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT e.*, u.username AS user_name
            FROM expenses e
            LEFT JOIN users u ON u.id = e.user_id
            {clause}
            ORDER BY e.id DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def delete_expense(expense_id: int, user_id: int = None):
    """Voids the expense by voiding the linked voucher transactionally."""
    session = get_session()
    try:
        exp = session.query(Expense).filter_by(id=expense_id).first()
        if exp:
            # Find the associated Voucher
            v = session.query(Voucher).filter_by(voucher_no=exp.voucher_no).first()
            if v:
                # Void voucher reverses all double-entry and ledger entries!
                ledger_service.void_voucher(v.id, user_id or 1)
            
            # Delete the expense record
            session.delete(exp)
            session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

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
