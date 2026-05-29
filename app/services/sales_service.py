"""
Sales service: records sales and decrements finished-product stock.
Directs sales transactions through the double-entry ledgers using SQLAlchemy.
Supports partial payments (deposit/credit splits), editing, and voiding.
Dual-compatible with payment_type ("CASH" / "CREDIT") and explicit amount_paid.
"""
from sqlalchemy import func
from app.database.db import get_session, get_connection
from app.database.models import Voucher, InventoryLedger, JournalEntry, Article, User
from app.services import ledger_service
from datetime import datetime

def record_sale(product_id: int, customer_name: str, quantity: float,
                unit_price: float, user_id: int = None, note: str = None,
                amount_paid: float = None,
                allow_negative_stock: bool = False,
                payment_type: str = "CASH"):
    """
    Atomically records a sale transaction.
    Creates a CASH_SALE or CREDIT_SALE voucher, deducts finished goods from the shop floor,
    and posts balanced debit/credit rows.
    Supports partial cash deposits (amount_paid) or term splits (payment_type).
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if unit_price < 0:
        raise ValueError("unit price cannot be negative")

    session = get_session()
    try:
        prod = session.query(Article).filter_by(id=product_id).first()
        if prod is None:
            raise ValueError("product not found")
            
        current_stock = prod.shop_floor_qty or 0.0
        if not allow_negative_stock and current_stock < quantity:
            raise ValueError(f"Insufficient stock: have {current_stock}, need {quantity}")

        total = round(quantity * unit_price, 2)
        
        # Resolve deposit vs accounts receivable split
        if amount_paid is None:
            if payment_type.upper() == "CASH":
                paid = total
            else:
                paid = 0.0
        else:
            paid = round(min(max(amount_paid, 0.0), total), 2)
            
        ar = round(total - paid, 2)
        v_type = "CASH_SALE" if ar == 0 else "CREDIT_SALE"

        # 1. Create Voucher Header
        v = ledger_service.create_voucher(
            session=session,
            voucher_type=v_type,
            created_by_id=user_id or 1,
            note=note,
            customer_name=customer_name
        )
        session.flush()

        # 2. Deduct product from Shop Floor inventory
        ledger_service.post_inventory_movement(
            session=session,
            voucher_id=v.id,
            article_id=product_id,
            qty_change=-quantity,
            location="SHOP_FLOOR",
            cost_rate=prod.cost_price or 0.0
        )

        # 3. Post Balanced Journal Entries
        # Debit Cash and/or AR, Credit Sales Revenue
        if paid > 0:
            ledger_service.post_journal_entry(
                session=session,
                voucher_id=v.id,
                account_code="GL-1101 Cash on Hand",
                debit=paid,
                credit=0.0
            )
        if ar > 0:
            ledger_service.post_journal_entry(
                session=session,
                voucher_id=v.id,
                account_code="GL-1105 Accounts Receivable",
                debit=ar,
                credit=0.0
            )
            
        ledger_service.post_journal_entry(
            session=session,
            voucher_id=v.id,
            account_code="GL-4101 Sales Revenue",
            debit=0.0,
            credit=total
        )

        session.commit()
        return v.id
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def list_sales(limit: int = 200, date_from: str = None, date_to: str = None, offset: int = 0, include_deleted: bool = False):
    """Retrieves all sales records mapped to the core voucher logs."""
    conn = get_connection()
    try:
        where = ["v.voucher_type IN ('CASH_SALE', 'CREDIT_SALE')"]
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

        # A sale corresponds to a finished product deduction (qty_change < 0).
        sql = f"""
            SELECT v.id, v.voucher_no, v.created_at, v.note, v.customer_name, v.state,
                   datetime(v.created_at) AS created_at_str,
                   date(v.created_at) AS sale_date,
                   u.username AS user_name, v.created_by_id AS user_id,
                   ABS(il.qty_change) AS quantity, il.cost_rate,
                   a.id AS product_id, a.code AS product_code, a.name AS product_name, a.unit AS input_unit,
                   je_rev.credit AS total,
                   COALESCE(je_cash.debit, 0.0) AS amount_paid
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0
            JOIN articles a ON a.id = il.article_id
            JOIN journal_entries je_rev ON je_rev.voucher_id = v.id AND je_rev.account_code = 'GL-4101 Sales Revenue'
            LEFT JOIN journal_entries je_cash ON je_cash.voucher_id = v.id AND je_cash.account_code = 'GL-1101 Cash on Hand'
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
                "customer_name": r["customer_name"],
                "quantity": r["quantity"],
                "unit_price": round(r["total"] / r["quantity"], 2) if r["quantity"] else 0.0,
                "total": r["total"],
                "amount_paid": r["amount_paid"],
                "balance": round(r["total"] - r["amount_paid"], 2),
                "sale_date": r["sale_date"],
                "created_at": r["created_at_str"],
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "note": r["note"],
                "state": r["state"]
            } for r in rows
        ]
    finally:
        conn.close()

def get_sale(sale_id: int):
    """Fetches details of a specific sale."""
    conn = get_connection()
    try:
        sql = """
            SELECT v.id, v.voucher_no, v.created_at, v.note, v.customer_name, v.state,
                   datetime(v.created_at) AS created_at_str,
                   date(v.created_at) AS sale_date,
                   u.username AS user_name, v.created_by_id AS user_id,
                   ABS(il.qty_change) AS quantity, il.cost_rate,
                   a.id AS product_id, a.code AS product_code, a.name AS product_name, a.unit AS input_unit,
                   je_rev.credit AS total,
                   COALESCE(je_cash.debit, 0.0) AS amount_paid
            FROM vouchers v
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0
            JOIN articles a ON a.id = il.article_id
            JOIN journal_entries je_rev ON je_rev.voucher_id = v.id AND je_rev.account_code = 'GL-4101 Sales Revenue'
            LEFT JOIN journal_entries je_cash ON je_cash.voucher_id = v.id AND je_cash.account_code = 'GL-1101 Cash on Hand'
            LEFT JOIN users u ON u.id = v.created_by_id
            WHERE v.id = ?
        """
        r = conn.execute(sql, (sale_id,)).fetchone()
        if r:
            return {
                "id": r["id"],
                "voucher_no": r["voucher_no"],
                "product_id": r["product_id"],
                "product_code": r["product_code"],
                "product_name": r["product_name"],
                "input_unit": r["input_unit"],
                "customer_name": r["customer_name"],
                "quantity": r["quantity"],
                "unit_price": round(r["total"] / r["quantity"], 2) if r["quantity"] else 0.0,
                "total": r["total"],
                "amount_paid": r["amount_paid"],
                "balance": round(r["total"] - r["amount_paid"], 2),
                "sale_date": r["sale_date"],
                "created_at": r["created_at_str"],
                "user_id": r["user_id"],
                "user_name": r["user_name"],
                "note": r["note"],
                "state": r["state"]
            }
        return None
    finally:
        conn.close()

def delete_sale(sale_id: int, user_id: int = None, reason: str = None):
    """Voids the sale voucher transactionally (swaps debits/credits and restores inventory stock)."""
    ledger_service.void_voucher(sale_id, user_id or 1)

def update_sale(sale_id: int, customer_name: str = None, quantity: float = None,
                unit_price: float = None, note: str = None, amount_paid: float = None,
                user_id: int = None, reason: str = None):
    """Edits a sale by voiding the old voucher and creating a new one."""
    existing = get_sale(sale_id)
    if existing is None:
        raise ValueError("Sale not found")
    if existing.get("state") == "VOIDED":
        raise ValueError("Cannot edit a voided sale")

    new_cust = customer_name if customer_name is not None else existing.get("customer_name")
    new_qty = quantity if quantity is not None else existing["quantity"]
    new_price = unit_price if unit_price is not None else existing["unit_price"]
    new_note = note if note is not None else existing.get("note")
    new_paid = amount_paid if amount_paid is not None else existing.get("amount_paid")

    # 1. Void the existing sale
    delete_sale(sale_id, user_id=user_id, reason=reason)

    # 2. Record the new sale
    return record_sale(
        product_id=existing["product_id"],
        customer_name=new_cust,
        quantity=new_qty,
        unit_price=new_price,
        user_id=user_id,
        note=new_note,
        amount_paid=new_paid,
        allow_negative_stock=True
    )

def record_cash_receipt(customer_name: str, amount: float, user_id: int = None, note: str = None):
    """Compatibility bridge: delegates to customer_service.record_payment."""
    from app.services import customer_service
    return customer_service.record_payment(
        customer_name=customer_name,
        amount=amount,
        method="cash",
        note=note,
        user_id=user_id
    )

def list_cash_receipts(limit: int = 200, offset: int = 0):
    """Lists all Cash Receipt Vouchers (CRV) for debt collection logs."""
    conn = get_connection()
    try:
        sql = """
            SELECT v.id, v.voucher_no, v.created_at, v.note, v.customer_name,
                   datetime(v.created_at) AS created_at_str,
                   u.username AS user_name,
                   je.debit AS amount
            FROM vouchers v
            JOIN journal_entries je ON je.voucher_id = v.id AND je.account_code IN ('GL-1101 Cash on Hand', 'GL-1102 Bank')
            LEFT JOIN users u ON u.id = v.created_by_id
            WHERE v.voucher_type = 'CRV' AND v.state = 'POSTED'
            ORDER BY v.id DESC LIMIT ? OFFSET ?
        """
        rows = conn.execute(sql, (limit, offset)).fetchall()
        return [
            {
                "id": r["id"],
                "voucher_no": r["voucher_no"],
                "customer_name": r["customer_name"],
                "amount": r["amount"],
                "created_at": r["created_at_str"],
                "user_name": r["user_name"],
                "note": r["note"]
            } for r in rows
        ]
    finally:
        conn.close()

def daily_revenue(date: str = None):
    """Calculates total sales revenue for a specific date (default = today)."""
    session = get_session()
    try:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
            
        # Sum credits on GL-4101 Sales Revenue for POSTED vouchers on this date
        res = session.query(func.sum(JournalEntry.credit)).join(Voucher).filter(
            Voucher.state == "POSTED",
            func.date(Voucher.created_at) == date,
            JournalEntry.account_code == "GL-4101 Sales Revenue"
        ).scalar()
        
        return float(res) if res is not None else 0.0
    finally:
        session.close()

def daily_profit(date: str = None):
    """Gross profit (revenue - cost of goods sold) for today or a given date."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_connection()
    try:
        sql = """
            SELECT SUM(je_rev.credit) AS rev,
                   SUM(ABS(il.qty_change) * il.cost_rate) AS cost
            FROM vouchers v
            JOIN journal_entries je_rev ON je_rev.voucher_id = v.id AND je_rev.account_code = 'GL-4101 Sales Revenue'
            JOIN inventory_ledger il ON il.voucher_id = v.id AND il.qty_change < 0
            WHERE v.voucher_type IN ('CASH_SALE', 'CREDIT_SALE') 
              AND v.state = 'POSTED'
              AND date(v.created_at) = ?
        """
        r = conn.execute(sql, (date,)).fetchone()
        rev = r["rev"] or 0.0
        cost = r["cost"] or 0.0
        return {
            "revenue": rev,
            "cost": cost,
            "profit": round(rev - cost, 2)
        }
    finally:
        conn.close()
