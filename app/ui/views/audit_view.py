"""Audit log view (admin only)."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView)

from app.services import audit_service
from app.ui.widgets.search_box import SearchBox

ACTION_LABELS = {
    "login_success":     "Login (success)",
    "login_failure":     "Login (FAILED)",
    "password_change":   "Password changed",
    "user_create":       "User created",
    "user_delete":       "User deleted",
    "sale_create":       "Sale recorded",
    "sale_edit":         "Sale edited",
    "sale_delete":       "Sale deleted",
    "production_create": "Production recorded",
    "production_edit":   "Production edited",
    "production_delete": "Production deleted",
    "stock_purchase":    "Stock purchased",
    "stock_adjust":      "Stock adjusted",
    "payment_create":    "Payment received",
    "expense_create":    "Expense recorded",
    "expense_delete":    "Expense deleted",
    "waste_record":      "Waste recorded",
    "product_update":    "Product changed",
    "formula_create":    "Formula created",
    "formula_update":    "Formula updated",
}


class AuditLogView(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self._build(); self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        try: self.refresh()
        except Exception: pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)
        head = QHBoxLayout()
        t = QLabel("Audit Log"); t.setObjectName("pagetitle")
        head.addWidget(t); head.addStretch()
        rb = QPushButton("⟳ Refresh"); rb.setObjectName("secondary"); rb.clicked.connect(self.refresh)
        head.addWidget(rb)
        outer.addLayout(head)

        info = QLabel("Records every edit, delete, or other notable action by users. "
                      "Read-only — admins cannot remove entries.")
        info.setObjectName("hint"); info.setWordWrap(True)
        outer.addWidget(info)

        self.search = SearchBox(None, placeholder="Search audit log…")
        outer.addWidget(self.search)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["When","User","Action","Details"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search.attach(self.table)
        outer.addWidget(self.table)

    def refresh(self):
        rows = audit_service.list_entries(limit=1000)
        self.table.setRowCount(len(rows))
        for r, a in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(a["created_at"]))
            self.table.setItem(r, 1, QTableWidgetItem(a["username"]))
            label = ACTION_LABELS.get(a["action"], a["action"])
            action_item = QTableWidgetItem(label)
            if a["action"].endswith("_delete") or a["action"] == "login_failure":
                from PyQt5.QtCore import Qt
                action_item.setForeground(Qt.red)
            self.table.setItem(r, 2, action_item)
            self.table.setItem(r, 3, QTableWidgetItem(a.get("details") or ""))
        self.search.reapply()
