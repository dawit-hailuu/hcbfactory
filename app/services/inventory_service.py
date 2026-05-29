"""
Inventory service: raw materials, stock movements, low-stock alerts.

All stock changes go through `record_movement()` which:
  1) appends a row to stock_movements (full audit history)
  2) updates the cached current_stock on materials
in a single transaction.
"""
from app.database.db import get_connection
from app.utils import clock


def list_materials():
    """All materials with current cached stock."""
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM materials ORDER BY name"
        ).fetchall()]
    finally:
        conn.close()


def get_material(material_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def record_movement(material_id: int, qty: float, movement: str,
                    user_id: int = None, reference: str = None, note: str = None,
                    supplier_name: str = None, unit_cost: float = None,
                    conn=None):
    """
    Record a stock change.  qty is SIGNED:
      - positive for purchase / addition
      - negative for production consumption / adjustment down

    If `conn` is provided, runs inside the caller's transaction (used by
    production_service to keep production + consumption + stock atomic).
    Purchases auto-receive an MV-#### voucher number.
    """
    if movement not in ("purchase", "production", "adjustment", "initial"):
        raise ValueError(f"invalid movement type: {movement}")

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        voucher_no = None
        if movement == "purchase":
            from app.services import voucher_service
            voucher_no = voucher_service.next_voucher("MV", conn=conn)

        conn.execute(
            """INSERT INTO stock_movements
                 (material_id, qty, movement, reference, note, user_id,
                  created_at, supplier_name, unit_cost, voucher_no)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (material_id, qty, movement, reference, note, user_id,
             clock.now(), supplier_name, unit_cost, voucher_no),
        )
        conn.execute(
            "UPDATE materials SET current_stock = current_stock + ? WHERE id = ?",
            (qty, material_id),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def add_stock(material_id: int, qty: float, user_id: int = None,
              note: str = None, unit_cost: float = None,
              supplier_name: str = None):
    """User-facing 'add stock' (purchase or initial stocking)."""
    if qty <= 0:
        raise ValueError("Quantity to add must be positive")
    from app.services import audit_service
    conn = get_connection()
    try:
        record_movement(material_id, qty, "purchase",
                        user_id=user_id, note=note,
                        supplier_name=supplier_name, unit_cost=unit_cost,
                        conn=conn)
        if unit_cost is not None:
            conn.execute("UPDATE materials SET unit_cost = ? WHERE id = ?",
                         (unit_cost, material_id))
        conn.commit()
        # Get material name for audit
        m = conn.execute("SELECT code FROM materials WHERE id = ?",
                         (material_id,)).fetchone()
        audit_service.log(
            user_id, "stock_purchase",
            f"material={m['code'] if m else material_id} qty=+{qty} "
            f"unit_cost={unit_cost or '-'} supplier={supplier_name or '-'}"
        )
    finally:
        conn.close()


def adjust_stock(material_id: int, new_qty: float, user_id: int = None, note: str = None):
    """Set stock to an absolute value (e.g. after physical inventory count)."""
    from app.services import audit_service
    mat = get_material(material_id)
    if mat is None:
        raise ValueError("material not found")
    delta = new_qty - mat["current_stock"]
    if delta == 0:
        return
    record_movement(material_id, delta, "adjustment",
                    user_id=user_id, note=note or "manual adjustment")
    audit_service.log(
        user_id, "stock_adjust",
        f"material={mat['code']} from={mat['current_stock']} to={new_qty} "
        f"delta={delta:+.3f} note={note or '-'}"
    )


def stock_history(material_id: int = None, limit: int = 500):
    conn = get_connection()
    try:
        if material_id is None:
            rows = conn.execute(
                """SELECT sm.*, m.code AS material_code, m.name AS material_name, m.unit,
                          u.username AS user_name
                   FROM stock_movements sm
                   JOIN materials m ON m.id = sm.material_id
                   LEFT JOIN users u ON u.id = sm.user_id
                   ORDER BY sm.id DESC LIMIT ?""", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT sm.*, m.code AS material_code, m.name AS material_name, m.unit,
                          u.username AS user_name
                   FROM stock_movements sm
                   JOIN materials m ON m.id = sm.material_id
                   LEFT JOIN users u ON u.id = sm.user_id
                   WHERE sm.material_id = ?
                   ORDER BY sm.id DESC LIMIT ?""", (material_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def low_stock_materials():
    """Materials currently below or at their low-stock threshold."""
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM materials WHERE current_stock <= low_stock_alert ORDER BY name"
        ).fetchall()]
    finally:
        conn.close()


def update_material_settings(material_id: int, low_stock_alert: float = None,
                             unit_cost: float = None):
    conn = get_connection()
    try:
        if low_stock_alert is not None:
            conn.execute("UPDATE materials SET low_stock_alert = ? WHERE id = ?",
                         (low_stock_alert, material_id))
        if unit_cost is not None:
            conn.execute("UPDATE materials SET unit_cost = ? WHERE id = ?",
                         (unit_cost, material_id))
        conn.commit()
    finally:
        conn.close()


def distinct_suppliers():
    """Return distinct supplier names ever used in purchases, most recent first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT supplier_name, MAX(id) AS last_id
                 FROM stock_movements
                WHERE supplier_name IS NOT NULL AND TRIM(supplier_name) != ''
             GROUP BY supplier_name
             ORDER BY last_id DESC"""
        ).fetchall()
        return [r["supplier_name"] for r in rows]
    finally:
        conn.close()


def supplier_purchase_history(supplier_name: str, limit: int = 200):
    """All purchases from one supplier."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT sm.*, m.code AS material_code, m.name AS material_name, m.unit
                 FROM stock_movements sm
                 JOIN materials m ON m.id = sm.material_id
                WHERE sm.movement = 'purchase'
                  AND LOWER(COALESCE(sm.supplier_name,'')) = LOWER(?)
             ORDER BY sm.id DESC LIMIT ?""",
            (supplier_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
