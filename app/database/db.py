"""
SQLite database connection and schema setup.
All tables created here. The schema is designed so that:
- Formulas are stored in DB (not hardcoded) and editable from the UI.
- Stock movements are append-only for full history/audit trail.
- Formula versions are preserved by date so historical production records
  remain accurate even if formulas change later.
"""
import sqlite3
from pathlib import Path

from app.utils.paths import DATA_DIR

# Database file lives in <app folder>/data/factory.db
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "factory.db"


def get_connection():
    """Return a new SQLite connection with foreign keys enabled and row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL CHECK(role IN ('admin','worker')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- RAW MATERIALS  (cement, sand, pumice, teter00, teter01, water, ቀለም)
-- Each material has a unit and a low-stock threshold.
-- Current stock is computed from the stock_movements ledger,
-- but we also cache it here for quick dashboard reads.
-- ============================================================
CREATE TABLE IF NOT EXISTS materials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT UNIQUE NOT NULL,        -- e.g. 'CEMENT', 'TETER00'
    name            TEXT NOT NULL,               -- display name (supports Amharic)
    unit            TEXT NOT NULL,               -- 'kg', 'm3', 'liter'
    current_stock   REAL NOT NULL DEFAULT 0,
    low_stock_alert REAL NOT NULL DEFAULT 0,
    unit_cost       REAL NOT NULL DEFAULT 0      -- ETB per unit, optional
);

-- Append-only ledger of every stock change.
-- Positive qty = added, negative = consumed.
CREATE TABLE IF NOT EXISTS stock_movements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    qty         REAL NOT NULL,                   -- signed
    movement    TEXT NOT NULL CHECK(movement IN ('purchase','production','adjustment','initial')),
    reference   TEXT,                            -- e.g. production_id or supplier name
    note        TEXT,
    user_id     INTEGER REFERENCES users(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- PRODUCTS  (HCB blocks + Terazo tiles)
-- input_unit is what the user enters:
--   'piece' for HCB
--   'm2'    for Terazo (kare)
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT UNIQUE NOT NULL,           -- 'HCB10N', 'TERAZO_30x30x5', 'TUBO_30', ...
    name         TEXT NOT NULL,
    category     TEXT NOT NULL CHECK(category IN ('HCB','TERAZO','PIPE')),
    input_unit   TEXT NOT NULL CHECK(input_unit IN ('piece','m2')),
    stock        REAL NOT NULL DEFAULT 0,        -- finished goods on hand
    sell_price   REAL NOT NULL DEFAULT 0,        -- ETB per piece or per m2
    low_stock_alert REAL NOT NULL DEFAULT 0
);

-- ============================================================
-- FORMULAS  (per 1 input_unit of product, per material)
-- Versioned by effective_from date.  When admin edits a formula
-- we INSERT a new row; old production records still resolve to
-- the formula that was active on their production date.
-- ============================================================
CREATE TABLE IF NOT EXISTS formulas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id     INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    material_id    INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    qty_per_unit   REAL NOT NULL,                -- material qty per 1 piece or 1 m2
    effective_from TEXT NOT NULL DEFAULT (date('now','localtime')),
    UNIQUE(product_id, material_id, effective_from)
);

-- ============================================================
-- PRODUCTION RUNS
-- ============================================================
CREATE TABLE IF NOT EXISTS production (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id    INTEGER NOT NULL REFERENCES products(id),
    quantity      REAL NOT NULL,                 -- pieces or m2
    production_date TEXT NOT NULL DEFAULT (date('now','localtime')),
    user_id       INTEGER REFERENCES users(id),     -- who recorded it in the system
    made_by       TEXT,                             -- which worker physically made it (free text)
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Snapshot of which materials and how much were consumed for each production run.
-- Stored so reports stay correct even if formulas are edited later.
CREATE TABLE IF NOT EXISTS production_consumption (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    production_id INTEGER NOT NULL REFERENCES production(id) ON DELETE CASCADE,
    material_id   INTEGER NOT NULL REFERENCES materials(id),
    qty_consumed  REAL NOT NULL
);

-- ============================================================
-- SALES
-- ============================================================
CREATE TABLE IF NOT EXISTS sales (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id    INTEGER NOT NULL REFERENCES products(id),
    customer_name TEXT,
    quantity      REAL NOT NULL,
    unit_price    REAL NOT NULL,
    total         REAL NOT NULL,
    sale_date     TEXT NOT NULL DEFAULT (date('now','localtime')),
    user_id       INTEGER REFERENCES users(id),
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- AUDIT LOG (lightweight)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id),
    action     TEXT NOT NULL,
    details    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ============================================================
-- APP META  (migration flags, schema version, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS app_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ============================================================
-- v3 ADDITIONS
-- ============================================================

-- Suppliers (raw material vendors)
CREATE TABLE IF NOT EXISTS suppliers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT UNIQUE NOT NULL,
    phone      TEXT,
    address    TEXT,
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Customers (kept lightweight — also used informally via sales.customer_name)
CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT UNIQUE NOT NULL,
    phone      TEXT,
    address    TEXT,
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Customer payments (settle outstanding balances on credit sales)
CREATE TABLE IF NOT EXISTS customer_payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    amount        REAL NOT NULL,
    payment_date  TEXT NOT NULL DEFAULT (date('now','localtime')),
    method        TEXT,                       -- 'cash','bank','etc'
    note          TEXT,
    user_id       INTEGER REFERENCES users(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Expenses (salaries, utilities, etc.)
CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    category     TEXT NOT NULL,               -- 'Labor','Utilities','Rent','Transport','Maintenance','Other'
    amount       REAL NOT NULL,
    expense_date TEXT NOT NULL DEFAULT (date('now','localtime')),
    description  TEXT,
    user_id      INTEGER REFERENCES users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Damaged / wasted finished goods
CREATE TABLE IF NOT EXISTS waste (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    REAL NOT NULL,                -- always positive; the action is implicitly a stock reduction
    reason      TEXT,                         -- 'cracked','rejected','dropped',...
    waste_date  TEXT NOT NULL DEFAULT (date('now','localtime')),
    user_id     INTEGER REFERENCES users(id),
    note        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_stock_mov_mat ON stock_movements(material_id);
CREATE INDEX IF NOT EXISTS idx_stock_mov_date ON stock_movements(created_at);
CREATE INDEX IF NOT EXISTS idx_production_date ON production(production_date);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_formula_prod ON formulas(product_id);
CREATE INDEX IF NOT EXISTS idx_payments_customer ON customer_payments(customer_name);
CREATE INDEX IF NOT EXISTS idx_payments_date ON customer_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_waste_date ON waste(waste_date);
"""


def init_database():
    """Create tables if they do not exist, and apply migrations."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _run_migrations(conn)
    finally:
        conn.close()


def _migration_done(conn, key: str) -> bool:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row is not None and row["value"] == "1"


def _mark_migration_done(conn, key: str):
    conn.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES (?,?)",
                 (key, "1"))
    conn.commit()


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _run_migrations(conn):
    """Apply schema migrations to existing databases.
    Each migration is idempotent (gated by app_meta flag or column existence check).
    """
    # ----------------------------------------------------------------
    # Migration: add made_by column to production
    # ----------------------------------------------------------------
    if not _column_exists(conn, "production", "made_by"):
        try:
            conn.execute("ALTER TABLE production ADD COLUMN made_by TEXT")
            conn.commit()
        except Exception:
            pass  # column may have been added in a parallel run

    # ----------------------------------------------------------------
    # Migration: allow PIPE category on products
    # SQLite cannot alter CHECK constraints in-place — rebuild the table.
    # ----------------------------------------------------------------
    if not _migration_done(conn, "products_allow_pipe_category_v1"):
        # Determine if the existing CHECK already includes 'PIPE'.
        # Easiest: try inserting + rolling back a PIPE row; if it fails, rebuild.
        needs_rebuild = False
        try:
            conn.execute(
                """INSERT INTO products (code, name, category, input_unit)
                   VALUES ('__pipe_probe__', '__probe__', 'PIPE', 'piece')"""
            )
            # success — clean up the probe row
            conn.execute("DELETE FROM products WHERE code = '__pipe_probe__'")
            conn.commit()
        except Exception:
            conn.rollback()
            needs_rebuild = True

        if needs_rebuild:
            try:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.executescript("""
                    BEGIN;
                    CREATE TABLE products_new (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        code         TEXT UNIQUE NOT NULL,
                        name         TEXT NOT NULL,
                        category     TEXT NOT NULL CHECK(category IN ('HCB','TERAZO','PIPE')),
                        input_unit   TEXT NOT NULL CHECK(input_unit IN ('piece','m2')),
                        stock        REAL NOT NULL DEFAULT 0,
                        sell_price   REAL NOT NULL DEFAULT 0,
                        low_stock_alert REAL NOT NULL DEFAULT 0
                    );
                    INSERT INTO products_new (id, code, name, category, input_unit,
                                              stock, sell_price, low_stock_alert)
                    SELECT id, code, name, category, input_unit,
                           stock, sell_price, low_stock_alert
                    FROM products;
                    DROP TABLE products;
                    ALTER TABLE products_new RENAME TO products;
                    COMMIT;
                """)
            finally:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.commit()
        _mark_migration_done(conn, "products_allow_pipe_category_v1")

    # ----------------------------------------------------------------
    # Migration: zero out TeTer00/TeTer01 for HCB N-variants
    # ----------------------------------------------------------------
    if not _migration_done(conn, "hcb_n_variant_zero_teter_v1"):
        cur = conn.execute(
            """SELECT p.id AS pid, m.id AS mid, m.code AS mcode
                 FROM products p, materials m
                WHERE p.code IN ('HCB10N','HCB15N','HCB20N')
                  AND m.code IN ('TETER00','TETER01')"""
        ).fetchall()
        # Insert a new formula version dated today setting these to 0,
        # so historical production records keep their old values.
        from app.utils import clock
        today = clock.today()
        for r in cur:
            existing = conn.execute(
                """SELECT id FROM formulas
                    WHERE product_id = ? AND material_id = ?
                      AND effective_from = ?""",
                (r["pid"], r["mid"], today),
            ).fetchone()
            if existing:
                conn.execute("UPDATE formulas SET qty_per_unit = 0 WHERE id = ?",
                             (existing["id"],))
            else:
                conn.execute(
                    """INSERT INTO formulas (product_id, material_id, qty_per_unit, effective_from)
                       VALUES (?,?,0,?)""",
                    (r["pid"], r["mid"], today),
                )
        conn.commit()
        _mark_migration_done(conn, "hcb_n_variant_zero_teter_v1")

    # ----------------------------------------------------------------
    # v3 migrations: new columns for profit, supplier, credit sales, soft delete
    # ----------------------------------------------------------------
    if not _column_exists(conn, "production", "cost_total"):
        try:
            conn.execute("ALTER TABLE production ADD COLUMN cost_total REAL DEFAULT 0")
            conn.commit()
        except Exception:
            pass

    if not _column_exists(conn, "production", "deleted_at"):
        try:
            conn.execute("ALTER TABLE production ADD COLUMN deleted_at TEXT")
            conn.commit()
        except Exception:
            pass

    if not _column_exists(conn, "sales", "amount_paid"):
        try:
            # Default = total (legacy sales assumed fully paid in cash)
            conn.execute("ALTER TABLE sales ADD COLUMN amount_paid REAL")
            conn.execute("UPDATE sales SET amount_paid = total WHERE amount_paid IS NULL")
            conn.commit()
        except Exception:
            pass

    if not _column_exists(conn, "sales", "cost_total"):
        try:
            conn.execute("ALTER TABLE sales ADD COLUMN cost_total REAL DEFAULT 0")
            conn.commit()
        except Exception:
            pass

    if not _column_exists(conn, "sales", "deleted_at"):
        try:
            conn.execute("ALTER TABLE sales ADD COLUMN deleted_at TEXT")
            conn.commit()
        except Exception:
            pass

    if not _column_exists(conn, "stock_movements", "supplier_name"):
        try:
            conn.execute("ALTER TABLE stock_movements ADD COLUMN supplier_name TEXT")
            conn.commit()
        except Exception:
            pass

    if not _column_exists(conn, "stock_movements", "unit_cost"):
        try:
            conn.execute("ALTER TABLE stock_movements ADD COLUMN unit_cost REAL")
            conn.commit()
        except Exception:
            pass

    # ----------------------------------------------------------------
    # v4 migrations: voucher numbers on every transactional table
    # ----------------------------------------------------------------
    for tbl in ("sales", "production", "expenses", "customer_payments",
                "stock_movements", "waste"):
        if not _column_exists(conn, tbl, "voucher_no"):
            try:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN voucher_no TEXT")
                conn.commit()
            except Exception:
                pass

    # Backfill voucher numbers on existing rows
    if not _migration_done(conn, "voucher_backfill_v1"):
        # Each prefix has its own counter
        configs = [
            ("sales",             "SV"),  # Sales Voucher
            ("customer_payments", "RV"),  # Receipt Voucher
            ("expenses",          "EV"),  # Expense Voucher
            ("production",        "PV"),  # Production Voucher
            ("waste",             "WV"),  # Waste Voucher
            # stock purchases (movement='purchase') become Material Vouchers (MV)
        ]
        for tbl, prefix in configs:
            rows = conn.execute(
                f"SELECT id FROM {tbl} WHERE voucher_no IS NULL ORDER BY id"
            ).fetchall()
            for i, r in enumerate(rows, start=1):
                conn.execute(
                    f"UPDATE {tbl} SET voucher_no = ? WHERE id = ?",
                    (f"{prefix}-{i:05d}", r["id"]),
                )
        # Stock movements: only the 'purchase' movements get MV numbers
        purchases = conn.execute(
            "SELECT id FROM stock_movements WHERE movement='purchase' AND voucher_no IS NULL ORDER BY id"
        ).fetchall()
        for i, r in enumerate(purchases, start=1):
            conn.execute(
                "UPDATE stock_movements SET voucher_no = ? WHERE id = ?",
                (f"MV-{i:05d}", r["id"]),
            )
        conn.commit()
        _mark_migration_done(conn, "voucher_backfill_v1")
