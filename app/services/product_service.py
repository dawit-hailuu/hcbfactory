"""
Product & formula service.
Bridged to the unified 'articles' table and versioned SQLAlchemy formulas.
"""
from app.database.db import get_session, get_connection
from app.database.models import Article, Formula
from app.utils import clock


def list_products(category: str = None):
    """List all finished product articles."""
    session = get_session()
    try:
        query = session.query(Article).filter(
            Article.category != "RAW",
            Article.is_active == True
        )
        if category:
            query = query.filter(Article.category == category)
            
        prods = query.order_by(Article.category, Article.code).all()
        return [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "category": p.category,
                "input_unit": p.unit,
                "stock": p.shop_floor_qty,
                "sell_price": p.sell_price,
                "low_stock_alert": p.low_stock_alert
            } for p in prods
        ]
    finally:
        session.close()


def get_product(product_id: int):
    session = get_session()
    try:
        p = session.query(Article).filter(
            Article.id == product_id,
            Article.category != "RAW"
        ).first()
        if p:
            return {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "category": p.category,
                "input_unit": p.unit,
                "stock": p.shop_floor_qty,
                "sell_price": p.sell_price,
                "low_stock_alert": p.low_stock_alert
            }
        return None
    finally:
        session.close()


def get_product_by_code(code: str):
    session = get_session()
    try:
        p = session.query(Article).filter(
            Article.code == code,
            Article.category != "RAW"
        ).first()
        if p:
            return {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "category": p.category,
                "input_unit": p.unit,
                "stock": p.shop_floor_qty,
                "sell_price": p.sell_price,
                "low_stock_alert": p.low_stock_alert
            }
        return None
    finally:
        session.close()


def update_product(product_id: int, sell_price: float = None,
                   low_stock_alert: float = None, name: str = None):
    session = get_session()
    try:
        art = session.query(Article).filter_by(id=product_id).first()
        if art:
            if sell_price is not None:
                art.sell_price = sell_price
            if low_stock_alert is not None:
                art.low_stock_alert = low_stock_alert
            if name is not None:
                art.name = name
            session.commit()
    finally:
        session.close()


def get_active_formula(product_id: int, on_date: str = None):
    """
    Returns active formulas on a given date (default = today).
    Uses the latest effective_from <= on_date version.
    """
    conn = get_connection()
    try:
        if on_date is None:
            on_date_clause = "date('now','localtime')"
            params = (product_id,)
        else:
            on_date_clause = "?"
            params = (product_id, on_date)

        # Query using compatibility SQL pointing to the merged articles schema
        sql = f"""
        SELECT f.material_id, f.qty_per_unit, m.code AS material_code,
               m.name AS material_name, m.unit
        FROM formulas f
        JOIN articles m ON m.id = f.material_id
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
    active = get_active_formula(product_id)
    return list(active.values())


def upsert_formula(product_id: int, material_id: int, qty_per_unit: float):
    """Inserts a new formula record versioned today."""
    if qty_per_unit < 0:
        raise ValueError("formula quantity cannot be negative")
    today = clock.today()
    session = get_session()
    try:
        existing = session.query(Formula).filter_by(
            product_id=product_id,
            material_id=material_id,
            effective_from=today
        ).first()
        if existing:
            existing.qty_per_unit = qty_per_unit
        else:
            form = Formula(
                product_id=product_id,
                material_id=material_id,
                qty_per_unit=qty_per_unit,
                effective_from=today
            )
            session.add(form)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def record_fgtv(product_id: int, quantity: float, user_id: int = None, note: str = None):
    """
    Creates a Finished Goods Transfer Voucher (FGTV).
    Transfers finished blocks from curing yard (WAREHOUSE) to sales floor (SHOP_FLOOR).
    """
    if quantity <= 0:
        raise ValueError("transfer quantity must be positive")

    from app.services import ledger_service
    session = get_session()
    try:
        prod = session.query(Article).filter_by(id=product_id).first()
        if not prod:
            raise ValueError("Product not found")

        # Check if curing yard (WAREHOUSE) has enough stock
        curing_stock = ledger_service.get_current_stock(session, product_id, "WAREHOUSE")
        if curing_stock < quantity:
            raise ValueError(f"Insufficient curing yard stock: have {curing_stock:.2f}, need {quantity:.2f}")

        # 1. Create Voucher Header
        v = ledger_service.create_voucher(
            session=session,
            voucher_type="FGTV",
            created_by_id=user_id or 1
        )
        v.note = note
        session.flush()

        # 2. Decrement Curing Yard (WAREHOUSE)
        ledger_service.post_inventory_movement(
            session=session,
            voucher_id=v.id,
            article_id=product_id,
            qty_change=-quantity,
            location="WAREHOUSE",
            cost_rate=prod.cost_price or 0.0
        )

        # 3. Increment Sales Floor (SHOP_FLOOR)
        ledger_service.post_inventory_movement(
            session=session,
            voucher_id=v.id,
            article_id=product_id,
            qty_change=quantity,
            location="SHOP_FLOOR",
            cost_rate=prod.cost_price or 0.0
        )

        # 4. Balanced Journal Entry
        # Debit Finished Goods, Credit WIP/Curing Yard Inventory
        val = quantity * (prod.sell_price or 0.0)
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-1104 Finished Goods",
            debit=val,
            credit=0.0
        )
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-1103 WIP Inventory",
            debit=0.0,
            credit=val
        )

        session.commit()
        return v.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def list_fgtv(limit: int = 200, offset: int = 0):
    """Lists all Finished Goods Transfer Vouchers (FGTV)."""
    conn = get_connection()
    try:
        sql = """
            SELECT v.id, v.voucher_no, v.created_at, v.note,
                   datetime(v.created_at) AS created_at_str,
                   u.username AS user_name,
                   ABS(il.qty_change) AS quantity,
                   a.code AS product_code, a.name AS product_name, a.unit
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0 AND il.location = 'WAREHOUSE'
            JOIN articles a ON a.id = il.article_id
            LEFT JOIN users u ON u.id = v.created_by_id
            WHERE v.voucher_type = 'FGTV' AND v.state = 'POSTED'
            ORDER BY v.id DESC LIMIT ? OFFSET ?
        """
        rows = conn.execute(sql, (limit, offset)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

