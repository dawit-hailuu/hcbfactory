"""Expenses view: track operating costs."""
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
                             QComboBox, QDateEdit, QMessageBox)

from app.services import expense_service
from app.ui.widgets.search_box import SearchBox


class _ExpenseDialog(QDialog):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.recorded_voucher = None
        self.setWindowTitle("Record Expense")
        self.setMinimumWidth(380)
        f = QFormLayout(self)

        self.category = QComboBox(); self.category.addItems(expense_service.CATEGORIES)
        f.addRow("Category:", self.category)

        self.amount = QDoubleSpinBox(); self.amount.setRange(0, 1_000_000_000); self.amount.setDecimals(2)
        f.addRow("Amount (ETB):", self.amount)

        self.date = QDateEdit(); self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd"); self.date.setDate(QDate.currentDate())
        f.addRow("Date:", self.date)

        self.desc = QLineEdit(); self.desc.setPlaceholderText("What was this for?")
        f.addRow("Description:", self.desc)

        br = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self._save)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(ok); br.addWidget(cancel); f.addRow(br)

    def _save(self):
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Amount must be greater than zero."); return
        try:
            self.recorded_voucher = expense_service.record_expense(
                self.category.currentText(),
                self.amount.value(),
                description=self.desc.text() or None,
                expense_date=self.date.date().toString("yyyy-MM-dd"),
                user_id=self.user["id"],
            )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot record", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class ExpensesView(QWidget):
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
        t = QLabel("Expenses"); t.setObjectName("pagetitle")
        head.addWidget(t); head.addStretch()
        add = QPushButton("➕ Record Expense"); add.setObjectName("success")
        add.clicked.connect(self._new)
        head.addWidget(add)
        outer.addLayout(head)

        self.search = SearchBox(None, placeholder="Search expenses…")
        outer.addWidget(self.search)

        # Summary row
        self.summary_lbl = QLabel("")
        self.summary_lbl.setObjectName("summarybox")
        outer.addWidget(self.summary_lbl)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Voucher","Date","Category","Amount (ETB)","Description","User","Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search.attach(self.table)
        outer.addWidget(self.table)

    def refresh(self):
        rows = expense_service.list_expenses(limit=1000)
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(e.get("voucher_no") or ""))
            self.table.setItem(r, 1, QTableWidgetItem(e["expense_date"]))
            self.table.setItem(r, 2, QTableWidgetItem(e["category"]))
            self.table.setItem(r, 3, QTableWidgetItem(f"{e['amount']:,.2f}"))
            self.table.setItem(r, 4, QTableWidgetItem(e.get("description") or ""))
            self.table.setItem(r, 5, QTableWidgetItem(e.get("user_name") or ""))
            # Actions cell with print + (admin) delete
            from PyQt5.QtWidgets import QWidget, QHBoxLayout
            from app.ui.voucher_helper import print_voucher
            actions = QWidget(); ah = QHBoxLayout(actions); ah.setContentsMargins(0,0,0,0); ah.setSpacing(4)
            pb = QPushButton("🖨"); pb.setMaximumWidth(34); pb.setToolTip("Print voucher")
            pb.clicked.connect(lambda _, v=e.get("voucher_no"): print_voucher(self, v))
            ah.addWidget(pb)
            if self.user["role"] == "admin":
                db = QPushButton("🗑"); db.setObjectName("danger"); db.setMaximumWidth(34)
                db.clicked.connect(lambda _, eid=e["id"]: self._delete(eid))
                ah.addWidget(db)
            self.table.setCellWidget(r, 6, actions)
        # Summary across all
        totals = expense_service.expense_summary("2000-01-01", "2100-12-31")
        all_sum = sum(t["total"] for t in totals)
        if totals:
            parts = "  ·  ".join(f"{t['category']}: {t['total']:,.0f}" for t in totals[:5])
            self.summary_lbl.setText(f"Total recorded: {all_sum:,.2f} ETB   ·   {parts}")
        else:
            self.summary_lbl.setText("No expenses recorded yet. Click “Record Expense” to add the first one.")
        self.search.reapply()

    def _new(self):
        dlg = _ExpenseDialog(self.user, self)
        if dlg.exec_() == QDialog.Accepted:
            vno = getattr(dlg, "recorded_voucher", None) or "-"
            QMessageBox.information(self, "Expense recorded", f"Voucher {vno} saved.")
            self.refresh()

    def _delete(self, eid):
        if QMessageBox.question(self, "Delete expense", "Delete this expense?") != QMessageBox.Yes:
            return
        expense_service.delete_expense(eid, user_id=self.user["id"])
        self.refresh()
