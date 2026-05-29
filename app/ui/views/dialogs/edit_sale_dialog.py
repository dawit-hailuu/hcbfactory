"""Dialog to edit a sale (admin only)."""
from PyQt5.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QDoubleSpinBox,
                             QLineEdit, QPushButton, QMessageBox, QLabel)
from app.services import sales_service


class EditSaleDialog(QDialog):
    def __init__(self, sale_id, user, parent=None):
        super().__init__(parent)
        self.sale_id = sale_id
        self.user = user
        s = sales_service.get_sale(sale_id)
        if s is None:
            raise ValueError("Sale not found")
        self.setWindowTitle(f"Edit Sale #{sale_id}")
        self.setMinimumWidth(420)
        f = QFormLayout(self)

        f.addRow(QLabel(f"<b>{s['product_code']}</b> — {s['product_name']}"))
        f.addRow(QLabel(f"Date: {s['sale_date']}"))

        self.customer = QLineEdit(s.get("customer_name") or "")
        f.addRow("Customer:", self.customer)

        self.qty = QDoubleSpinBox(); self.qty.setRange(0, 1_000_000); self.qty.setDecimals(2)
        self.qty.setValue(s["quantity"])
        f.addRow("Quantity:", self.qty)

        self.price = QDoubleSpinBox(); self.price.setRange(0, 1_000_000); self.price.setDecimals(2)
        self.price.setValue(s["unit_price"])
        f.addRow("Unit price:", self.price)

        self.paid = QDoubleSpinBox(); self.paid.setRange(0, 1_000_000_000); self.paid.setDecimals(2)
        self.paid.setValue(s.get("amount_paid") or s["total"])
        f.addRow("Amount paid:", self.paid)

        self.note = QLineEdit(s.get("note") or "")
        f.addRow("Note:", self.note)

        self.reason = QLineEdit(); self.reason.setPlaceholderText("Reason for editing (required)")
        f.addRow("Reason:", self.reason)

        br = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self._save)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(ok); br.addWidget(cancel)
        f.addRow(br)

    def _save(self):
        if not self.reason.text().strip():
            QMessageBox.warning(self, "Reason required", "Please provide a reason."); return
        try:
            sales_service.update_sale(
                self.sale_id,
                customer_name=self.customer.text().strip() or None,
                quantity=self.qty.value(),
                unit_price=self.price.value(),
                amount_paid=self.paid.value(),
                note=self.note.text() or None,
                user_id=self.user["id"],
                reason=self.reason.text().strip(),
            )
            QMessageBox.information(self, "Saved", "Sale updated.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot save", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
