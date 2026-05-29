"""Dialog to edit a production run (admin only)."""
from PyQt5.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QDoubleSpinBox,
                             QLineEdit, QPushButton, QMessageBox, QLabel)
from app.services import production_service


class EditProductionDialog(QDialog):
    def __init__(self, production_id, user, parent=None):
        super().__init__(parent)
        self.production_id = production_id
        self.user = user
        prod = production_service.get_production(production_id)
        if prod is None:
            raise ValueError("Production not found")
        self.setWindowTitle(f"Edit Production #{production_id}")
        self.setMinimumWidth(420)
        f = QFormLayout(self)

        f.addRow(QLabel(f"<b>{prod['product_code']}</b> — {prod['product_name']}"))
        f.addRow(QLabel(f"Date: {prod['production_date']}"))

        self.qty = QDoubleSpinBox(); self.qty.setRange(0, 1_000_000); self.qty.setDecimals(2)
        self.qty.setValue(prod["quantity"])
        f.addRow("Quantity:", self.qty)

        self.made_by = QLineEdit(prod.get("made_by") or "")
        f.addRow("Made by:", self.made_by)

        self.note = QLineEdit(prod.get("note") or "")
        f.addRow("Note:", self.note)

        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Reason for editing (required)")
        f.addRow("Reason:", self.reason)

        warn = QLabel(
            "<i>Editing will reverse the original run (materials returned, stock removed) "
            "and create a corrected one. Both events are logged to the audit log.</i>"
        )
        warn.setWordWrap(True); warn.setObjectName("hint")
        f.addRow(warn)

        br = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self._save)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(ok); br.addWidget(cancel)
        f.addRow(br)

    def _save(self):
        if not self.reason.text().strip():
            QMessageBox.warning(self, "Reason required", "Please provide a reason."); return
        try:
            production_service.update_production(
                self.production_id,
                quantity=self.qty.value(),
                made_by=self.made_by.text().strip() or None,
                note=self.note.text() or None,
                user_id=self.user["id"],
                reason=self.reason.text().strip(),
            )
            QMessageBox.information(self, "Saved", "Production updated.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot save", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
