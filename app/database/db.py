"""
SQLAlchemy database setup and transactional migration.
Provides raw connections for backward compatibility and SQLAlchemy sessions.
"""
import os
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database.models import (
    Base, User, Permission, UserPermission, Article, Formula, Voucher, 
    InventoryLedger, JournalEntry, AuditLog, AppMeta, Supplier, Customer, 
    CustomerPayment, Expense, Waste
)

# Database file location
DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "factory.db"

# SQLAlchemy Setup
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Return a new SQLAlchemy Session instance."""
    return SessionLocal()


def get_connection():
    """Return a raw sqlite3 connection (backward compatibility for views/reports)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_database():
    """Initialize database tables, run migrations, and enable WAL mode."""
    # Enable WAL mode via raw connection first
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        
        # Check if old tables exist to trigger migration
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='materials'")
        has_old_db = cursor.fetchone() is not None
        
        if has_old_db:
            print("Old database version detected. Starting migration...")
            _migrate_old_database(conn)
            print("Migration completed successfully.")
        else:
            # Safe creation of new tables
            Base.metadata.create_all(engine)
            
            # Ensure all columns exist in vouchers table (dynamic upgrade check)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vouchers'")
            if cursor.fetchone() is not None:
                cursor.execute("PRAGMA table_info(vouchers)")
                columns = [row[1] for row in cursor.fetchall()]
                if "note" not in columns:
                    conn.execute("ALTER TABLE vouchers ADD COLUMN note TEXT")
                if "customer_name" not in columns:
                    conn.execute("ALTER TABLE vouchers ADD COLUMN customer_name TEXT")
                if "made_by" not in columns:
                    conn.execute("ALTER TABLE vouchers ADD COLUMN made_by TEXT")
                conn.commit()
    finally:
        conn.close()


def _migrate_old_database(raw_conn):
    """
    Reads all legacy database entries, drops old tables, 
    creates the new unified schema, and populates the double-entry structures.
    """
    raw_conn.row_factory = sqlite3.Row
    cursor = raw_conn.cursor()
    
    # 1. Fetch old data into memory
    old_users = cursor.execute("SELECT * FROM users").fetchall()
    old_materials = cursor.execute("SELECT * FROM materials").fetchall()
    old_products = cursor.execute("SELECT * FROM products").fetchall()
    old_formulas = cursor.execute("SELECT * FROM formulas").fetchall()
    old_production = cursor.execute("SELECT * FROM production").fetchall()
    old_consumption = cursor.execute("SELECT * FROM production_consumption").fetchall()
    old_sales = cursor.execute("SELECT * FROM sales").fetchall()
    old_movements = cursor.execute("SELECT * FROM stock_movements").fetchall()
    old_audit = cursor.execute("SELECT * FROM audit_log").fetchall()
    
    # 2. Drop old tables (turn off foreign keys temporarily for drop)
    raw_conn.execute("PRAGMA foreign_keys = OFF")
    tables_to_drop = [
        "app_meta", "audit_log", "sales", "production_consumption", 
        "production", "formulas", "products", "stock_movements", 
        "materials", "users"
    ]
    for table in tables_to_drop:
        raw_conn.execute(f"DROP TABLE IF EXISTS {table}")
    raw_conn.commit()
    raw_conn.execute("PRAGMA foreign_keys = ON")
    
    # 3. Create new schema using SQLAlchemy metadata
    Base.metadata.create_all(engine)
    
    # 4. Insert data using a clean SQLAlchemy Session
    session = SessionLocal()
    try:
        # Create map of old IDs to new objects
        user_map = {}
        article_map = {}  # code -> Article ORM object
        
        # A. Migrate Users
        default_admin_id = None
        for u in old_users:
            # Map old roles (admin, worker) to new (owner, cashier)
            role = "owner" if u["role"] == "admin" else "cashier"
            new_u = User(
                username=u["username"],
                password_hash=u["password_hash"],
                full_name=u["full_name"],
                role=role,
                created_at=datetime.strptime(u["created_at"], "%Y-%m-%d %H:%M:%S") if " " in u["created_at"] else datetime.now()
            )
            session.add(new_u)
            session.flush()
            user_map[u["id"]] = new_u.id
            if u["username"] == "admin":
                default_admin_id = new_u.id
                
        if not default_admin_id and user_map:
            default_admin_id = list(user_map.values())[0]
            
        # B. Migrate Materials (Raw Articles)
        for m in old_materials:
            art = Article(
                code=m["code"],
                name=m["name"],
                category="RAW",
                unit=m["unit"],
                cost_price=m["unit_cost"],
                warehouse_qty=m["current_stock"],
                shop_floor_qty=0.0,
                low_stock_alert=m["low_stock_alert"],
                is_active=True
            )
            session.add(art)
            session.flush()
            article_map[m["code"]] = art
            
        # C. Migrate Products (Finished Articles)
        for p in old_products:
            art = Article(
                code=p["code"],
                name=p["name"],
                category=p["category"],
                unit=p["input_unit"],
                sell_price=p["sell_price"],
                warehouse_qty=0.0,
                shop_floor_qty=p["stock"],
                low_stock_alert=p["low_stock_alert"],
                is_active=True
            )
            session.add(art)
            session.flush()
            article_map[p["code"]] = art
            
        # D. Migrate Formulas
        # Map old raw material and product IDs via code strings
        old_mat_code = {m["id"]: m["code"] for m in old_materials}
        old_prod_code = {p["id"]: p["code"] for p in old_products}
        
        for f in old_formulas:
            p_code = old_prod_code.get(f["product_id"])
            m_code = old_mat_code.get(f["material_id"])
            if p_code in article_map and m_code in article_map:
                prod = article_map[p_code]
                mat = article_map[m_code]
                
                # Check for default effective_from
                eff_from = f["effective_from"] if "effective_from" in f.keys() else "2026-01-01"
                
                new_f = Formula(
                    product_id=prod.id,
                    material_id=mat.id,
                    qty_per_unit=f["qty_per_unit"],
                    effective_from=eff_from
                )
                session.add(new_f)
        
        session.flush()
        
        # Helper to parse dates
        def parse_date(date_str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    pass
            return datetime.now()
            
        # E. Migrate Raw Stock Purchases (from old stock_movements)
        # Old movements mapping: purchase -> Store Receipt Voucher (SRV)
        # adjustment -> Stock Adjustment Voucher
        srv_counter = 1
        adj_counter = 1
        
        for mov in old_movements:
            m_code = old_mat_code.get(mov["material_id"])
            if m_code not in article_map:
                continue
            art = article_map[m_code]
            
            # Skip movements tied to production (production_service handles it separately)
            if mov["movement"] == "production":
                continue
                
            v_type = "SRV" if mov["movement"] == "purchase" else "ADJUSTMENT"
            v_no = f"MIG-{v_type}-{(srv_counter if v_type == 'SRV' else adj_counter):05d}"
            if v_type == "SRV":
                srv_counter += 1
            else:
                adj_counter += 1
                
            v = Voucher(
                voucher_no=v_no,
                voucher_type=v_type,
                state="POSTED",
                created_at=parse_date(mov["created_at"]),
                created_by_id=user_map.get(mov["user_id"], default_admin_id),
                note=mov["note"]
            )
            session.add(v)
            session.flush()
            
            # Stock addition
            ledger = InventoryLedger(
                voucher_id=v.id,
                article_id=art.id,
                qty_change=mov["qty"],
                cost_rate=art.cost_price,
                location="WAREHOUSE"
            )
            session.add(ledger)
            
            # Balanced Journal Entry
            account = "GL-1102 Raw Stock"
            offset = "GL-2101 Accounts Payable" if v_type == "SRV" else "GL-5109 Stock Variance"
            
            if mov["qty"] >= 0:
                val = mov["qty"] * art.cost_price
                session.add(JournalEntry(voucher_id=v.id, account_code=account, debit=val, credit=0.0))
                session.add(JournalEntry(voucher_id=v.id, account_code=offset, debit=0.0, credit=val))
            else:
                val = abs(mov["qty"]) * art.cost_price
                session.add(JournalEntry(voucher_id=v.id, account_code=offset, debit=val, credit=0.0))
                session.add(JournalEntry(voucher_id=v.id, account_code=account, debit=0.0, credit=val))
                
        # F. Migrate Production Records
        # Legacy production increments finished products and consumes raw materials
        prod_counter = 1
        for pr in old_production:
            p_code = old_prod_code.get(pr["product_id"])
            if p_code not in article_map:
                continue
            prod_art = article_map[p_code]
            
            v_no = f"MIG-PRD-{prod_counter:05d}"
            prod_counter += 1
            
            v = Voucher(
                voucher_no=v_no,
                voucher_type="PRODUCTION",
                state="POSTED",
                created_at=parse_date(pr["created_at"]),
                created_by_id=user_map.get(pr["user_id"], default_admin_id),
                note=pr["note"],
                made_by=pr["made_by"]
            )
            session.add(v)
            session.flush()
            
            # Increment Finished Goods (Shop Floor Location)
            session.add(InventoryLedger(
                voucher_id=v.id,
                article_id=prod_art.id,
                qty_change=pr["quantity"],
                cost_rate=prod_art.cost_price,
                location="SHOP_FLOOR"
            ))
            
            # Deduct Raw Materials consumed
            # Find consumption rows for this production
            related_cons = [c for c in old_consumption if c["production_id"] == pr["id"]]
            for cons in related_cons:
                m_code = old_mat_code.get(cons["material_id"])
                if m_code in article_map:
                    mat_art = article_map[m_code]
                    session.add(InventoryLedger(
                        voucher_id=v.id,
                        article_id=mat_art.id,
                        qty_change=-cons["qty_consumed"],
                        cost_rate=mat_art.cost_price,
                        location="WAREHOUSE"
                    ))
            
            # Balanced Production Journal Entries
            val_finished = pr["quantity"] * prod_art.sell_price  # fallback estimate
            session.add(JournalEntry(voucher_id=v.id, account_code="GL-1104 Finished Goods", debit=val_finished, credit=0.0))
            session.add(JournalEntry(voucher_id=v.id, account_code="GL-1103 WIP Inventory", debit=0.0, credit=val_finished))
            
        # G. Migrate Sales Records
        sale_counter = 1
        for s in old_sales:
            p_code = old_prod_code.get(s["product_id"])
            if p_code not in article_map:
                continue
            prod_art = article_map[p_code]
            
            v_no = f"MIG-SAL-{sale_counter:05d}"
            sale_counter += 1
            
            v = Voucher(
                voucher_no=v_no,
                voucher_type="CASH_SALE",
                state="POSTED",
                created_at=parse_date(s["created_at"]),
                created_by_id=user_map.get(s["user_id"], default_admin_id),
                note=s["note"],
                customer_name=s["customer_name"]
            )
            session.add(v)
            session.flush()
            
            # Decrement finished block stock
            session.add(InventoryLedger(
                voucher_id=v.id,
                article_id=prod_art.id,
                qty_change=-s["quantity"],
                cost_rate=prod_art.cost_price,
                location="SHOP_FLOOR"
            ))
            
            # Balanced General Ledger Sale Entries
            # Debit Cash, Credit Revenue
            session.add(JournalEntry(voucher_id=v.id, account_code="GL-1101 Cash on Hand", debit=s["total"], credit=0.0))
            session.add(JournalEntry(voucher_id=v.id, account_code="GL-4101 Sales Revenue", debit=0.0, credit=s["total"]))
            
        # H. Migrate Audit Logs
        for log in old_audit:
            new_log = AuditLog(
                user_id=user_map.get(log["user_id"], default_admin_id),
                action=log["action"],
                details=log["details"],
                created_at=parse_date(log["created_at"])
            )
            session.add(new_log)
            
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error executing database migration: {e}")
        raise e
    finally:
        session.close()
