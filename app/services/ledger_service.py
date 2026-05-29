"""
Double-entry transaction ledger engine for SuperERP.
Coordinates voucher creations, inventory ledger movements, 
journal entries, and compensations (voiding).
"""
from datetime import datetime
from sqlalchemy import func
from app.database.db import get_session, get_connection
from app.database.models import Voucher, InventoryLedger, JournalEntry, Article, User


def generate_voucher_no(session, voucher_type: str) -> str:
    """
    Generates a unique sequential voucher number.
    Format: [TYPE]-[YYYYMMDD]-[4-digit-sequence]
    """
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = f"{voucher_type}-{today_str}-"
    
    # Query count of vouchers created today of this type
    count = session.query(func.count(Voucher.id)).filter(
        Voucher.voucher_type == voucher_type,
        Voucher.voucher_no.like(f"{prefix}%")
    ).scalar()
    
    seq = (count or 0) + 1
    return f"{prefix}{seq:04d}"


def create_voucher(session, voucher_type: str, created_by_id: int, state: str = "POSTED", voucher_no: str = None,
                   note: str = None, customer_name: str = None, made_by: str = None, created_at=None) -> Voucher:
    """Creates and logs a Voucher header."""
    if not voucher_no:
        voucher_no = generate_voucher_no(session, voucher_type)
        
    v = Voucher(
        voucher_no=voucher_no,
        voucher_type=voucher_type,
        state=state,
        created_at=created_at if created_at else datetime.now(),
        created_by_id=created_by_id,
        note=note,
        customer_name=customer_name,
        made_by=made_by
    )
    session.add(v)
    session.flush()
    return v


def post_inventory_movement(session, voucher_id: int, article_id: int, qty_change: float, location: str, cost_rate: float = 0.0) -> InventoryLedger:
    """
    Appends a physical inventory ledger row and updates
    cached stock quantities on the Article table.
    """
    if location not in ("WAREHOUSE", "SHOP_FLOOR"):
        raise ValueError(f"Invalid location: {location}")
        
    # Append ledger entry
    entry = InventoryLedger(
        voucher_id=voucher_id,
        article_id=article_id,
        qty_change=qty_change,
        cost_rate=cost_rate,
        location=location
    )
    session.add(entry)
    
    # Update article cached quantities
    art = session.query(Article).filter_by(id=article_id).first()
    if art:
        if location == "WAREHOUSE":
            art.warehouse_qty = (art.warehouse_qty or 0.0) + qty_change
        else:
            art.shop_floor_qty = (art.shop_floor_qty or 0.0) + qty_change
            
    session.flush()
    return entry


def post_journal_entry(session, voucher_id: int, account_code: str, debit: float, credit: float) -> JournalEntry:
    """Logs a double-entry line."""
    je = JournalEntry(
        voucher_id=voucher_id,
        account_code=account_code,
        debit=debit,
        credit=credit
    )
    session.add(je)
    session.flush()
    return je


def get_current_stock(session, article_id: int, location: str = None) -> float:
    """Calculates active stock balance of an article by summing the ledger."""
    query = session.query(func.sum(InventoryLedger.qty_change)).join(Voucher).filter(
        InventoryLedger.article_id == article_id,
        Voucher.state == "POSTED"
    )
    if location:
        query = query.filter(InventoryLedger.location == location)
        
    res = query.scalar()
    return float(res) if res is not None else 0.0


def void_voucher(voucher_id: int, voided_by_id: int) -> bool:
    """
    Voids an active voucher transactionally.
    Reverses all inventory ledger rows and journal entries.
    """
    session = get_session()
    try:
        v = session.query(Voucher).filter_by(id=voucher_id).first()
        if not v:
            raise ValueError("Voucher not found")
        if v.state == "VOIDED":
            return True  # Already voided
            
        v.state = "VOIDED"
        v.voided_by_id = voided_by_id
        
        # 1. Reverse Inventory Ledger entries
        ledger_entries = session.query(InventoryLedger).filter_by(voucher_id=voucher_id).all()
        for le in ledger_entries:
            # Post matching opposite ledger row
            rev_le = InventoryLedger(
                voucher_id=voucher_id,
                article_id=le.article_id,
                qty_change=-le.qty_change,  # reverse sign
                cost_rate=le.cost_rate,
                location=le.location
            )
            session.add(rev_le)
            
            # Sync cached quantities back
            art = session.query(Article).filter_by(id=le.article_id).first()
            if art:
                if le.location == "WAREHOUSE":
                    art.warehouse_qty = (art.warehouse_qty or 0.0) - le.qty_change
                else:
                    art.shop_floor_qty = (art.shop_floor_qty or 0.0) - le.qty_change
                    
        # 2. Reverse Journal Entries
        journal_lines = session.query(JournalEntry).filter_by(voucher_id=voucher_id).all()
        for jl in journal_lines:
            # Post matching opposite journal row (swap debit and credit)
            rev_jl = JournalEntry(
                voucher_id=voucher_id,
                account_code=jl.account_code,
                debit=jl.credit,
                credit=jl.debit
            )
            session.add(rev_jl)
            
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def list_vouchers_paginated(limit: int = 50, offset: int = 0, type_filter: str = None, 
                            state_filter: str = None, query: str = None):
    """Retrieves a search-filtered, paginated list of voucher headers."""
    conn = get_connection()
    try:
        where = []
        params = []
        
        if type_filter and type_filter.upper() != "ALL":
            where.append("v.voucher_type = ?")
            params.append(type_filter.upper())
            
        if state_filter and state_filter.upper() != "ALL":
            where.append("v.state = ?")
            params.append(state_filter.upper())
            
        if query:
            q = f"%{query.lower()}%"
            where.append("""(
                LOWER(v.voucher_no) LIKE ? OR
                LOWER(COALESCE(v.note, '')) LIKE ? OR
                LOWER(COALESCE(v.customer_name, '')) LIKE ? OR
                LOWER(COALESCE(v.made_by, '')) LIKE ? OR
                LOWER(u.username) LIKE ?
            )""")
            params.extend([q, q, q, q, q])
            
        clause = "WHERE " + " AND ".join(where) if where else ""
        sql = f"""
            SELECT v.id, v.voucher_no, v.voucher_type, v.state, 
                   v.created_at, v.note, v.customer_name, v.made_by,
                   u.username AS created_by_name,
                   datetime(v.created_at) AS created_at_str
            FROM vouchers v
            LEFT JOIN users u ON u.id = v.created_by_id
            {clause}
            ORDER BY v.id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_voucher_details(voucher_id: int):
    """Fetches all physical stock movements and ledger balance items for a voucher."""
    conn = get_connection()
    try:
        # 1. Fetch physical movements
        inv_sql = """
            SELECT il.id, il.qty_change, il.cost_rate, il.location,
                   a.code AS article_code, a.name AS article_name, a.unit
            FROM inventory_ledger il
            JOIN articles a ON a.id = il.article_id
            WHERE il.voucher_id = ?
            ORDER BY il.id ASC
        """
        inventory_rows = conn.execute(inv_sql, (voucher_id,)).fetchall()
        
        # 2. Fetch general ledger journal logs
        jl_sql = """
            SELECT id, account_code, debit, credit
            FROM journal_entries
            WHERE voucher_id = ?
            ORDER BY id ASC
        """
        journal_rows = conn.execute(jl_sql, (voucher_id,)).fetchall()
        
        return {
            "inventory": [dict(r) for r in inventory_rows],
            "journal": [dict(r) for r in journal_rows]
        }
    finally:
        conn.close()

