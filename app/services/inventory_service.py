"""
Inventory service: raw materials, stock movements, and low-stock alerts.
Bridged to the unified 'articles' table and double-entry ledger.
"""
from app.database.db import get_session, get_connection
from app.database.models import Article, Voucher, InventoryLedger, JournalEntry
from app.services import ledger_service
from app.utils import clock
from datetime import datetime


def list_materials():
    """All raw materials with cached stock."""
    session = get_session()
    try:
        materials = session.query(Article).filter(
            Article.category == "RAW",
            Article.is_active == True
        ).order_by(Article.name).all()
        return [
            {
                "id": m.id,
                "code": m.code,
                "name": m.name,
                "unit": m.unit,
                "current_stock": m.warehouse_qty,
                "low_stock_alert": m.low_stock_alert,
                "unit_cost": m.cost_price
            } for m in materials
        ]
    finally:
        session.close()


def get_material(material_id: int):
    session = get_session()
    try:
        m = session.query(Article).filter(
            Article.id == material_id,
            Article.category == "RAW"
        ).first()
        if m:
            return {
                "id": m.id,
                "code": m.code,
                "name": m.name,
                "unit": m.unit,
                "current_stock": m.warehouse_qty,
                "low_stock_alert": m.low_stock_alert,
                "unit_cost": m.cost_price
            }
        return None
    finally:
        session.close()


def record_movement(material_id: int, qty: float, movement: str,
                    user_id: int = None, reference: str = None, note: str = None,
                    session=None):
    """
    Record a raw material stock change inside the double-entry ledger.
    Grounded in ledger_service. Supports session share for atomic operations.
    """
    if movement not in ("purchase", "production", "adjustment", "initial", "disposal"):
        raise ValueError(f"invalid movement type: {movement}")

    own_session = session is None
    if own_session:
        session = get_session()
        
    try:
        # Resolve voucher type
        v_type = "SRV" if movement == "purchase" else "ADJUSTMENT"
        if movement == "production":
            v_type = "PRODUCTION"
        elif movement == "disposal":
            v_type = "SIV"
            
        # 1. Create Voucher (if not inside an active parent transaction already)
        v = ledger_service.create_voucher(
            session=session,
            voucher_type=v_type,
            created_by_id=user_id or 1
        )
        v.note = note
        session.flush()
        
        # 2. Append Inventory Ledger
        ledger_service.post_inventory_movement(
            session=session,
            voucher_id=v.id,
            article_id=material_id,
            qty_change=qty,
            location="WAREHOUSE",
            cost_rate=0.0
        )
        
        # 3. Balanced Journal Entry
        art = session.query(Article).filter_by(id=material_id).first()
        val = abs(qty) * (art.cost_price or 0.0)
        account = "GL-1102 Raw Stock"
        offset = "GL-2101 Accounts Payable" if v_type == "SRV" else "GL-5109 Stock Variance"
        
        if qty >= 0:
            ledger_service.post_journal_entry(session, v.id, account, val, 0.0)
            ledger_service.post_journal_entry(session, v.id, offset, 0.0, val)
        else:
            ledger_service.post_journal_entry(session, v.id, offset, val, 0.0)
            ledger_service.post_journal_entry(session, v.id, account, 0.0, val)
            
        if own_session:
            session.commit()
    except Exception as e:
        if own_session:
            session.rollback()
        raise e
    finally:
        if own_session:
            session.close()


def add_stock(material_id: int, qty: float, user_id: int = None,
              note: str = None, unit_cost: float = None):
    """User-facing 'add stock' (purchase) posting an SRV Voucher."""
    if qty <= 0:
        raise ValueError("Quantity to add must be positive")
        
    session = get_session()
    try:
        art = session.query(Article).filter_by(id=material_id).first()
        if not art:
            raise ValueError("Material not found")
            
        # Update cost rate if provided
        if unit_cost is not None:
            art.cost_price = unit_cost
            
        record_movement(material_id, qty, "purchase",
                        user_id=user_id, note=note, session=session)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def issue_stock(material_id: int, qty: float, user_id: int = None, note: str = None):
    """User-facing 'issue stock' (disposal/waste) posting an SIV Voucher."""
    if qty <= 0:
        raise ValueError("Quantity to issue must be positive")
        
    session = get_session()
    try:
        art = session.query(Article).filter_by(id=material_id).first()
        if not art:
            raise ValueError("Material not found")
            
        if art.warehouse_qty < qty:
            raise ValueError(f"Insufficient stock: have {art.warehouse_qty:.3f}, need {qty:.3f}")
            
        record_movement(material_id, -qty, "disposal",
                        user_id=user_id, note=note or "Material issue/disposal", session=session)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def adjust_stock(material_id: int, new_qty: float, user_id: int = None, note: str = None):
    """Set raw material stock to physical count using a Stock Adjustment Voucher."""
    session = get_session()
    try:
        art = session.query(Article).filter_by(id=material_id).first()
        if not art:
            raise ValueError("Material not found")
            
        delta = new_qty - (art.warehouse_qty or 0.0)
        if delta == 0:
            return
            
        record_movement(material_id, delta, "adjustment",
                        user_id=user_id, note=note or "manual adjustment", session=session)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def stock_history(material_id: int = None, limit: int = 500, offset: int = 0):
    """Retrieves physical movement history from the new inventory ledger."""
    conn = get_connection()
    try:
        where = ["a.category = 'RAW'"]
        params = []
        if material_id is not None:
            where.append("il.article_id = ?")
            params.append(material_id)
            
        clause = "WHERE " + " AND ".join(where)
        params.extend([limit, offset])
        
        sql = f"""
            SELECT il.id, il.qty_change AS qty, il.location,
                   v.voucher_type AS movement, v.voucher_no AS reference,
                   v.created_at, u.username AS user_name,
                   a.code AS material_code, a.name AS material_name, a.unit
            FROM inventory_ledger il
            JOIN vouchers v ON v.id = il.voucher_id
            JOIN articles a ON a.id = il.article_id
            LEFT JOIN users u ON u.id = v.created_by_id
            {clause}
            ORDER BY il.id DESC LIMIT ? OFFSET ?
        """
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def low_stock_materials():
    """Raw materials below alert threshold."""
    session = get_session()
    try:
        mats = session.query(Article).filter(
            Article.category == "RAW",
            Article.warehouse_qty <= Article.low_stock_alert,
            Article.is_active == True
        ).order_by(Article.name).all()
        return [
            {
                "id": m.id,
                "code": m.code,
                "name": m.name,
                "unit": m.unit,
                "current_stock": m.warehouse_qty,
                "low_stock_alert": m.low_stock_alert,
                "unit_cost": m.cost_price
            } for m in mats
        ]
    finally:
        session.close()


def update_material_settings(material_id: int, low_stock_alert: float = None,
                              unit_cost: float = None):
    session = get_session()
    try:
        art = session.query(Article).filter_by(id=material_id).first()
        if art:
            if low_stock_alert is not None:
                art.low_stock_alert = low_stock_alert
            if unit_cost is not None:
                art.cost_price = unit_cost
            session.commit()
    finally:
        session.close()
