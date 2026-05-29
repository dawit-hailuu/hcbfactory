"""
Seed initial master records using SQLAlchemy:
Unified Articles (materials + products), date-versioned Formulas,
UAC Permissions, and default Admin/User configurations.
"""
import hashlib
from datetime import datetime
from app.database.db import get_session
from app.database.models import User, Permission, UserPermission, Article, Formula, Customer, Supplier


def _hash(pw: str) -> str:
    """SHA-256 password hash for local user accounts."""
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


# 1. Raw Material Articles (Category: RAW)
MATERIALS = [
    # (code, name, unit, low_stock_alert)
    ("CEMENT",  "Cement",       "kg",   500.0),
    ("SAND",    "Sand",         "m3",   2.0),
    ("PUMICE",  "Pumice",       "m3",   2.0),
    ("TETER00", "TeTer00",      "m3",   1.0),
    ("TETER01", "TeTer01",      "m3",   1.0),
    ("COLOR",   "ቀለም (Color)", "kg",   10.0),
    ("WATER",   "Water",        "liter", 100.0),
]

# 2. Finished Concrete Articles (Category: FINISHED)
HCB_PRODUCTS = [
    ("HCB10N",   "HCB10N",   "piece"),
    ("HCB10B",   "HCB10B",   "piece"),
    ("HCB10C",   "HCB10C",   "piece"),
    ("HCB15N",   "HCB15N",   "piece"),
    ("HCB15B",   "HCB15B",   "piece"),
    ("HCB15C",   "HCB15C",   "piece"),
    ("HCB20N",   "HCB20N",   "piece"),
    ("HCB20B",   "HCB20B",   "piece"),
    ("HCB20C",   "HCB20C",   "piece"),
    ("SLAB24",   "SLAB24",   "piece"),
    ("SLAB16",   "SLAB16",   "piece"),
    ("HCBGETER", "HCBገተር",   "piece"),
]

TERAZO_PRODUCTS = [
    ("TERAZO_15x30x5", "Terazo 15×30×5", "m2"),
    ("TERAZO_30x30x5", "Terazo 30×30×5", "m2"),
    ("TERAZO_10x20x5", "Terazo 10×20×5", "m2"),
    ("TERAZO_20x20x5", "Terazo 20×20×5", "m2"),
    ("TERAZO_40x40x5", "Terazo 40×40×5", "m2"),
    ("I_SECTION",      "I-Section",      "m2"),
    ("C_SECTION",      "C-Section",      "m2"),
]

PIPE_PRODUCTS = [
    ("TUBO_30",        "ቱቦ ባለ 30",        "piece"),
    ("TUBO_40",        "ቱቦ ባለ 40",        "piece"),
    ("TUBO_50",        "ቱቦ ባለ 50",        "piece"),
    ("TUBO_60",        "ቱቦ ባለ 60",        "piece"),
    ("TUBO_100",       "ቱቦ ባለ 100",       "piece"),
    ("TUBO_BIRET_100", "ቱቦ ባለ ቢረት 100", "piece"),
]

# 3. Recipes and Mixing Formulas (qty per 1 unit)
HCB_FORMULAS = {
    "HCB10N": {"CEMENT": 2.5,         "PUMICE": 0.792,  "TETER00": 0.0,   "TETER01": 0.0},
    "HCB10B": {"CEMENT": 4.0,         "PUMICE": 0.792,  "TETER00": 1.456, "TETER01": 4.664},
    "HCB10C": {"CEMENT": 6.0,         "PUMICE": 0.0792, "TETER00": 2.456, "TETER01": 5.664},
    "HCB15N": {"CEMENT": 2.777778,    "PUMICE": 0.576,  "TETER00": 0.0,   "TETER01": 0.0},
    "HCB15B": {"CEMENT": 5.0,         "PUMICE": 0.336,  "TETER00": 4.456, "TETER01": 0.336},
    "HCB15C": {"CEMENT": 4.166667,    "PUMICE": 0.456,  "TETER00": 5.456, "TETER01": 0.336},
    "HCB20N": {"CEMENT": 4.166667,    "PUMICE": 0.528,  "TETER00": 0.0,   "TETER01": 0.0},
    "HCB20B": {"CEMENT": 6.25,        "PUMICE": 0.288,  "TETER00": 7.456, "TETER01": 0.288},
    "HCB20C": {"CEMENT": 5.0,         "PUMICE": 0.384,  "TETER00": 8.456, "TETER01": 0.228},
    "SLAB24": {"CEMENT": 0.0,         "PUMICE": 0.0,    "TETER00": 0.0,   "TETER01": 0.0},
    "SLAB16": {"CEMENT": 0.0,         "PUMICE": 0.0,    "TETER00": 0.0,   "TETER01": 0.0},
    "HCBGETER": {"CEMENT": 2.7777778, "PUMICE": 0.384,  "TETER00": 0.0,   "TETER01": 0.0},
}

TERAZO_FORMULAS = {
    "TERAZO_15x30x5": {"CEMENT": 33.8461538, "TETER00": 0.02437,  "TETER01": 0.036554, "COLOR": 0.154},
    "TERAZO_30x30x5": {"CEMENT": 33.6666667, "TETER00": 0.02424,  "TETER01": 0.03636,  "COLOR": 0.07777},
    "TERAZO_10x20x5": {"CEMENT": 78.125,     "TETER00": 0.05625,  "TETER01": 0.084375, "COLOR": 0.35},
    "TERAZO_20x20x5": {"CEMENT": 69.4444444, "TETER00": 0.05,     "TETER01": 0.075,    "COLOR": 0.175},
    "TERAZO_40x40x5": {"CEMENT": 34.7222222, "TETER00": 0.025,    "TETER01": 0.0375,   "COLOR": 0.04375},
    "I_SECTION":      {"CEMENT": 40.0,        "TETER00": 0.0288,   "TETER01": 0.0432,   "COLOR": 0.182},
    "C_SECTION":      {"CEMENT": 33.3333333, "TETER00": 0.024,    "TETER01": 0.036,    "COLOR": 0.154},
}

PIPE_FORMULAS = {
    "TUBO_30":        {"CEMENT": 30.0,         "TETER00": 14.616},
    "TUBO_40":        {"CEMENT": 25.0,         "TETER00": 52.38288},
    "TUBO_50":        {"CEMENT": 50.0,         "TETER00": 0.288},
    "TUBO_60":        {"CEMENT": 66.6666667,  "TETER00": 20.736},
    "TUBO_100":       {"CEMENT": 100.0,        "TETER00": 0.936},
    "TUBO_BIRET_100": {"CEMENT": 100.0,        "TETER00": 6.84},
}

# 4. Standard UAC permissions
SYSTEM_PERMISSIONS = [
    ("sale:create",          "Allowed to create Cash/Credit Sale vouchers"),
    ("sale:void",            "Allowed to void sales transactions"),
    ("inventory:add-stock",  "Allowed to post Store Receipt Vouchers (Model 19)"),
    ("inventory:adjust",     "Allowed to perform physical stock adjustments"),
    ("inventory:disposal",   "Allowed to file inventory disposal/wastage vouchers"),
    ("production:create",    "Allowed to record production runs"),
    ("system:update-price",  "Allowed to modify product prices"),
    ("user:manage",          "Allowed to manage user rosters and credentials"),
    ("audit:view",           "Allowed to view general transaction and audit logs"),
]


def seed_initial_data():
    """Idempotently populates the database with default articles, formulas, and security keys."""
    session = get_session()
    try:
        # A. Seed Permissions
        perm_map = {}
        for action, desc in SYSTEM_PERMISSIONS:
            perm = session.query(Permission).filter_by(action_key=action).first()
            if not perm:
                perm = Permission(action_key=action, description=desc)
                session.add(perm)
                session.flush()
            perm_map[action] = perm.id

        # B. Seed Default Admin User (Owner)
        admin = session.query(User).filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=_hash("admin123"),
                full_name="Factory Owner / Admin",
                role="owner"
            )
            session.add(admin)
            session.flush()

            # Grant all permissions to admin
            for perm_id in perm_map.values():
                up = UserPermission(user_id=admin.id, permission_id=perm_id, is_allowed=True)
                session.add(up)

        # C. Seed Materials (Raw Articles)
        for code, name, unit, alert in MATERIALS:
            art = session.query(Article).filter_by(code=code).first()
            if not art:
                art = Article(
                    code=code,
                    name=name,
                    category="RAW",
                    unit=unit,
                    low_stock_alert=alert,
                    is_active=True
                )
                session.add(art)

        # D. Seed HCB Finished Articles
        for code, name, unit in HCB_PRODUCTS:
            art = session.query(Article).filter_by(code=code).first()
            if not art:
                art = Article(
                    code=code,
                    name=name,
                    category="HCB",
                    unit=unit,
                    low_stock_alert=100.0,
                    is_active=True
                )
                session.add(art)

        # E. Seed Terazo Finished Articles
        for code, name, unit in TERAZO_PRODUCTS:
            art = session.query(Article).filter_by(code=code).first()
            if not art:
                art = Article(
                    code=code,
                    name=name,
                    category="TERAZO",
                    unit=unit,
                    low_stock_alert=50.0,
                    is_active=True
                )
                session.add(art)

        # F. Seed Pipe Finished Articles
        for code, name, unit in PIPE_PRODUCTS:
            art = session.query(Article).filter_by(code=code).first()
            if not art:
                art = Article(
                    code=code,
                    name=name,
                    category="PIPE",
                    unit=unit,
                    low_stock_alert=20.0,
                    is_active=True
                )
                session.add(art)

        session.flush()

        # Build Article ID maps
        articles = session.query(Article).all()
        art_ids = {a.code: a.id for a in articles}

        def _seed_formula_set(formula_dict):
            for p_code, materials in formula_dict.items():
                if p_code not in art_ids:
                    continue
                pid = art_ids[p_code]
                for m_code, qty in materials.items():
                    if m_code not in art_ids:
                        continue
                    mid = art_ids[m_code]
                    
                    # See if formula link exists (default to epoch year 2026-01-01)
                    existing = session.query(Formula).filter_by(
                        product_id=pid, material_id=mid, effective_from="2026-01-01"
                    ).first()
                    if not existing:
                        form = Formula(
                            product_id=pid,
                            material_id=mid,
                            qty_per_unit=qty,
                            effective_from="2026-01-01"
                        )
                        session.add(form)

        _seed_formula_set(HCB_FORMULAS)
        _seed_formula_set(TERAZO_FORMULAS)
        _seed_formula_set(PIPE_FORMULAS)

        # Seed default Customer & Supplier
        default_customer = session.query(Customer).filter_by(name="Walk-in Customer").first()
        if not default_customer:
            session.add(Customer(name="Walk-in Customer", phone="0000000000", address="Local", note="Default customer for cash sales"))
        
        default_supplier = session.query(Supplier).filter_by(name="General Supplier").first()
        if not default_supplier:
            session.add(Supplier(name="General Supplier", phone="0000000000", address="Local", note="Default supplier for materials"))

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
