"""
Production service.
Coordinates batch manufacturing logs, material consumption audits, 
and posts Production Vouchers directly to the double-entry ledger.
"""
from sqlalchemy import func
from app.database.db import get_session, get_connection
from app.database.models import Voucher, InventoryLedger, JournalEntry, Article, User
from app.services import product_service, inventory_service, ledger_service
from app.utils import clock
from datetime import datetime

def calculate_consumption(product_id: int, quantity: float, on_date: str = None):
    """
    Returns list of dicts {material_id, material_code, material_name, unit,
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
        available = mat.get("current_stock", 0.0)
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
    result.sort(key=lambda r: r["material_name"])
    return result

def has_sufficient_materials(product_id: int, quantity: float):
    consumption = calculate_consumption(product_id, quantity)
    short = [c["material_name"] for c in consumption if not c["sufficient"]]
    return (len(short) == 0, short)

def record_production(product_id: int, quantity: float, user_id: int = None,
                      note: str = None, made_by: str = None,
                      allow_negative_stock: bool = False):
    """
    Atomically creates a PRODUCTION Voucher, consumes raw materials, 
    increments finished blocks, and balances the accounting journal.
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

    session = get_session()
    try:
        prod_art = session.query(Article).filter_by(id=product_id).first()
        if not prod_art:
            raise ValueError("Product not found")

        # 1. Create Voucher Header
        v = ledger_service.create_voucher(
            session=session,
            voucher_type="PRODUCTION",
            created_by_id=user_id or 1
        )
        v.note = note
        v.made_by = made_by
        session.flush()

        # 2. Add Finished Product (Curing Yard / Warehouse)
        ledger_service.post_inventory_movement(
            session=session,
            voucher_id=v.id,
            article_id=product_id,
            qty_change=quantity,
            location="WAREHOUSE",
            cost_rate=prod_art.sell_price
        )

        # 3. Deduct consumed materials (Warehouse)
        total_material_cost = 0.0
        for c in consumption:
            if c["qty_needed"] <= 0:
                continue
            
            mat_art = session.query(Article).filter_by(id=c["material_id"]).first()
            cost_price = mat_art.cost_price or 0.0
            total_material_cost += c["qty_needed"] * cost_price
            
            ledger_service.post_inventory_movement(
                session=session,
                voucher_id=v.id,
                article_id=c["material_id"],
                qty_change=-c["qty_needed"],
                location="WAREHOUSE",
                cost_rate=cost_price
            )

        # 4. Balanced Journal Entry
        # Debit Finished Goods, Credit WIP/Raw Materials
        finished_valuation = quantity * prod_art.sell_price
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-1104 Finished Goods",
            debit=finished_valuation,
            credit=0.0
        )
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-1103 WIP Inventory",
            debit=0.0,
            credit=finished_valuation
        )

        session.commit()
        return v.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def list_production(limit: int = 200, date_from: str = None, date_to: str = None, offset: int = 0, include_deleted: bool = False):
    """Retrieves all manufacturing runs from Production Vouchers."""
    conn = get_connection()
    try:
        where = ["v.voucher_type = 'PRODUCTION'"]
        params = []
        
        if not include_deleted:
            where.append("v.state = 'POSTED'")
        if date_from:
            where.append("date(v.created_at) >= ?")
            params.append(date_from)
        if date_to:
            where.append("date(v.created_at) <= ?")
            params.append(date_to)
            
        clause = "WHERE " + " AND ".join(where)
        params.extend([limit, offset])

        # In a Production Voucher, the finished product addition is the positive ledger change.
        sql = f"""
            SELECT v.id, v.voucher_no, v.created_at, v.note, v.made_by, v.state,
                   datetime(v.created_at) AS created_at_str,
                   date(v.created_at) AS production_date,
                   u.username AS user_name, v.created_by_id AS user_id,
                   il.qty_change AS quantity,
                   a.id AS product_id, a.code AS product_code, a.name AS product_name, a.unit AS input_unit
             FROM vouchers v
             JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change > 0
             JOIN articles a ON a.id = il.article_id
             LEFT JOIN users u ON u.id = v.created_by_id
             {clause}
             ORDER BY v.id DESC LIMIT ? OFFSET ?
        """
        rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": r["id"],
                "voucher_no": r["voucher_no"],
                "product_id": r["product_id"],
                "product_code": r["product_code"],
                "product_name": r["product_name"],
                "input_unit": r["input_unit"],
                "quantity": r["quantity"],
                "production_date": r["production_date"],
                "created_at": r["created_at_str"],
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "made_by": r["made_by"],
                "note": r["note"],
                "state": r["state"]
            } for r in rows
        ]
    finally:
        conn.close()

def get_production(production_id: int):
    """Fetches details of a specific production run."""
    conn = get_connection()
    try:
        sql = """
            SELECT v.id, v.voucher_no, v.created_at, v.note, v.made_by, v.state,
                   datetime(v.created_at) AS created_at_str,
                   date(v.created_at) AS production_date,
                   u.username AS user_name, v.created_by_id AS user_id,
                   il.qty_change AS quantity,
                   a.id AS product_id, a.code AS product_code, a.name AS product_name, a.unit AS input_unit
             FROM vouchers v
             JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change > 0
             JOIN articles a ON a.id = il.article_id
             LEFT JOIN users u ON u.id = v.created_by_id
             WHERE v.id = ?
        """
        r = conn.execute(sql, (production_id,)).fetchone()
        if r:
            return {
                "id": r["id"],
                "voucher_no": r["voucher_no"],
                "product_id": r["product_id"],
                "product_code": r["product_code"],
                "product_name": r["product_name"],
                "input_unit": r["input_unit"],
                "quantity": r["quantity"],
                "production_date": r["production_date"],
                "created_at": r["created_at_str"],
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "made_by": r["made_by"],
                "note": r["note"],
                "state": r["state"]
            }
        return None
    finally:
        conn.close()

def delete_production(production_id: int, user_id: int = None, reason: str = None):
    """Voids the production run voucher transactionally."""
    ledger_service.void_voucher(production_id, user_id or 1)

def update_production(production_id: int, quantity: float = None,
                      made_by: str = None, note: str = None, user_id: int = None,
                      reason: str = None):
    """Edits a production run by voiding the old voucher and creating a new one."""
    existing = get_production(production_id)
    if existing is None:
        raise ValueError("Production run not found")
    if existing.get("state") == "VOIDED":
        raise ValueError("Cannot edit a voided production run")

    new_qty = quantity if quantity is not None else existing["quantity"]
    new_made = made_by if made_by is not None else existing.get("made_by")
    new_note = note if note is not None else existing.get("note")

    # 1. Void the existing production run
    delete_production(production_id, user_id=user_id, reason=reason)

    # 2. Record the corrected production run
    return record_production(
        product_id=existing["product_id"],
        quantity=new_qty,
        user_id=user_id,
        note=new_note,
        made_by=new_made,
        allow_negative_stock=True
    )

def recent_made_by(limit: int = 10):
    """Retrieves unique operator/worker names from recent production logs."""
    session = get_session()
    try:
        rows = session.query(
            Voucher.made_by,
            func.max(Voucher.id).label("last_seen")
        ).filter(
            Voucher.voucher_type == "PRODUCTION",
            Voucher.made_by != None,
            Voucher.made_by != ""
        ).group_by(Voucher.made_by).order_by(
            func.max(Voucher.id).desc()
        ).limit(limit).all()
        return [r[0] for r in rows]
    finally:
        session.close()

def production_consumption_detail(production_id: int):
    """Retrieves material deductions for a specific Production Voucher."""
    conn = get_connection()
    try:
        sql = """
            SELECT ABS(il.qty_change) AS qty_consumed, a.code, a.name, a.unit
            FROM inventory_ledger il
            JOIN articles a ON a.id = il.article_id
            WHERE il.voucher_id = ? AND il.qty_change < 0
            ORDER BY a.name
        """
        rows = conn.execute(sql, (production_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
