"""
SQLAlchemy ORM models for SuperERP.
Includes Users, Permissions, Articles (raw and finished unified),
Vouchers, double-entry Inventory Ledgers, Journal Entries, and Audit logs.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, 
    UniqueConstraint, create_engine
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ============================================================
# USER & SECURITY (UAC) MODELS
# ============================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(20), nullable=False, default="cashier")  # 'cashier', 'manager', 'owner'
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")
    created_vouchers = relationship("Voucher", foreign_keys="Voucher.created_by_id", back_populates="created_by")
    voided_vouchers = relationship("Voucher", foreign_keys="Voucher.voided_by_id", back_populates="voided_by")
    audit_logs = relationship("AuditLog", back_populates="user")


class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_key = Column(String(100), unique=True, nullable=False)  # e.g., 'sale:create', 'system:void'
    description = Column(String(200), nullable=True)
    
    # Relationships
    user_links = relationship("UserPermission", back_populates="permission", cascade="all, delete-orphan")


class UserPermission(Base):
    __tablename__ = "user_permissions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    is_allowed = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="permissions")
    permission = relationship("Permission", back_populates="user_links")
    
    __table_args__ = (
        UniqueConstraint("user_id", "permission_id", name="uq_user_permission"),
    )

# ============================================================
# INVENTORY (ARTICLES) MODELS
# ============================================================

class Article(Base):
    """
    Unified model mapping both raw ingredients (Cement, Sand, Scoria)
    and finished products (HCB Blocks, Tiles, Pipes).
    """
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)  # e.g., 'CEMENT', 'HCB15N'
    name = Column(String(150), nullable=False)  # display name (supports Amharic)
    category = Column(String(20), nullable=False)  # 'RAW' or 'FINISHED'
    unit = Column(String(20), nullable=False)  # 'kg', 'm3', 'liter', 'piece', 'm2'
    barcode = Column(String(100), unique=True, nullable=True)
    cost_price = Column(Float, default=0.0)  # average raw cost
    sell_price = Column(Float, default=0.0)  # selling rate for finished articles
    warehouse_qty = Column(Float, default=0.0)  # Cached warehouse quantity
    shop_floor_qty = Column(Float, default=0.0)  # Cached shop floor quantity
    low_stock_alert = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)  # soft-delete flag
    
    # Relationships
    ledger_entries = relationship("InventoryLedger", back_populates="article")
    # For formulas, an article can be a product or a raw ingredient
    formulas_as_product = relationship("Formula", foreign_keys="Formula.product_id", back_populates="product", cascade="all, delete-orphan")
    formulas_as_ingredient = relationship("Formula", foreign_keys="Formula.material_id", back_populates="material", cascade="all, delete-orphan")


class Formula(Base):
    """
    Quantity recipe definitions. Date-versioned by effective_from.
    """
    __tablename__ = "formulas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    material_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    qty_per_unit = Column(Float, nullable=False)  # raw qty per 1 finished unit
    effective_from = Column(String(20), nullable=False)  # Format: 'YYYY-MM-DD'
    
    # Relationships
    product = relationship("Article", foreign_keys=[product_id], back_populates="formulas_as_product")
    material = relationship("Article", foreign_keys=[material_id], back_populates="formulas_as_ingredient")
    
    __table_args__ = (
        UniqueConstraint("product_id", "material_id", "effective_from", name="uq_product_material_version"),
    )

# ============================================================
# VOUCHER & LEDGER (DOUBLE-ENTRY) MODELS
# ============================================================

class Voucher(Base):
    """
    Central transaction header recording any inventory movements or financial changes.
    """
    __tablename__ = "vouchers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    voucher_no = Column(String(50), unique=True, nullable=False)
    voucher_type = Column(String(30), nullable=False)  # 'SRV', 'PRODUCTION', 'CASH_SALE', 'CREDIT_SALE', etc.
    state = Column(String(20), nullable=False, default="POSTED")  # 'POSTED', 'VOIDED'
    created_at = Column(DateTime, default=datetime.now)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    voided_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Metadata fields
    note = Column(String(500), nullable=True)
    customer_name = Column(String(150), nullable=True)
    made_by = Column(String(100), nullable=True)
    
    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="created_vouchers")
    voided_by = relationship("User", foreign_keys=[voided_by_id], back_populates="voided_vouchers")
    inventory_entries = relationship("InventoryLedger", back_populates="voucher", cascade="all, delete-orphan")
    journal_entries = relationship("JournalEntry", back_populates="voucher", cascade="all, delete-orphan")


class InventoryLedger(Base):
    """
    Append-only physical stock transaction log.
    Positive values add inventory, negative values deduct it.
    """
    __tablename__ = "inventory_ledger"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    voucher_id = Column(Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    qty_change = Column(Float, nullable=False)  # signed decimal
    cost_rate = Column(Float, default=0.0)  # average unit cost at posting time
    location = Column(String(20), nullable=False)  # 'WAREHOUSE' or 'SHOP_FLOOR'
    
    # Relationships
    voucher = relationship("Voucher", back_populates="inventory_entries")
    article = relationship("Article", back_populates="ledger_entries")


class JournalEntry(Base):
    """
    Double-entry accounting transaction details. Debits must equal credits.
    """
    __tablename__ = "journal_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    voucher_id = Column(Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False)
    account_code = Column(String(50), nullable=False)  # e.g., 'GL-1102 Raw Stock', 'GL-4101 Sales'
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    
    # Relationships
    voucher = relationship("Voucher", back_populates="journal_entries")

# ============================================================
# AUDIT & METADATA
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class AppMeta(Base):
    __tablename__ = "app_meta"
    
    key = Column(String(100), primary_key=True)
    value = Column(String(200), nullable=True)


# ============================================================
# NEW FEATURE MIGRATIONS (v3/v4 EXPANSION)
# ============================================================

class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(String(200), nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(String(200), nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class CustomerPayment(Base):
    __tablename__ = "customer_payments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_name = Column(String(150), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(String(20), nullable=False)  # 'YYYY-MM-DD'
    method = Column(String(50), nullable=True)  # 'cash', 'bank', etc.
    note = Column(String(500), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    voucher_no = Column(String(50), nullable=True)


class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    expense_date = Column(String(20), nullable=False)  # 'YYYY-MM-DD'
    description = Column(String(500), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    voucher_no = Column(String(50), nullable=True)


class Waste(Base):
    __tablename__ = "waste"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    reason = Column(String(200), nullable=True)
    waste_date = Column(String(20), nullable=False)  # 'YYYY-MM-DD'
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    voucher_no = Column(String(50), nullable=True)

