"""
Product & formula service.

Formulas are stored per (product, material) and are versioned by effective_from.
The 'active' formula for a product on a given date is the one with the latest
effective_from <= that date.
"""
from app.database.db import get_connection
from app.utils import clock


def list_products(category: str = None):
    conn = get_connection()
    try:
        if category:
            rows = conn.execute(
                "SELECT * FROM products WHERE category = ? ORDER BY code", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM products ORDER BY category, code").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_product(product_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_product_by_code(code: str):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM products WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_product(product_id: int, sell_price: float = None,
                   low_stock_alert: float = None, name: str = None):
    from app.services import audit_service
    # Validate
    if sell_price is not None and sell_price < 0:
        raise ValueError("Sell price cannot be negative")
    if low_stock_alert is not None and low_stock_alert < 0:
        raise ValueError("Low-stock alert cannot be negative")
    if name is not None and not name.strip():
        raise ValueError("Product name cannot be empty")
    conn = get_connection()
    try:
        old = conn.execute("SELECT code, sell_price, name, low_stock_alert FROM products WHERE id=?",
                           (product_id,)).fetchone()
        changes = []
        if sell_price is not None:
            conn.execute("UPDATE products SET sell_price = ? WHERE id = ?",
                         (sell_price, product_id))
            if old and abs((old["sell_price"] or 0) - sell_price) > 1e-9:
                changes.append(f"price {old['sell_price']}->{sell_price}")
        if low_stock_alert is not None:
            conn.execute("UPDATE products SET low_stock_alert = ? WHERE id = ?",
                         (low_stock_alert, product_id))
            if old and (old["low_stock_alert"] or 0) != low_stock_alert:
                changes.append(f"alert {old['low_stock_alert']}->{low_stock_alert}")
        if name is not None:
            conn.execute("UPDATE products SET name = ? WHERE id = ?", (name, product_id))
            if old and old["name"] != name:
                changes.append(f"name '{old['name']}'->'{name}'")
        conn.commit()
        if changes and old:
            audit_service.log(None, "product_update",
                              f"code={old['code']} {' | '.join(changes)}")
    finally:
        conn.close()


def get_active_formula(product_id: int, on_date: str = None):
    """
    Return a dict {material_id: {qty_per_unit, material_code, material_name, unit}}
    representing the formula in effect on the given date (default = today).
    Uses the latest effective_from <= on_date for each material.
    """
    conn = get_connection()
    try:
        if on_date is None:
            on_date_clause = "date('now','localtime')"
            params = (product_id,)
        else:
            on_date_clause = "?"
            params = (product_id, on_date)

        sql = f"""
        SELECT f.material_id, f.qty_per_unit, m.code AS material_code,
               m.name AS material_name, m.unit
        FROM formulas f
        JOIN materials m ON m.id = f.material_id
        WHERE f.product_id = ?
          AND f.effective_from = (
              SELECT MAX(effective_from) FROM formulas f2
              WHERE f2.product_id = f.product_id
                AND f2.material_id = f.material_id
                AND f2.effective_from <= {on_date_clause}
          )
        """
        rows = conn.execute(sql, params).fetchall()
        return {r["material_id"]: dict(r) for r in rows}
    finally:
        conn.close()


def list_formulas_for_product(product_id: int):
    """Return current (latest) formula rows for the Admin > Formulas table."""
    active = get_active_formula(product_id)
    return list(active.values())


def upsert_formula(product_id: int, material_id: int, qty_per_unit: float):
    """
    Insert a new formula version effective today.  If a row already exists for
    (product, material, today) we update it in place so rapid edits don't
    create dozens of rows.
    """
    if qty_per_unit < 0:
        raise ValueError("formula quantity cannot be negative")
    from app.services import audit_service
    today = clock.today()
    conn = get_connection()
    try:
        ctx = conn.execute(
            """SELECT p.code AS prod_code, m.code AS mat_code
                 FROM products p, materials m
                WHERE p.id = ? AND m.id = ?""",
            (product_id, material_id),
        ).fetchone()
        existing = conn.execute(
            """SELECT id, qty_per_unit FROM formulas
               WHERE product_id = ? AND material_id = ?
                 AND effective_from = ?""",
            (product_id, material_id, today),
        ).fetchone()
        if existing:
            old_qty = existing["qty_per_unit"]
            conn.execute("UPDATE formulas SET qty_per_unit = ? WHERE id = ?",
                         (qty_per_unit, existing["id"]))
            if ctx and abs(old_qty - qty_per_unit) > 1e-9:
                audit_service.log(
                    None, "formula_update",
                    f"{ctx['prod_code']}/{ctx['mat_code']} {old_qty}->{qty_per_unit}"
                )
        else:
            conn.execute(
                """INSERT INTO formulas (product_id, material_id, qty_per_unit, effective_from)
                   VALUES (?,?,?,?)""",
                (product_id, material_id, qty_per_unit, today),
            )
            if ctx:
                audit_service.log(
                    None, "formula_create",
                    f"{ctx['prod_code']}/{ctx['mat_code']} qty={qty_per_unit}"
                )
        conn.commit()
    finally:
        conn.close()
