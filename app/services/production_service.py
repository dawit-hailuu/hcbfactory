"""
Production service.

`calculate_consumption(product_id, qty)` returns a list of (material, needed_qty)
without touching the DB — used by the UI to preview before confirming.

`record_production(...)` runs the actual transaction:
  - inserts the production row
  - looks up the active formula
  - inserts a snapshot row per material into production_consumption
  - decrements raw material stock (via inventory_service.record_movement)
  - increments finished-product stock
all atomically.
"""
from app.database.db import get_connection
from app.services import product_service, inventory_service
from app.utils import clock


def calculate_consumption(product_id: int, quantity: float, on_date: str = None):
    """
    Return list of dicts {material_id, material_code, material_name, unit,
                          qty_per_unit, qty_needed, available, sufficient}
    for the given product + production quantity.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    formula = product_service.get_active_formula(product_id, on_date)
    materials = {m["id"]: m for m in inventory_service.list_materials()}

    result = []
    for mat_id, fdata in formula.items():
        needed = fdata["qty_per_unit"] * quantity
        mat = materials.get(mat_id, {})
        available = mat.get("current_stock", 0)
        result.append({
            "material_id":   mat_id,
            "material_code": fdata["material_code"],
            "material_name": fdata["material_name"],
            "unit":          fdata["unit"],
            "qty_per_unit":  fdata["qty_per_unit"],
            "qty_needed":    needed,
            "available":     available,
            "sufficient":    available >= needed,
        })
    # Sort for stable UI display
    result.sort(key=lambda r: r["material_name"])
    return result


def has_sufficient_materials(product_id: int, quantity: float):
    """Quick check: returns (bool ok, list of insufficient material names)."""
    consumption = calculate_consumption(product_id, quantity)
    short = [c["material_name"] for c in consumption if not c["sufficient"]]
    return (len(short) == 0, short)


def record_production(product_id: int, quantity: float, user_id: int = None,
                      note: str = None, made_by: str = None,
                      allow_negative_stock: bool = False):
    """
    Atomically:
      - insert production row
      - compute consumption from active formula
      - deduct each material via stock_movements ledger
      - snapshot consumption into production_consumption
      - increase finished-product stock

    `made_by` is the free-text name of the worker who physically made the blocks.
    Distinct from `user_id` which is who recorded the entry.

    Raises ValueError if materials insufficient (unless allow_negative_stock=True).
    Returns the new production_id.
    """
    if quantity <= 0:
        raise ValueError("production quantity must be positive")

    consumption = calculate_consumption(product_id, quantity)

    if not allow_negative_stock:
        short = [c for c in consumption if not c["sufficient"]]
        if short:
            names = ", ".join(f"{c['material_name']} (need {c['qty_needed']:.3f} "
                              f"{c['unit']}, have {c['available']:.3f})" for c in short)
            raise ValueError(f"Insufficient raw materials: {names}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Compute total material cost for this run (for profit tracking)
        material_costs = {
            r["id"]: r["unit_cost"] or 0
            for r in cur.execute("SELECT id, unit_cost FROM materials").fetchall()
        }
        cost_total = sum(c["qty_needed"] * material_costs.get(c["material_id"], 0)
                         for c in consumption)

        from app.services import voucher_service, audit_service
        voucher_no = voucher_service.next_voucher("PV", conn=conn)

        cur.execute(
            """INSERT INTO production
                 (product_id, quantity, user_id, note, made_by,
                  production_date, created_at, cost_total, voucher_no)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (product_id, quantity, user_id, note, made_by,
             clock.today(), clock.now(), cost_total, voucher_no),
        )
        production_id = cur.lastrowid

        # consume materials + snapshot
        for c in consumption:
            if c["qty_needed"] <= 0:
                continue
            inventory_service.record_movement(
                material_id=c["material_id"],
                qty=-c["qty_needed"],
                movement="production",
                user_id=user_id,
                reference=f"production#{production_id}",
                note=f"Used for {quantity} of product {product_id}",
                conn=conn,
            )
            cur.execute(
                """INSERT INTO production_consumption (production_id, material_id, qty_consumed)
                   VALUES (?,?,?)""",
                (production_id, c["material_id"], c["qty_needed"]),
            )

        # increment finished-product stock
        cur.execute("UPDATE products SET stock = stock + ? WHERE id = ?",
                    (quantity, product_id))

        conn.commit()
        audit_service.log(
            user_id, "production_create",
            f"{voucher_no} product_id={product_id} qty={quantity} made_by={made_by or '-'}"
        )
        return production_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_production(limit: int = 200, date_from: str = None, date_to: str = None,
                    include_deleted: bool = False):
    conn = get_connection()
    try:
        where = ["1=1"]
        params = []
        if not include_deleted:
            where.append("p.deleted_at IS NULL")
        if date_from:
            where.append("p.production_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("p.production_date <= ?")
            params.append(date_to)
        clause = "WHERE " + " AND ".join(where)
        params.append(limit)
        rows = conn.execute(
            f"""SELECT p.*, pr.code AS product_code, pr.name AS product_name,
                       pr.input_unit, u.username AS user_name
                FROM production p
                JOIN products pr ON pr.id = p.product_id
                LEFT JOIN users u ON u.id = p.user_id
                {clause}
                ORDER BY p.id DESC LIMIT ?""", params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_production(production_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT p.*, pr.code AS product_code, pr.name AS product_name,
                      pr.input_unit
                 FROM production p
                 JOIN products pr ON pr.id = p.product_id
                WHERE p.id = ?""",
            (production_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_production(production_id: int, user_id: int = None, reason: str = None):
    """Soft-delete a production run. Reverses the inventory effects:
    raw materials are added back, finished stock is reduced.
    Audit log records the reason. The original row stays in the DB with
    deleted_at set, so reports can still surface it if needed.
    """
    from app.services import audit_service
    conn = get_connection()
    try:
        cur = conn.cursor()
        prod = cur.execute(
            "SELECT * FROM production WHERE id = ? AND deleted_at IS NULL",
            (production_id,)
        ).fetchone()
        if prod is None:
            raise ValueError("Production run not found (or already deleted)")

        # Reverse the material consumption
        consumed = cur.execute(
            """SELECT material_id, qty_consumed FROM production_consumption
                WHERE production_id = ?""", (production_id,)
        ).fetchall()
        for c in consumed:
            inventory_service.record_movement(
                material_id=c["material_id"],
                qty=+c["qty_consumed"],
                movement="adjustment",
                user_id=user_id,
                reference=f"reverse_production#{production_id}",
                note=f"Reversal of deleted production run #{production_id}",
                conn=conn,
            )

        # Reduce finished product stock
        cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?",
                    (prod["quantity"], prod["product_id"]))

        # Soft-delete
        cur.execute("UPDATE production SET deleted_at = ? WHERE id = ?",
                    (clock.now(), production_id))
        conn.commit()
        audit_service.log(
            user_id, "production_delete",
            f"id={production_id} qty={prod['quantity']} reason={reason or '-'}"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_production(production_id: int, quantity: float = None,
                      made_by: str = None, note: str = None, user_id: int = None,
                      reason: str = None):
    """Edit a production run. The cleanest correct approach is to delete + re-create;
    we do that internally so material consumption and stock stay consistent.
    Returns the new production_id."""
    from app.services import audit_service
    existing = get_production(production_id)
    if existing is None:
        raise ValueError("Production run not found")
    if existing.get("deleted_at"):
        raise ValueError("Cannot edit a deleted production run")

    new_qty   = quantity if quantity is not None else existing["quantity"]
    new_made  = made_by if made_by is not None else existing.get("made_by")
    new_note  = note if note is not None else existing.get("note")

    # First reverse the original, then create the corrected version
    delete_production(production_id, user_id=user_id,
                      reason=f"edited{(' — ' + reason) if reason else ''}")
    new_id = record_production(
        product_id=existing["product_id"], quantity=new_qty,
        user_id=user_id, note=new_note, made_by=new_made,
    )
    audit_service.log(
        user_id, "production_edit",
        f"old_id={production_id} new_id={new_id} qty={existing['quantity']} -> {new_qty}"
    )
    return new_id


def recent_made_by(limit: int = 10):
    """Return the last `limit` distinct non-empty 'made_by' values,
    most-recently-used first. Used for autocomplete on the Production form."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT made_by, MAX(id) AS last_seen
               FROM production
               WHERE made_by IS NOT NULL AND TRIM(made_by) != ''
               GROUP BY made_by
               ORDER BY last_seen DESC
               LIMIT ?""", (limit,)
        ).fetchall()
        return [r["made_by"] for r in rows]
    finally:
        conn.close()


def production_consumption_detail(production_id: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT pc.qty_consumed, m.code, m.name, m.unit
               FROM production_consumption pc
               JOIN materials m ON m.id = pc.material_id
               WHERE pc.production_id = ?
               ORDER BY m.name""", (production_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
