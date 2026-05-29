"""Dialog to record damaged / wasted finished goods."""
from PyQt5.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QComboBox,
                             QDoubleSpinBox, QLineEdit, QPushButton, QMessageBox,
                             QLabel)
from app.services import product_service, waste_service


class WasteDialog(QDialog):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("Record Damaged / Wasted Goods")
        self.setMinimumWidth(420)
        form = QFormLayout(self)

        self.category = QComboBox(); self.category.addItems(["HCB","TERAZO","PIPE"])
        self.category.currentTextChanged.connect(self._reload_products)
        form.addRow("Category:", self.category)

        self.product = QComboBox()
        self.product.currentIndexChanged.connect(self._product_changed)
        form.addRow("Product:", self.product)

        self.stock_lbl = QLabel("—"); self.stock_lbl.setObjectName("hintmedium")
        form.addRow("In stock:", self.stock_lbl)

        self.qty = QDoubleSpinBox(); self.qty.setRange(0, 1_000_000); self.qty.setDecimals(2)
        form.addRow("Quantity damaged:", self.qty)

        self.reason = QComboBox()
        self.reason.setEditable(True)
        self.reason.addItems(["cracked","broken","rejected","dropped","other"])
        form.addRow("Reason:", self.reason)

        self.note = QLineEdit(); self.note.setPlaceholderText("Optional details")
        form.addRow("Note:", self.note)

        br = QHBoxLayout()
        ok = QPushButton("Record"); ok.setObjectName("danger"); ok.clicked.connect(self._save)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(ok); br.addWidget(cancel)
        form.addRow(br)
        self._reload_products()

    def _reload_products(self):
        cat = self.category.currentText()
        self.product.clear()
        for p in product_service.list_products(cat):
            self.product.addItem(f"{p['code']} — {p['name']}", p["id"])
        self._product_changed()

    def _product_changed(self):
        pid = self.product.currentData()
        if pid is None:
            self.stock_lbl.setText("—"); return
        p = product_service.get_product(pid)
        unit = "pcs" if p["input_unit"] == "piece" else "m²"
        self.stock_lbl.setText(f"{p['stock']:.2f} {unit}")

    def _save(self):
        pid = self.product.currentData()
        if pid is None or self.qty.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Pick a product and quantity > 0."); return
        try:
            waste_service.record_waste(
                product_id=pid, quantity=self.qty.value(),
                reason=self.reason.currentText() or None,
                note=self.note.text() or None,
                user_id=self.user["id"],
            )
            QMessageBox.information(self, "Done", "Waste recorded; stock reduced.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot record", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
