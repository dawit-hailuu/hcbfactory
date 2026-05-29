"""Sales service: records sales, tracks credit (amount_paid), supports edit/delete."""
from app.database.db import get_connection
from app.utils import clock


def _avg_unit_cost(conn, product_id: int) -> float:
    """Average material cost per finished unit, based on this product's production runs.
    Used to estimate cost-of-sale for profit reporting.

    Strategy: take all non-deleted production runs for the product, sum their
    cost_total / sum of qty produced. Falls back to 0 when no production data.
    """
    row = conn.execute(
        """SELECT COALESCE(SUM(cost_total), 0) AS tc,
                  COALESCE(SUM(quantity), 0)   AS tq
             FROM production
            WHERE product_id = ? AND deleted_at IS NULL""",
        (product_id,)
    ).fetchone()
    if not row or row["tq"] == 0:
        return 0.0
    return row["tc"] / row["tq"]


def record_sale(product_id: int, customer_name: str, quantity: float,
                unit_price: float, user_id: int = None, note: str = None,
                amount_paid: float = None,
                allow_negative_stock: bool = False):
    """Record a sale.

    `amount_paid` defaults to the full total (cash sale). Pass a smaller number
    for partial payment / credit sale. The balance shows up under the customer.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if unit_price < 0:
        raise ValueError("unit price cannot be negative")

    conn = get_connection()
    try:
        cur = conn.cursor()
        prod = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if prod is None:
            raise ValueError("product not found")
        if not allow_negative_stock and prod["stock"] < quantity:
            raise ValueError(f"Insufficient stock: have {prod['stock']}, need {quantity}")

        from app.services import voucher_service, audit_service
        voucher_no = voucher_service.next_voucher("SV", conn=conn)

        total = round(quantity * unit_price, 2)
        paid  = total if amount_paid is None else round(min(max(amount_paid, 0), total + 1e9), 2)
        cost_per_unit = _avg_unit_cost(conn, product_id)
        cost_total = round(quantity * cost_per_unit, 2)

        cur.execute(
            """INSERT INTO sales
                 (product_id, customer_name, quantity, unit_price, total,
                  user_id, note, sale_date, created_at,
                  amount_paid, cost_total, voucher_no)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (product_id, customer_name, quantity, unit_price, total,
             user_id, note, clock.today(), clock.now(),
             paid, cost_total, voucher_no),
        )
        sale_id = cur.lastrowid
        cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?",
                    (quantity, product_id))
        conn.commit()
        audit_service.log(
            user_id, "sale_create",
            f"{voucher_no} customer={customer_name or '-'} "
            f"qty={quantity} total={total} paid={paid}"
        )
        return sale_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_sales(limit: int = 200, date_from: str = None, date_to: str = None,
               include_deleted: bool = False):
    conn = get_connection()
    try:
        where = ["1=1"]
        params = []
        if not include_deleted:
            where.append("s.deleted_at IS NULL")
        if date_from:
            where.append("s.sale_date >= ?"); params.append(date_from)
        if date_to:
            where.append("s.sale_date <= ?"); params.append(date_to)
        clause = "WHERE " + " AND ".join(where)
        params.append(limit)
        rows = conn.execute(
            f"""SELECT s.*, p.code AS product_code, p.name AS product_name,
                       p.input_unit, u.username AS user_name,
                       (s.total - COALESCE(s.amount_paid, s.total)) AS balance
                FROM sales s
                JOIN products p ON p.id = s.product_id
                LEFT JOIN users u ON u.id = s.user_id
                {clause}
                ORDER BY s.id DESC LIMIT ?""", params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_sale(sale_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT s.*, p.code AS product_code, p.name AS product_name,
                      p.input_unit
                FROM sales s
                JOIN products p ON p.id = s.product_id
                WHERE s.id = ?""",
            (sale_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_sale(sale_id: int, user_id: int = None, reason: str = None):
    """Soft-delete a sale and add the stock back to finished products."""
    from app.services import audit_service
    conn = get_connection()
    try:
        cur = conn.cursor()
        sale = cur.execute(
            "SELECT * FROM sales WHERE id = ? AND deleted_at IS NULL",
            (sale_id,)
        ).fetchone()
        if sale is None:
            raise ValueError("Sale not found (or already deleted)")
        sale_d = dict(sale)

        cur.execute("UPDATE products SET stock = stock + ? WHERE id = ?",
                    (sale_d["quantity"], sale_d["product_id"]))
        cur.execute("UPDATE sales SET deleted_at = ? WHERE id = ?",
                    (clock.now(), sale_id))
        conn.commit()
        audit_service.log(
            user_id, "sale_delete",
            f"id={sale_id} customer={sale_d.get('customer_name') or '-'} "
            f"qty={sale_d['quantity']} total={sale_d['total']} reason={reason or '-'}"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_sale(sale_id: int, customer_name: str = None, quantity: float = None,
                unit_price: float = None, note: str = None, amount_paid: float = None,
                user_id: int = None, reason: str = None):
    """Edit a sale — implemented as soft-delete + re-create for inventory consistency."""
    from app.services import audit_service
    existing = get_sale(sale_id)
    if existing is None:
        raise ValueError("Sale not found")
    if existing.get("deleted_at"):
        raise ValueError("Cannot edit a deleted sale")

    new_cust  = customer_name if customer_name is not None else existing.get("customer_name")
    new_qty   = quantity if quantity is not None else existing["quantity"]
    new_price = unit_price if unit_price is not None else existing["unit_price"]
    new_note  = note if note is not None else existing.get("note")
    new_paid  = amount_paid if amount_paid is not None else existing.get("amount_paid")

    delete_sale(sale_id, user_id=user_id,
                reason=f"edited{(' — ' + reason) if reason else ''}")
    new_id = record_sale(
        product_id=existing["product_id"], customer_name=new_cust,
        quantity=new_qty, unit_price=new_price,
        user_id=user_id, note=new_note, amount_paid=new_paid,
    )
    audit_service.log(
        user_id, "sale_edit",
        f"old_id={sale_id} new_id={new_id} qty={existing['quantity']} -> {new_qty}"
    )
    return new_id


def daily_revenue(date: str = None):
    conn = get_connection()
    try:
        if date:
            row = conn.execute(
                """SELECT COALESCE(SUM(total),0) AS rev FROM sales
                    WHERE sale_date = ? AND deleted_at IS NULL""", (date,)
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT COALESCE(SUM(total),0) AS rev FROM sales
                    WHERE sale_date = date('now','localtime') AND deleted_at IS NULL"""
            ).fetchone()
        return row["rev"]
    finally:
        conn.close()


def daily_profit(date: str = None):
    """Gross profit (revenue - cost_total) for today or given date."""
    conn = get_connection()
    try:
        d = date or conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
        row = conn.execute(
            """SELECT COALESCE(SUM(total),0) AS rev,
                      COALESCE(SUM(cost_total),0) AS cost
                FROM sales
                WHERE sale_date = ? AND deleted_at IS NULL""", (d,)
        ).fetchone()
        return {"revenue": row["rev"], "cost": row["cost"],
                "profit": row["rev"] - row["cost"]}
    finally:
        conn.close()
