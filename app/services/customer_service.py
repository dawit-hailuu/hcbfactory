"""
Customer balances and payments.

We don't force customers to be registered. The system reads names directly
from sales and payments and aggregates a balance per name (case-insensitive).
Optionally an admin can create a customer record to add a phone / address.
"""
from app.database.db import get_connection
from app.utils import clock


def record_payment(customer_name: str, amount: float, method: str = None,
                   note: str = None, user_id: int = None):
    if amount <= 0:
        raise ValueError("Payment amount must be positive")
    if not customer_name or not customer_name.strip():
        raise ValueError("Customer name is required")
    from app.services import voucher_service, audit_service
    conn = get_connection()
    try:
        voucher_no = voucher_service.next_voucher("RV", conn=conn)
        conn.execute(
            """INSERT INTO customer_payments
                 (customer_name, amount, method, note, user_id,
                  payment_date, created_at, voucher_no)
               VALUES (?,?,?,?,?,?,?,?)""",
            (customer_name.strip(), amount, method, note, user_id,
             clock.today(), clock.now(), voucher_no),
        )
        conn.commit()
        audit_service.log(
            user_id, "payment_create",
            f"{voucher_no} customer={customer_name} amount={amount} method={method or '-'}"
        )
        return voucher_no
    finally:
        conn.close()


def customer_balances():
    """For every customer (across sales and payments), compute outstanding balance.
    balance = total_sold - amount_paid_on_sale - extra_payments
    A negative balance means the customer overpaid.
    """
    conn = get_connection()
    try:
        # Sales side: per-customer total billed and per-sale paid
        sale_rows = conn.execute(
            """SELECT COALESCE(NULLIF(TRIM(customer_name), ''), '(no name)') AS name,
                      SUM(total) AS billed,
                      SUM(COALESCE(amount_paid, total)) AS paid_on_sale,
                      COUNT(*) AS sale_count
                 FROM sales
                WHERE deleted_at IS NULL
             GROUP BY LOWER(name)"""
        ).fetchall()
        # Extra payments (e.g., to settle outstanding balance)
        pay_rows = conn.execute(
            """SELECT customer_name AS name, SUM(amount) AS extra
                 FROM customer_payments
             GROUP BY LOWER(customer_name)"""
        ).fetchall()
        extras = {(r["name"] or "").lower(): r["extra"] for r in pay_rows}

        out = []
        for s in sale_rows:
            billed = s["billed"] or 0
            paid_on_sale = s["paid_on_sale"] or 0
            extra = extras.get((s["name"] or "").lower(), 0)
            balance = billed - paid_on_sale - extra
            out.append({
                "name": s["name"],
                "billed": billed,
                "paid_on_sale": paid_on_sale,
                "extra_payments": extra,
                "balance": balance,
                "sale_count": s["sale_count"],
            })

        # Customers who only paid (and somehow have no sales) — show as credit balance
        sale_names = {(s["name"] or "").lower() for s in sale_rows}
        for r in pay_rows:
            key = (r["name"] or "").lower()
            if key not in sale_names:
                out.append({
                    "name": r["name"], "billed": 0, "paid_on_sale": 0,
                    "extra_payments": r["extra"], "balance": -(r["extra"] or 0),
                    "sale_count": 0,
                })
        out.sort(key=lambda x: -x["balance"])  # biggest debt first
        return out
    finally:
        conn.close()


def customer_statement(customer_name: str):
    """Combined timeline of sales and payments for one customer (by name, case-insensitive)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT 'sale' AS kind, s.sale_date AS date, s.id, s.total AS amount,
                      COALESCE(s.amount_paid, s.total) AS paid_now,
                      pr.code || ' x' || s.quantity AS detail
                 FROM sales s
                 JOIN products pr ON pr.id = s.product_id
                WHERE LOWER(COALESCE(s.customer_name,'')) = LOWER(?)
                  AND s.deleted_at IS NULL
                UNION ALL
               SELECT 'payment' AS kind, payment_date AS date, id,
                      amount, amount AS paid_now,
                      COALESCE(method, '') AS detail
                 FROM customer_payments
                WHERE LOWER(customer_name) = LOWER(?)
               ORDER BY date, id""",
            (customer_name, customer_name),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_payments(limit: int = 500, date_from: str = None, date_to: str = None):
    conn = get_connection()
    try:
        where, params = [], []
        if date_from:
            where.append("payment_date >= ?"); params.append(date_from)
        if date_to:
            where.append("payment_date <= ?"); params.append(date_to)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = conn.execute(
            f"""SELECT cp.*, u.username AS user_name
                  FROM customer_payments cp
             LEFT JOIN users u ON u.id = cp.user_id
                {clause}
              ORDER BY cp.id DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
