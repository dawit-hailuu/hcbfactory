"""
Products + Formulas view (Admin only).

- Lists products, lets admin edit sell price and stock alert per product.
- Per-product formula editor lets admin change qty_per_unit values.
  When saved, formulas are inserted/updated with effective_from = today
  so historical production records are unaffected.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QDialog, QFormLayout, QDoubleSpinBox, QLineEdit,
                             QMessageBox, QTabWidget, QComboBox)

from app.services import product_service, inventory_service


class _FormulaEditor(QDialog):
    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"Edit Formula — {product['code']} ({product['name']})")
        self.setMinimumSize(560, 420)
        v = QVBoxLayout(self)

        unit_text = "per 1 piece" if product["input_unit"] == "piece" else "per 1 m²"
        hint = QLabel(f"All quantities are {unit_text}. "
                      f"Changes take effect today; past production records are not affected.")
        hint.setObjectName("hintmedium"); hint.setWordWrap(True)
        v.addWidget(hint)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Material", "Unit", "Quantity"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table)

        # Load
        materials = inventory_service.list_materials()
        active = product_service.get_active_formula(product["id"])
        # Build a row per material so admin can fill ones currently missing
        self.table.setRowCount(len(materials))
        self._row_to_mat = {}
        for r, m in enumerate(materials):
            self._row_to_mat[r] = m["id"]
            name_item = QTableWidgetItem(m["name"]); name_item.setFlags(Qt.ItemIsEnabled)
            unit_item = QTableWidgetItem(m["unit"]); unit_item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, unit_item)

            spin = QDoubleSpinBox()
            spin.setRange(0, 1_000_000); spin.setDecimals(7)
            current = active.get(m["id"], {}).get("qty_per_unit", 0)
            spin.setValue(current)
            self.table.setCellWidget(r, 2, spin)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        ok = QPushButton("Save"); ok.setObjectName("success"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel); btn_row.addWidget(ok)
        v.addLayout(btn_row)

    def values(self):
        """Return dict material_id -> qty."""
        out = {}
        for r, mid in self._row_to_mat.items():
            w = self.table.cellWidget(r, 2)
            out[mid] = w.value()
        return out


class _ProductSettings(QDialog):
    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Product — {product['code']}")
        self.setMinimumWidth(360)
        form = QFormLayout(self)

        self.name = QLineEdit(product["name"])
        form.addRow("Display name:", self.name)

        self.price = QDoubleSpinBox(); self.price.setRange(0, 1_000_000); self.price.setDecimals(2)
        self.price.setValue(product["sell_price"])
        unit_label = "per piece" if product["input_unit"] == "piece" else "per m²"
        form.addRow(f"Sell price (ETB, {unit_label}):", self.price)

        self.alert = QDoubleSpinBox(); self.alert.setRange(0, 1_000_000); self.alert.setDecimals(2)
        self.alert.setValue(product["low_stock_alert"])
        form.addRow("Low-stock alert:", self.alert)

        br = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(ok); br.addWidget(cancel)
        form.addRow(br)


class ProductsView(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self._build(); self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        try: self.refresh()
        except Exception: pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)

        head = QHBoxLayout()
        t = QLabel("Products & Formulas")
        t.setObjectName("pagetitle")
        head.addWidget(t); head.addStretch()
        head.addWidget(QLabel("Category:"))
        self.cat = QComboBox(); self.cat.addItems(["All","HCB","TERAZO","PIPE"])
        self.cat.currentTextChanged.connect(self.refresh)
        head.addWidget(self.cat)
        rb = QPushButton("⟳ Refresh"); rb.setObjectName("secondary"); rb.clicked.connect(self.refresh)
        head.addWidget(rb)
        outer.addLayout(head)

        # Search bar above the products table
        from app.ui.widgets.search_box import SearchBox
        self.search = SearchBox(None, placeholder="Search products by code, name, category…")
        outer.addWidget(self.search)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Code","Name","Category","Input","Sell Price","Stock","Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        # Search only across the first 4 text columns (code, name, category, input)
        self.search.attach(self.table, columns=[0, 1, 2, 3])
        outer.addWidget(self.table)

    def refresh(self):
        cat = self.cat.currentText()
        prods = product_service.list_products(None if cat == "All" else cat)
        self.table.setRowCount(len(prods))
        for r, p in enumerate(prods):
            self.table.setItem(r, 0, QTableWidgetItem(p["code"]))
            self.table.setItem(r, 1, QTableWidgetItem(p["name"]))
            self.table.setItem(r, 2, QTableWidgetItem(p["category"]))
            self.table.setItem(r, 3, QTableWidgetItem("piece" if p["input_unit"]=="piece" else "m²"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{p['sell_price']:,.2f}"))
            unit_disp = "pcs" if p["input_unit"] == "piece" else "m²"
            self.table.setItem(r, 5, QTableWidgetItem(f"{p['stock']:.2f} {unit_disp}"))

            act = QWidget(); h = QHBoxLayout(act); h.setContentsMargins(0,0,0,0); h.setSpacing(4)
            edit_f = QPushButton("Formula"); edit_f.clicked.connect(lambda _, pid=p["id"]: self._edit_formula(pid))
            edit_s = QPushButton("Settings"); edit_s.clicked.connect(lambda _, pid=p["id"]: self._edit_settings(pid))
            h.addWidget(edit_f); h.addWidget(edit_s)
            self.table.setCellWidget(r, 6, act)
        if hasattr(self, "search"):
            self.search.reapply()

    def _edit_formula(self, pid):
        if self.user["role"] != "admin":
            QMessageBox.warning(self, "Permission denied", "Admins only."); return
        p = product_service.get_product(pid)
        dlg = _FormulaEditor(p, self)
        if dlg.exec_() != QDialog.Accepted: return
        for mid, qty in dlg.values().items():
            product_service.upsert_formula(pid, mid, qty)
        QMessageBox.information(self, "Saved", "Formula updated.")
        self.refresh()

    def _edit_settings(self, pid):
        if self.user["role"] != "admin":
            QMessageBox.warning(self, "Permission denied", "Admins only."); return
        p = product_service.get_product(pid)
        dlg = _ProductSettings(p, self)
        if dlg.exec_() != QDialog.Accepted: return
        product_service.update_product(
            pid, sell_price=dlg.price.value(),
            low_stock_alert=dlg.alert.value(),
            name=dlg.name.text() or None,
        )
        self.refresh()
