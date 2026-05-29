"""
Inventory view: raw materials list + SRV dialog + SIV dialog + SAV (adjust) dialog.
Explicitly matches the 8 core vouchers catalog.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDialog, QFormLayout, QComboBox,
                             QDoubleSpinBox, QLineEdit, QMessageBox, QTabWidget)

from app.services import inventory_service


class _SRVDialog(QDialog):
    """Store Receipt Voucher (SRV) dialog."""
    def __init__(self, materials, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Store Receipt Voucher (SRV) — Inbound Raw Materials")
        self.setMinimumWidth(400)
        form = QFormLayout(self)

        self.mat_combo = QComboBox()
        for m in materials:
            self.mat_combo.addItem(f"{m['name']} ({m['unit']})", m["id"])
        form.addRow("Material:", self.mat_combo)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 1_000_000); self.qty.setDecimals(3); self.qty.setValue(0)
        form.addRow("Quantity Received:", self.qty)

        self.cost = QDoubleSpinBox()
        self.cost.setRange(0, 1_000_000); self.cost.setDecimals(2); self.cost.setValue(0)
        form.addRow("Unit Cost (ETB, optional):", self.cost)

        self.note = QLineEdit()
        self.note.setPlaceholderText("Supplier name / Invoice reference")
        form.addRow("Reference/Supplier Note:", self.note)

        btn_row = QHBoxLayout()
        ok = QPushButton("Post SRV"); ok.setObjectName("success"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        form.addRow(btn_row)


class _SIVDialog(QDialog):
    """Store Issue Voucher (SIV) dialog."""
    def __init__(self, materials, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Store Issue Voucher (SIV) — Issue Raw Materials")
        self.setMinimumWidth(400)
        form = QFormLayout(self)

        self.mat_combo = QComboBox()
        for m in materials:
            self.mat_combo.addItem(f"{m['name']} ({m['unit']})", m["id"])
        form.addRow("Material to Issue:", self.mat_combo)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 1_000_000); self.qty.setDecimals(3); self.qty.setValue(0)
        form.addRow("Quantity Issued:", self.qty)

        self.note = QLineEdit()
        self.note.setPlaceholderText("Reason for issue (e.g., disposal, damage, transfer)")
        form.addRow("Reason Note:", self.note)

        btn_row = QHBoxLayout()
        ok = QPushButton("Post SIV"); ok.setObjectName("danger"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        form.addRow(btn_row)


class _AdjustDialog(QDialog):
    """Stock Adjustment Voucher (SAV) dialog."""
    def __init__(self, material, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Stock Adjustment Voucher (SAV) — {material['name']}")
        self.setMinimumWidth(380)
        form = QFormLayout(self)

        cur = QLabel(f"Current System Stock: {material['current_stock']:.3f} {material['unit']}")
        form.addRow(cur)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 1_000_000); self.qty.setDecimals(3)
        self.qty.setValue(material["current_stock"])
        form.addRow("Physical Counted Stock:", self.qty)

        self.note = QLineEdit(); self.note.setPlaceholderText("Discrepancy reason (e.g. audit, loss)")
        form.addRow("Audit Note:", self.note)

        btn_row = QHBoxLayout()
        ok = QPushButton("Post SAV"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok); btn_row.addWidget(cancel)
        form.addRow(btn_row)


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
        try: 
            self.refresh()
        except Exception: 
            pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)

        head = QHBoxLayout()
        t = QLabel("Inventory — Raw Materials")
        t.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        head.addWidget(t)
        head.addStretch()

        # Voucher creation triggers
        srv_btn = QPushButton("➕ Post SRV"); srv_btn.setObjectName("success"); srv_btn.clicked.connect(self._post_srv)
        head.addWidget(srv_btn)

        siv_btn = QPushButton("➖ Post SIV"); siv_btn.setObjectName("danger"); siv_btn.clicked.connect(self._post_siv)
        head.addWidget(siv_btn)

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
        self.hist = QTableWidget(0, 7)
        self.hist.setHorizontalHeaderLabels(
            ["When", "Material", "Qty", "Unit", "Voucher Type", "User", "Reference/Note"])
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
            adj = QPushButton("Post SAV"); adj.clicked.connect(lambda _, mid=m["id"]: self._adjust(mid))
            settings = QPushButton("⚙"); settings.setMaximumWidth(34)
            settings.clicked.connect(lambda _, mid=m["id"]: self._settings(mid))
            h.addWidget(adj); h.addWidget(settings)
            self.table.setCellWidget(r, 6, actions)

        # history
        hist = inventory_service.stock_history(limit=300)
        self.hist.setRowCount(len(hist))
        for r, h in enumerate(hist):
            self.hist.setItem(r, 0, QTableWidgetItem(h["created_at"]))
            self.hist.setItem(r, 1, QTableWidgetItem(h["material_name"]))
            item = QTableWidgetItem(f"{h['qty']:+.3f}")
            item.setForeground(Qt.darkGreen if h["qty"] > 0 else Qt.red)
            self.hist.setItem(r, 2, item)
            self.hist.setItem(r, 3, QTableWidgetItem(h["unit"]))
            self.hist.setItem(r, 4, QTableWidgetItem(h["movement"]))
            self.hist.setItem(r, 5, QTableWidgetItem(h.get("user_name") or ""))
            
            # Combine voucher code reference with user notes
            ref_and_note = f"[{h.get('reference') or ''}] {h.get('note') or ''}"
            self.hist.setItem(r, 6, QTableWidgetItem(ref_and_note))
        if hasattr(self, "search"):
            self.search.reapply()

    def _post_srv(self):
        mats = inventory_service.list_materials()
        dlg = _SRVDialog(mats, self)
        if dlg.exec_() != QDialog.Accepted: 
            return
        if dlg.qty.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Quantity must be greater than zero.")
            return
        try:
            inventory_service.add_stock(
                material_id=dlg.mat_combo.currentData(),
                qty=dlg.qty.value(),
                user_id=self.user["id"],
                note=dlg.note.text() or None,
                unit_cost=dlg.cost.value() if dlg.cost.value() > 0 else None,
            )
            QMessageBox.information(self, "Posted", "Store Receipt Voucher (SRV) posted successfully.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _post_siv(self):
        mats = inventory_service.list_materials()
        dlg = _SIVDialog(mats, self)
        if dlg.exec_() != QDialog.Accepted: 
            return
        if dlg.qty.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Quantity must be greater than zero.")
            return
        try:
            inventory_service.issue_stock(
                material_id=dlg.mat_combo.currentData(),
                qty=dlg.qty.value(),
                user_id=self.user["id"],
                note=dlg.note.text() or None
            )
            QMessageBox.information(self, "Posted", "Store Issue Voucher (SIV) posted successfully.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _adjust(self, material_id):
        m = inventory_service.get_material(material_id)
        dlg = _AdjustDialog(m, self)
        if dlg.exec_() != QDialog.Accepted: 
            return
        try:
            inventory_service.adjust_stock(
                material_id=material_id,
                new_qty=dlg.qty.value(),
                user_id=self.user["id"],
                note=dlg.note.text() or "manual adjustment"
            )
            QMessageBox.information(self, "Posted", "Stock Adjustment Voucher (SAV) posted successfully.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _settings(self, material_id):
        m = inventory_service.get_material(material_id)
        dlg = _SettingsDialog(m, self)
        if dlg.exec_() != QDialog.Accepted: 
            return
        inventory_service.update_material_settings(
            material_id,
            low_stock_alert=dlg.threshold.value(),
            unit_cost=dlg.cost.value(),
        )
        self.refresh()
