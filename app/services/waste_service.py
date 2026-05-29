"""
Damaged / wasted finished goods.
Uses double-entry Voucher, InventoryLedger, JournalEntry, and Waste models.
"""
from datetime import datetime
from app.database.db import get_session, get_connection
from app.database.models import Waste, Voucher, JournalEntry, Article
from app.services import ledger_service

def record_waste(product_id: int, quantity: float, reason: str = None,
                 note: str = None, user_id: int = None,
                 allow_negative_stock: bool = False):
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    session = get_session()
    try:
        prod = session.query(Article).filter_by(id=product_id).first()
        if prod is None:
            raise ValueError("Product not found")

        current_stock = prod.shop_floor_qty or 0.0
        if not allow_negative_stock and current_stock < quantity:
            raise ValueError(
                f"Insufficient finished stock: have {current_stock}, attempting to waste {quantity}"
            )

        # 1. Create WV Voucher
        v = ledger_service.create_voucher(
            session=session,
            voucher_type="WV",
            created_by_id=user_id or 1,
            note=note
        )
        session.flush()

        # 2. Write to Waste table
        w = Waste(
            product_id=product_id,
            quantity=quantity,
            reason=reason,
            note=note,
            user_id=user_id,
            waste_date=datetime.now().strftime("%Y-%m-%d"),
            voucher_no=v.voucher_no
        )
        session.add(w)

        # 3. Post physical inventory movement (deduct quantity at SHOP_FLOOR)
        cost_rate = prod.cost_price or 0.0
        ledger_service.post_inventory_movement(
            session=session,
            voucher_id=v.id,
            article_id=product_id,
            qty_change=-quantity,
            location="SHOP_FLOOR",
            cost_rate=cost_rate
        )

        # 4. Post double-entry postings
        # Cost of waste = cost_rate * quantity
        total_waste_cost = round(quantity * cost_rate, 2)
        if total_waste_cost > 0:
            # Debit Factory Waste / Scrap Expense (GL-5102)
            ledger_service.post_journal_entry(
                session=session,
                voucher_id=v.id,
                account_code="GL-5102 Factory Waste",
                debit=total_waste_cost,
                credit=0.0
            )
            # Credit Finished Goods Asset (GL-1104)
            ledger_service.post_journal_entry(
                session=session,
                voucher_id=v.id,
                account_code="GL-1104 Finished Goods",
                debit=0.0,
                credit=total_waste_cost
            )

        session.commit()
        return w.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def list_waste(date_from: str = None, date_to: str = None, limit: int = 500):
    conn = get_connection()
    try:
        where = []
        params = []
        if date_from:
            where.append("w.waste_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("w.waste_date <= ?")
            params.append(date_to)

        clause = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT w.*, pr.code AS product_code, pr.name AS product_name,
                   pr.unit AS input_unit, pr.category, u.username AS user_name
            FROM waste w
            JOIN articles pr ON pr.id = w.product_id
            LEFT JOIN users u ON u.id = w.user_id
            {clause}
            ORDER BY w.id DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def waste_summary(date_from: str, date_to: str):
    """Per-product waste totals over a period — for reports."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT pr.code, pr.name, pr.category, pr.unit AS input_unit,
                      SUM(w.quantity) AS total_waste,
                      COUNT(*) AS waste_events
                 FROM waste w
                 JOIN articles pr ON pr.id = w.product_id
                WHERE w.waste_date BETWEEN ? AND ?
             GROUP BY pr.code, pr.name, pr.category, pr.unit
             ORDER BY pr.category, pr.code""",
            (date_from, date_to),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
