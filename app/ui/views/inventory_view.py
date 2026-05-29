"""Inventory view: raw materials list + add stock dialog + history view."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDialog, QFormLayout, QComboBox,
                             QDoubleSpinBox, QLineEdit, QMessageBox, QTabWidget)

from app.services import inventory_service


class _AddStockDialog(QDialog):
    def __init__(self, materials, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Stock")
        self.setMinimumWidth(380)
        form = QFormLayout(self)

        self.mat_combo = QComboBox()
        for m in materials:
            self.mat_combo.addItem(f"{m['name']} ({m['unit']})", m["id"])
        form.addRow("Material:", self.mat_combo)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 1_000_000); self.qty.setDecimals(3); self.qty.setValue(0)
        form.addRow("Quantity:", self.qty)

        self.cost = QDoubleSpinBox()
        self.cost.setRange(0, 1_000_000); self.cost.setDecimals(2); self.cost.setValue(0)
        form.addRow("Unit Cost (ETB, optional):", self.cost)

        # Supplier with autocomplete from previous purchases
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QCompleter
        from app.services import inventory_service as _inv
        self.supplier = QLineEdit()
        self.supplier.setPlaceholderText("Supplier name (optional)")
        completer = QCompleter(_inv.distinct_suppliers(), self.supplier)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.supplier.setCompleter(completer)
        form.addRow("Supplier:", self.supplier)

        self.note = QLineEdit()
        self.note.setPlaceholderText("Invoice number, comment, etc.")
        form.addRow("Note:", self.note)

        btn_row = QHBoxLayout()
        self.ok = QPushButton("Add"); self.ok.setObjectName("success"); self.ok.clicked.connect(self.accept)
        self.ok.setEnabled(False)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.ok); btn_row.addWidget(cancel)
        form.addRow(btn_row)

        # Enable Add only when qty > 0
        self.qty.valueChanged.connect(lambda v: self.ok.setEnabled(v > 0))


class _AdjustDialog(QDialog):
    def __init__(self, material, parent=None):
        super().__init__(parent)
        self._material = material
        self.setWindowTitle(f"Adjust Stock — {material['name']}")
        self.setMinimumWidth(380)
        form = QFormLayout(self)

        cur = QLabel(f"Current: <b>{material['current_stock']:.3f} {material['unit']}</b>")
        form.addRow(cur)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 1_000_000); self.qty.setDecimals(3)
        self.qty.setValue(material["current_stock"])
        self.qty.valueChanged.connect(self._update_preview)
        form.addRow("New stock value:", self.qty)

        self.preview = QLabel("")
        self.preview.setObjectName("hintmedium")
        form.addRow("Change:", self.preview)
        self._update_preview()

        self.note = QLineEdit(); self.note.setPlaceholderText("Reason for adjustment (e.g. physical count)")
        form.addRow("Note:", self.note)

        btn_row = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        form.addRow(btn_row)

    def _update_preview(self):
        delta = self.qty.value() - self._material["current_stock"]
        if abs(delta) < 1e-9:
            self.preview.setText("(no change)")
            self.preview.setObjectName("hintmedium")
        elif delta > 0:
            self.preview.setText(f"+ {delta:.3f} {self._material['unit']}")
            self.preview.setStyleSheet("color: #27AE60; font-size: 12px; font-weight: bold;")
        else:
            self.preview.setText(f"− {abs(delta):.3f} {self._material['unit']}")
            self.preview.setStyleSheet("color: #C0392B; font-size: 12px; font-weight: bold;")


class _SettingsDialog(QDialog):
    def __init__(self, material, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Settings — {material['name']}")
        self.setMinimumWidth(360)
        form = QFormLayout(self)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0, 1_000_000); self.threshold.setDecimals(3)
        self.threshold.setValue(material["low_stock_alert"])
        form.addRow("Low-stock alert threshold:", self.threshold)

        self.cost = QDoubleSpinBox()
        self.cost.setRange(0, 1_000_000); self.cost.setDecimals(2)
        self.cost.setValue(material["unit_cost"])
        form.addRow("Unit cost (ETB):", self.cost)

        btn_row = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        form.addRow(btn_row)


class InventoryView(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self._build()
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        try: self.refresh()
        except Exception: pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)

        head = QHBoxLayout()
        t = QLabel("Inventory — Raw Materials")
        t.setObjectName("pagetitle")
        head.addWidget(t); head.addStretch()
        add = QPushButton("➕ Add Stock"); add.setObjectName("success"); add.clicked.connect(self._add_stock)
        head.addWidget(add)
        refresh = QPushButton("⟳ Refresh"); refresh.setObjectName("secondary"); refresh.clicked.connect(self.refresh)
        head.addWidget(refresh)
        outer.addLayout(head)

        self.tabs = QTabWidget()

        # Tab 1: current stock
        tab1 = QWidget(); v1 = QVBoxLayout(tab1)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Code", "Material", "Current", "Unit", "Low Alert", "Unit Cost", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        v1.addWidget(self.table)
        self.tabs.addTab(tab1, "Current Stock")

        # Tab 2: history
        tab2 = QWidget(); v2 = QVBoxLayout(tab2)
        from app.ui.widgets.search_box import SearchBox
        self.search = SearchBox(None, placeholder="Search stock movements by material, type, user, note, date…")
        v2.addWidget(self.search)
        self.hist = QTableWidget(0, 10)
        self.hist.setHorizontalHeaderLabels(
            ["When", "Voucher", "Material", "Qty", "Unit", "Type",
             "Supplier", "Unit Cost", "User", "Note"])
        self.hist.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hist.verticalHeader().setVisible(False)
        self.hist.setAlternatingRowColors(True)
        self.hist.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search.attach(self.hist)
        v2.addWidget(self.hist)
        self.tabs.addTab(tab2, "Stock History")

        outer.addWidget(self.tabs)

    def refresh(self):
        mats = inventory_service.list_materials()
        self.table.setRowCount(len(mats))
        for r, m in enumerate(mats):
            self.table.setItem(r, 0, QTableWidgetItem(m["code"]))
            self.table.setItem(r, 1, QTableWidgetItem(m["name"]))
            stock_item = QTableWidgetItem(f"{m['current_stock']:.3f}")
            if m["current_stock"] <= m["low_stock_alert"]:
                stock_item.setForeground(Qt.red)
            self.table.setItem(r, 2, stock_item)
            self.table.setItem(r, 3, QTableWidgetItem(m["unit"]))
            self.table.setItem(r, 4, QTableWidgetItem(f"{m['low_stock_alert']:.3f}"))
            self.table.setItem(r, 5, QTableWidgetItem(f"{m['unit_cost']:.2f}"))

            actions = QWidget(); h = QHBoxLayout(actions); h.setContentsMargins(0,0,0,0); h.setSpacing(4)
            adj = QPushButton("Adjust"); adj.clicked.connect(lambda _, mid=m["id"]: self._adjust(mid))
            settings = QPushButton("⚙"); settings.setMaximumWidth(34)
            settings.clicked.connect(lambda _, mid=m["id"]: self._settings(mid))
            h.addWidget(adj); h.addWidget(settings)
            self.table.setCellWidget(r, 6, actions)

        # history
        hist = inventory_service.stock_history(limit=300)
        self.hist.setRowCount(len(hist))
        TYPE_LABELS = {
            "purchase":   "Purchase",
            "production": "Used in production",
            "adjustment": "Adjustment",
            "initial":    "Initial stock",
        }
        for r, h in enumerate(hist):
            self.hist.setItem(r, 0, QTableWidgetItem(h["created_at"]))
            self.hist.setItem(r, 1, QTableWidgetItem(h.get("voucher_no") or ""))
            self.hist.setItem(r, 2, QTableWidgetItem(h["material_name"]))
            item = QTableWidgetItem(f"{h['qty']:+.3f}")
            item.setForeground(Qt.darkGreen if h["qty"] > 0 else Qt.red)
            self.hist.setItem(r, 3, item)
            self.hist.setItem(r, 4, QTableWidgetItem(h["unit"]))
            self.hist.setItem(r, 5, QTableWidgetItem(TYPE_LABELS.get(h["movement"], h["movement"])))
            self.hist.setItem(r, 6, QTableWidgetItem(h.get("supplier_name") or ""))
            uc = h.get("unit_cost")
            self.hist.setItem(r, 7, QTableWidgetItem(f"{uc:,.2f}" if uc else ""))
            self.hist.setItem(r, 8, QTableWidgetItem(h.get("user_name") or ""))
            self.hist.setItem(r, 9, QTableWidgetItem(h.get("note") or ""))
        if hasattr(self, "search"):
            self.search.reapply()

    def _add_stock(self):
        mats = inventory_service.list_materials()
        dlg = _AddStockDialog(mats, self)
        if dlg.exec_() != QDialog.Accepted: return
        if dlg.qty.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Quantity must be greater than zero."); return
        try:
            inventory_service.add_stock(
                material_id=dlg.mat_combo.currentData(),
                qty=dlg.qty.value(),
                user_id=self.user["id"],
                note=dlg.note.text() or None,
                unit_cost=dlg.cost.value() if dlg.cost.value() > 0 else None,
                supplier_name=dlg.supplier.text().strip() or None,
            )
            QMessageBox.information(self, "Done", "Stock added successfully.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _adjust(self, material_id):
        m = inventory_service.get_material(material_id)
        dlg = _AdjustDialog(m, self)
        if dlg.exec_() != QDialog.Accepted: return
        try:
            inventory_service.adjust_stock(material_id, dlg.qty.value(),
                                           user_id=self.user["id"],
                                           note=dlg.note.text() or "manual adjustment")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _settings(self, material_id):
        m = inventory_service.get_material(material_id)
        dlg = _SettingsDialog(m, self)
        if dlg.exec_() != QDialog.Accepted: return
        inventory_service.update_material_settings(
            material_id,
            low_stock_alert=dlg.threshold.value(),
            unit_cost=dlg.cost.value(),
        )
        self.refresh()
