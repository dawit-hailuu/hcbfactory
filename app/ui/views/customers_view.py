"""Customers view: balances + record payment + statement of account."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
                             QComboBox, QMessageBox)

from app.services import customer_service
from app.ui.widgets.search_box import SearchBox


class _PaymentDialog(QDialog):
    def __init__(self, user, default_customer=None, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("Receive Payment")
        self.setMinimumWidth(400)
        f = QFormLayout(self)

        from PyQt5.QtWidgets import QCompleter
        self.customer = QLineEdit()
        self.customer.setPlaceholderText("Customer name")
        names = [c["name"] for c in customer_service.customer_balances()]
        if names:
            completer = QCompleter(names, self.customer)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.customer.setCompleter(completer)
        if default_customer:
            self.customer.setText(default_customer)
        f.addRow("Customer:", self.customer)

        self.amount = QDoubleSpinBox(); self.amount.setRange(0, 1_000_000_000); self.amount.setDecimals(2)
        f.addRow("Amount (ETB):", self.amount)

        self.method = QComboBox(); self.method.setEditable(True)
        self.method.addItems(["cash","bank transfer","check","mobile money"])
        f.addRow("Payment method:", self.method)

        self.note = QLineEdit(); self.note.setPlaceholderText("Receipt # or comment")
        f.addRow("Note:", self.note)

        br = QHBoxLayout()
        self.ok_btn = QPushButton("Record"); self.ok_btn.setObjectName("success"); self.ok_btn.clicked.connect(self._save)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(self.ok_btn); br.addWidget(cancel); f.addRow(br)
        self.recorded_voucher = None

    def _save(self):
        name = self.customer.text().strip()
        if not name or self.amount.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Customer name and a positive amount are required.")
            return
        try:
            vno = customer_service.record_payment(
                name, self.amount.value(),
                method=self.method.currentText() or None,
                note=self.note.text() or None,
                user_id=self.user["id"],
            )
            self.recorded_voucher = vno
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot record", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class _StatementDialog(QDialog):
    def __init__(self, customer_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Statement — {customer_name}")
        self.resize(780, 460)
        v = QVBoxLayout(self)

        v.addWidget(QLabel(f"<b>Customer:</b> {customer_name}"))

        rows = customer_service.customer_statement(customer_name)
        if not rows:
            empty = QLabel("No sales or payments recorded for this customer yet.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setObjectName("emptystate")
            v.addWidget(empty)
        else:
            tbl = QTableWidget(len(rows), 5)
            tbl.setHorizontalHeaderLabels(["Date","Kind","Detail","Amount (ETB)","Paid Now"])
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setAlternatingRowColors(True)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            for r, row in enumerate(rows):
                tbl.setItem(r, 0, QTableWidgetItem(row["date"]))
                kind_label = "Sale" if row["kind"] == "sale" else "Payment"
                kind_item = QTableWidgetItem(kind_label)
                if row["kind"] == "payment":
                    kind_item.setForeground(Qt.darkGreen)
                tbl.setItem(r, 1, kind_item)
                tbl.setItem(r, 2, QTableWidgetItem(row["detail"]))
                tbl.setItem(r, 3, QTableWidgetItem(f"{row['amount']:,.2f}"))
                tbl.setItem(r, 4, QTableWidgetItem(f"{row['paid_now']:,.2f}"))
            v.addWidget(tbl)

        b = QPushButton("Close"); b.setObjectName("secondary"); b.clicked.connect(self.accept)
        v.addWidget(b, alignment=Qt.AlignRight)


class CustomersView(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self._build()
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        try: self.refresh()
        except Exception: pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)
        head = QHBoxLayout()
        t = QLabel("Customers & Balances")
        t.setObjectName("pagetitle")
        head.addWidget(t); head.addStretch()
        pay = QPushButton("💵 Record Payment"); pay.setObjectName("success")
        pay.clicked.connect(lambda: self._payment(None))
        head.addWidget(pay)
        outer.addLayout(head)

        self.search = SearchBox(None, placeholder="Search customers by name…")
        outer.addWidget(self.search)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Customer","Sales","Billed","Paid on Sale","Extra Payments","Balance Due"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search.attach(self.table, columns=[0])
        self.table.cellDoubleClicked.connect(self._open_statement)
        outer.addWidget(self.table)

        # Empty state hint (toggled by refresh)
        self.empty_hint = QLabel("")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setObjectName("emptystate")
        self.empty_hint.setWordWrap(True)
        self.empty_hint.hide()
        outer.addWidget(self.empty_hint)

        hint = QLabel("Double-click a customer to see their statement of account.")
        hint.setObjectName("hint")
        outer.addWidget(hint)

    def refresh(self):
        rows = customer_service.customer_balances()
        self.table.setRowCount(len(rows))
        for r, c in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(c["name"]))
            self.table.setItem(r, 1, QTableWidgetItem(str(c["sale_count"])))
            self.table.setItem(r, 2, QTableWidgetItem(f"{c['billed']:,.2f}"))
            self.table.setItem(r, 3, QTableWidgetItem(f"{c['paid_on_sale']:,.2f}"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{c['extra_payments']:,.2f}"))
            bal = c["balance"]
            it = QTableWidgetItem(f"{bal:,.2f}")
            if bal > 0:
                it.setForeground(Qt.red)
            elif bal < 0:
                it.setForeground(Qt.darkGreen)
            self.table.setItem(r, 5, it)
        # Empty state
        if not rows:
            self.empty_hint.setText(
                "No customers yet. Record a sale to start tracking customers,\n"
                "or use the “Record Payment” button to log a payment from a new customer."
            )
            self.empty_hint.show()
        else:
            self.empty_hint.hide()
        self.search.reapply()

    def _payment(self, name):
        dlg = _PaymentDialog(self.user, default_customer=name, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            vno = dlg.recorded_voucher or "-"
            QMessageBox.information(self, "Payment recorded",
                                    f"Receipt {vno} recorded. You can re-print it any time from Tools.")
            self.refresh()

    def _open_statement(self, row, _col):
        name_item = self.table.item(row, 0)
        if name_item:
            _StatementDialog(name_item.text(), self).exec_()
