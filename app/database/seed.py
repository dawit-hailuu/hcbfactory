"""
Seed initial data: materials, products, formulas, default admin.

All formula numbers come from the user-provided spreadsheet image.
These are PER ONE UNIT (per piece for HCB, per m² for Terazo).
Every number is editable from the Admin > Formulas screen — nothing is hardcoded
into business logic; this file only populates the DB on first run.
"""
import hashlib
from app.database.db import get_connection


def _hash(pw: str) -> str:
    """Simple SHA-256 password hash. Sufficient for a single-factory offline app.
    Replace with bcrypt/argon2 if deploying multi-tenant."""
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Master data
# ----------------------------------------------------------------------
MATERIALS = [
    # (code,     name,           unit,   low_stock_alert)
    ("CEMENT",  "Cement",       "kg",   500),
    ("SAND",    "Sand",         "m3",   2),
    ("PUMICE",  "Pumice",       "m3",   2),
    ("TETER00", "TeTer00",      "m3",   1),
    ("TETER01", "TeTer01",      "m3",   1),
    ("COLOR",   "ቀለም (Color)", "kg",   10),
    ("WATER",   "Water",        "liter", 100),
]

# HCB products. Category = 'HCB', input_unit = 'piece'.
# (code, display_name) — display name supports Amharic.
HCB_PRODUCTS = [
    ("HCB10N",   "HCB10N"),
    ("HCB10B",   "HCB10B"),
    ("HCB10C",   "HCB10C"),
    ("HCB15N",   "HCB15N"),
    ("HCB15B",   "HCB15B"),
    ("HCB15C",   "HCB15C"),
    ("HCB20N",   "HCB20N"),
    ("HCB20B",   "HCB20B"),
    ("HCB20C",   "HCB20C"),
    ("SLAB24",   "SLAB24"),
    ("SLAB16",   "SLAB16"),
    ("HCBGETER", "HCBገተር"),
]

# Terazo products. Category = 'TERAZO', input_unit = 'm2'.
TERAZO_PRODUCTS = [
    ("TERAZO_15x30x5", "Terazo 15×30×5"),
    ("TERAZO_30x30x5", "Terazo 30×30×5"),
    ("TERAZO_10x20x5", "Terazo 10×20×5"),
    ("TERAZO_20x20x5", "Terazo 20×20×5"),
    ("TERAZO_40x40x5", "Terazo 40×40×5"),
    ("I_SECTION",      "I-Section"),
    ("C_SECTION",      "C-Section"),
]

# Pipe (ቱቦ) products. Category = 'PIPE', input_unit = 'piece'.
PIPE_PRODUCTS = [
    ("TUBO_30",        "ቱቦ ባለ 30"),
    ("TUBO_40",        "ቱቦ ባለ 40"),
    ("TUBO_50",        "ቱቦ ባለ 50"),
    ("TUBO_60",        "ቱቦ ባለ 60"),
    ("TUBO_100",       "ቱቦ ባለ 100"),
    ("TUBO_BIRET_100", "ቱቦ ባለ ቢረት 100"),
]

# ----------------------------------------------------------------------
# Formulas — from the user's spreadsheet image.
# Format: { product_code: { material_code: qty_per_unit } }
# HCB: qty per 1 piece.  Terazo: qty per 1 m² (kare).
# ----------------------------------------------------------------------
HCB_FORMULAS = {
    # N-variants use only cement + pumice. TeTer values explicitly zero.
    "HCB10N": {"CEMENT": 2.5,         "PUMICE": 0.792,  "TETER00": 0,     "TETER01": 0},
    "HCB10B": {"CEMENT": 4,           "PUMICE": 0.792,  "TETER00": 1.456, "TETER01": 4.664},
    "HCB10C": {"CEMENT": 6,           "PUMICE": 0.0792, "TETER00": 2.456, "TETER01": 5.664},
    "HCB15N": {"CEMENT": 2.777778,    "PUMICE": 0.576,  "TETER00": 0,     "TETER01": 0},
    "HCB15B": {"CEMENT": 5,           "PUMICE": 0.336,  "TETER00": 4.456, "TETER01": 0.336},
    "HCB15C": {"CEMENT": 4.166667,    "PUMICE": 0.456,  "TETER00": 5.456, "TETER01": 0.336},
    "HCB20N": {"CEMENT": 4.166667,    "PUMICE": 0.528,  "TETER00": 0,     "TETER01": 0},
    "HCB20B": {"CEMENT": 6.25,        "PUMICE": 0.288,  "TETER00": 7.456, "TETER01": 0.288},
    "HCB20C": {"CEMENT": 5,           "PUMICE": 0.384,  "TETER00": 8.456, "TETER01": 0.228},
    # SLAB24 / SLAB16 not in the spreadsheet — start at 0; user fills via Admin UI.
    "SLAB24": {"CEMENT": 0, "PUMICE": 0, "TETER00": 0, "TETER01": 0},
    "SLAB16": {"CEMENT": 0, "PUMICE": 0, "TETER00": 0, "TETER01": 0},
    # HCBገተር — new HCB-category product, cement + pumice only
    "HCBGETER": {"CEMENT": 2.77777777778, "PUMICE": 0.384, "TETER00": 0, "TETER01": 0},
}

TERAZO_FORMULAS = {
    "TERAZO_15x30x5": {"CEMENT": 33.8461538, "TETER00": 0.02437,  "TETER01": 0.036554, "COLOR": 0.154},
    "TERAZO_30x30x5": {"CEMENT": 33.6666667, "TETER00": 0.02424,  "TETER01": 0.03636,  "COLOR": 0.07777},
    "TERAZO_10x20x5": {"CEMENT": 78.125,     "TETER00": 0.05625,  "TETER01": 0.084375, "COLOR": 0.35},
    "TERAZO_20x20x5": {"CEMENT": 69.4444444, "TETER00": 0.05,     "TETER01": 0.075,    "COLOR": 0.175},
    "TERAZO_40x40x5": {"CEMENT": 34.7222222, "TETER00": 0.025,    "TETER01": 0.0375,   "COLOR": 0.04375},
    "I_SECTION":      {"CEMENT": 40,         "TETER00": 0.0288,   "TETER01": 0.0432,   "COLOR": 0.182},
    "C_SECTION":      {"CEMENT": 33.3333333, "TETER00": 0.024,    "TETER01": 0.036,    "COLOR": 0.154},
}

# Pipe (ቱቦ) formulas — per 1 piece. Only Cement + TeTer00 are used.
# NOTE: TUBO_40 teter00=52.38288 is unusually large compared to siblings —
# user to verify; for now seeded as provided.
PIPE_FORMULAS = {
    "TUBO_30":        {"CEMENT": 30,          "TETER00": 14.616},
    "TUBO_40":        {"CEMENT": 25,          "TETER00": 52.38288},   # ← verify value with user
    "TUBO_50":        {"CEMENT": 50,          "TETER00": 0.288},
    "TUBO_60":        {"CEMENT": 66.6666667,  "TETER00": 20.736},
    "TUBO_100":       {"CEMENT": 100,         "TETER00": 0.936},
    "TUBO_BIRET_100": {"CEMENT": 100,         "TETER00": 6.84},
}


def seed_initial_data():
    """Idempotent seed. Safe to run on every startup — only inserts missing rows."""
    conn = get_connection()
    cur = conn.cursor()

    # --- default admin user ----------------------------------------------------
    cur.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
            ("admin", _hash("admin123"), "Factory Administrator", "admin"),
        )

    # --- materials -------------------------------------------------------------
    for code, name, unit, threshold in MATERIALS:
        cur.execute(
            """INSERT OR IGNORE INTO materials (code, name, unit, low_stock_alert)
               VALUES (?,?,?,?)""",
            (code, name, unit, threshold),
        )

    # --- HCB products ----------------------------------------------------------
    for code, name in HCB_PRODUCTS:
        cur.execute(
            """INSERT OR IGNORE INTO products (code, name, category, input_unit, sell_price)
               VALUES (?,?,?,?,?)""",
            (code, name, "HCB", "piece", 0),
        )

    # --- Terazo products -------------------------------------------------------
    for code, name in TERAZO_PRODUCTS:
        cur.execute(
            """INSERT OR IGNORE INTO products (code, name, category, input_unit, sell_price)
               VALUES (?,?,?,?,?)""",
            (code, name, "TERAZO", "m2", 0),
        )

    # --- Pipe (ቱቦ) products ---------------------------------------------------
    for code, name in PIPE_PRODUCTS:
        cur.execute(
            """INSERT OR IGNORE INTO products (code, name, category, input_unit, sell_price)
               VALUES (?,?,?,?,?)""",
            (code, name, "PIPE", "piece", 0),
        )

    conn.commit()

    # Build lookup tables (needed below)
    cur.execute("SELECT id, code FROM products")
    prod_ids = {row["code"]: row["id"] for row in cur.fetchall()}
    cur.execute("SELECT id, code FROM materials")
    mat_ids = {row["code"]: row["id"] for row in cur.fetchall()}

    def _insert_formula_set(formula_dict):
        """Insert formulas only for (product, material) pairs that have no row yet.
        This means newly-added products get their formulas seeded even on
        existing databases, while existing formulas are never overwritten."""
        for prod_code, materials in formula_dict.items():
            if prod_code not in prod_ids:
                continue
            pid = prod_ids[prod_code]
            for mat_code, qty in materials.items():
                if mat_code not in mat_ids:
                    continue
                mid = mat_ids[mat_code]
                existing = cur.execute(
                    "SELECT 1 FROM formulas WHERE product_id = ? AND material_id = ? LIMIT 1",
                    (pid, mid),
                ).fetchone()
                if existing is None:
                    cur.execute(
                        """INSERT INTO formulas (product_id, material_id, qty_per_unit)
                           VALUES (?,?,?)""",
                        (pid, mid, qty),
                    )

    _insert_formula_set(HCB_FORMULAS)
    _insert_formula_set(TERAZO_FORMULAS)
    _insert_formula_set(PIPE_FORMULAS)

    conn.commit()
    conn.close()
