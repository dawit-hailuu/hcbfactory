"""
Damaged / wasted finished goods.

Recording waste:
  - inserts a row in `waste`
  - reduces the corresponding product's finished stock
  - does NOT touch raw materials (they were already consumed)
"""
from app.database.db import get_connection
from app.services import audit_service
from app.utils import clock


def record_waste(product_id: int, quantity: float, reason: str = None,
                 note: str = None, user_id: int = None,
                 allow_negative_stock: bool = False):
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    conn = get_connection()
    try:
        cur = conn.cursor()
        prod = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if prod is None:
            raise ValueError("Product not found")
        if not allow_negative_stock and prod["stock"] < quantity:
            raise ValueError(
                f"Insufficient finished stock: have {prod['stock']}, attempting to waste {quantity}"
            )
        from app.services import voucher_service
        voucher_no = voucher_service.next_voucher("WV", conn=conn)
        cur.execute(
            """INSERT INTO waste
                 (product_id, quantity, reason, note, user_id,
                  waste_date, created_at, voucher_no)
               VALUES (?,?,?,?,?,?,?,?)""",
            (product_id, quantity, reason, note, user_id,
             clock.today(), clock.now(), voucher_no),
        )
        waste_id = cur.lastrowid
        cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?",
                    (quantity, product_id))
        conn.commit()
        audit_service.log(user_id, "waste_record",
                          f"{voucher_no} product={prod['code']} qty={quantity} "
                          f"reason={reason or '-'}")
        return waste_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_waste(date_from: str = None, date_to: str = None, limit: int = 500):
    conn = get_connection()
    try:
        where, params = [], []
        if date_from:
            where.append("w.waste_date >= ?"); params.append(date_from)
        if date_to:
            where.append("w.waste_date <= ?"); params.append(date_to)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = conn.execute(
            f"""SELECT w.*, pr.code AS product_code, pr.name AS product_name,
                       pr.input_unit, pr.category, u.username AS user_name
                  FROM waste w
                  JOIN products pr ON pr.id = w.product_id
             LEFT JOIN users u ON u.id = w.user_id
                {clause}
              ORDER BY w.id DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def waste_summary(date_from: str, date_to: str):
    """Per-product waste totals over a period — for reports."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT pr.code, pr.name, pr.category, pr.input_unit,
                      SUM(w.quantity) AS total_waste,
                      COUNT(*) AS waste_events
                 FROM waste w
                 JOIN products pr ON pr.id = w.product_id
                WHERE w.waste_date BETWEEN ? AND ?
             GROUP BY pr.code, pr.name, pr.category, pr.input_unit
             ORDER BY pr.category, pr.code""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
