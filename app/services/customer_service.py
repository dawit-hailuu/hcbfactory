"""
Customer balances and payments.
Queries our unified double-entry Voucher, JournalEntry, and Customer/CustomerPayment tables.
"""
from datetime import datetime
from sqlalchemy import func
from app.database.db import get_session, get_connection
from app.database.models import Customer, CustomerPayment, Voucher, JournalEntry, InventoryLedger, Article
from app.services import ledger_service

def record_payment(customer_name: str, amount: float, method: str = "cash",
                   note: str = None, user_id: int = None):
    if amount <= 0:
        raise ValueError("Payment amount must be positive")
    if not customer_name or not customer_name.strip():
        raise ValueError("Customer name is required")

    session = get_session()
    try:
        # Normalize name
        cust_name = customer_name.strip()

        # 1. Create CRV Voucher
        v = ledger_service.create_voucher(
            session=session,
            voucher_type="CRV",
            created_by_id=user_id or 1,
            note=note,
            customer_name=cust_name
        )
        session.flush()

        # 2. Write to CustomerPayment table
        pay = CustomerPayment(
            customer_name=cust_name,
            amount=amount,
            payment_date=datetime.now().strftime("%Y-%m-%d"),
            method=method,
            note=note,
            user_id=user_id,
            voucher_no=v.voucher_no
        )
        session.add(pay)

        # 3. Post double-entry accounting entries
        # Debit Cash (GL-1101) or Bank (GL-1102) depending on method
        cash_or_bank = "GL-1102 Bank" if method and "bank" in method.lower() else "GL-1101 Cash on Hand"
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code=cash_or_bank,
            debit=amount,
            credit=0.0
        )
        # Credit Accounts Receivable (GL-1105)
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-1105 Accounts Receivable",
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

def customer_balances():
    """
    Computes total billed, paid_on_sale, extra_payments, and net outstanding balance per customer.
    Groups dynamically by customer name.
    """
    conn = get_connection()
    try:
        # Query sales
        sales_sql = """
            SELECT LOWER(TRIM(v.customer_name)) AS key_name,
                   MAX(v.customer_name) AS display_name,
                   SUM(je_rev.credit) AS billed,
                   SUM(COALESCE(je_cash.debit, 0.0)) AS paid_on_sale,
                   COUNT(DISTINCT v.id) AS sale_count
            FROM vouchers v
            JOIN journal_entries je_rev ON je_rev.voucher_id = v.id AND je_rev.account_code = 'GL-4101 Sales Revenue'
            LEFT JOIN journal_entries je_cash ON je_cash.voucher_id = v.id AND je_cash.account_code = 'GL-1101 Cash on Hand'
            WHERE v.voucher_type IN ('CASH_SALE', 'CREDIT_SALE') AND v.state = 'POSTED'
            GROUP BY key_name
        """
        sales = conn.execute(sales_sql).fetchall()

        # Query extra payments
        payments_sql = """
            SELECT LOWER(TRIM(v.customer_name)) AS key_name,
                   MAX(v.customer_name) AS display_name,
                   SUM(je.debit) AS extra
            FROM vouchers v
            JOIN journal_entries je ON je.voucher_id = v.id AND je.account_code IN ('GL-1101 Cash on Hand', 'GL-1102 Bank')
            WHERE v.voucher_type = 'CRV' AND v.state = 'POSTED'
            GROUP BY key_name
        """
        payments = conn.execute(payments_sql).fetchall()
        extras = {p["key_name"]: p["extra"] for p in payments}

        # Query registered customer details to enrich
        custs_sql = """
            SELECT LOWER(TRIM(name)) AS key_name, phone, address, note
            FROM customers
        """
        custs_rows = conn.execute(custs_sql).fetchall()
        cust_profiles = {c["key_name"]: {"phone": c["phone"], "address": c["address"], "note": c["note"]} for c in custs_rows}

        results = {}
        for s in sales:
            k = s["key_name"]
            if not k:
                k = "(no name)"
            billed = s["billed"] or 0.0
            paid_on_sale = s["paid_on_sale"] or 0.0
            extra = extras.get(k, 0.0)
            balance = billed - paid_on_sale - extra
            profile = cust_profiles.get(k, {"phone": "", "address": "", "note": ""})

            results[k] = {
                "name": s["display_name"] or "Walk-in Customer",
                "billed": billed,
                "paid_on_sale": paid_on_sale,
                "extra_payments": extra,
                "balance": round(balance, 2),
                "sale_count": s["sale_count"],
                "phone": profile["phone"],
                "address": profile["address"],
                "note": profile["note"]
            }

        # Catch customers who only have payments
        for p in payments:
            k = p["key_name"]
            if not k:
                continue
            if k not in results:
                profile = cust_profiles.get(k, {"phone": "", "address": "", "note": ""})
                results[k] = {
                    "name": p["display_name"] or k.title(),
                    "billed": 0.0,
                    "paid_on_sale": 0.0,
                    "extra_payments": p["extra"],
                    "balance": round(-p["extra"], 2),
                    "sale_count": 0,
                    "phone": profile["phone"],
                    "address": profile["address"],
                    "note": profile["note"]
                }

        out = list(results.values())
        out.sort(key=lambda x: -x["balance"])
        return out
    finally:
        conn.close()

def customer_statement(customer_name: str):
    """Combined timeline of sales and payments for a customer (case-insensitive)."""
    conn = get_connection()
    try:
        # Sales timeline
        sales_sql = """
            SELECT 'sale' AS kind,
                   date(v.created_at) AS date,
                   v.id,
                   je_rev.credit AS amount,
                   COALESCE(je_cash.debit, 0.0) AS paid_now,
                   (a.code || ' x' || ABS(il.qty_change)) AS detail
            FROM vouchers v
            JOIN journal_entries je_rev ON je_rev.voucher_id = v.id AND je_rev.account_code = 'GL-4101 Sales Revenue'
            LEFT JOIN journal_entries je_cash ON je_cash.voucher_id = v.id AND je_cash.account_code = 'GL-1101 Cash on Hand'
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0
            JOIN articles a ON a.id = il.article_id
            WHERE LOWER(TRIM(v.customer_name)) = LOWER(TRIM(?)) AND v.state = 'POSTED'
        """
        sales_rows = conn.execute(sales_sql, (customer_name,)).fetchall()

        # Payments timeline
        payments_sql = """
            SELECT 'payment' AS kind,
                   date(v.created_at) AS date,
                   v.id,
                   je.debit AS amount,
                   je.debit AS paid_now,
                   v.voucher_no AS detail
            FROM vouchers v
            JOIN journal_entries je ON je.voucher_id = v.id AND je.account_code IN ('GL-1101 Cash on Hand', 'GL-1102 Bank')
            WHERE v.voucher_type = 'CRV' AND LOWER(TRIM(v.customer_name)) = LOWER(TRIM(?)) AND v.state = 'POSTED'
        """
        payments_rows = conn.execute(payments_sql, (customer_name,)).fetchall()

        combined = [dict(r) for r in sales_rows] + [dict(r) for r in payments_rows]
        combined.sort(key=lambda x: (x["date"], x["id"]))
        return combined
    finally:
        conn.close()

def list_payments(limit: int = 500, date_from: str = None, date_to: str = None):
    conn = get_connection()
    try:
        where = []
        params = []
        if date_from:
            where.append("payment_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("payment_date <= ?")
            params.append(date_to)
        
        clause = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT cp.*, u.username AS user_name
            FROM customer_payments cp
            LEFT JOIN users u ON u.id = cp.user_id
            {clause}
            ORDER BY cp.id DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
