"""
Logistics View: consolidates Raw Materials Stock (SRV, SIV, SAV) 
and Finished Goods Yard Transfers (FGTV).
Uses PaginatedTableWidget for logs to prevent UI freeze on large tables.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDialog, QFormLayout, QComboBox,
                             QDoubleSpinBox, QLineEdit, QMessageBox, QTabWidget, QGroupBox)

from app.services import inventory_service, product_service, auth_service
from app.ui.widgets.paginated_table import PaginatedTableWidget


class _SRVDialog(QDialog):
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


class LogisticsView(QWidget):
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        title = QLabel("Logistics Management")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        outer.addWidget(title)

        self.tabs = QTabWidget()

        # --- Tab 1: Current Raw Materials ---
        tab_raw = QWidget()
        v_raw = QVBoxLayout(tab_raw)
        
        btn_h = QHBoxLayout()
        btn_h.addWidget(QLabel("Raw Materials Inventory:"))
        btn_h.addStretch()
        
        # Voucher creation triggers
        srv_btn = QPushButton("➕ Post SRV"); srv_btn.setObjectName("success"); srv_btn.clicked.connect(self._post_srv)
        btn_h.addWidget(srv_btn)

        siv_btn = QPushButton("➖ Post SIV"); siv_btn.setObjectName("danger"); siv_btn.clicked.connect(self._post_siv)
        btn_h.addWidget(siv_btn)

        refresh_btn = QPushButton("⟳ Refresh"); refresh_btn.setObjectName("secondary"); refresh_btn.clicked.connect(self.refresh)
        btn_h.addWidget(refresh_btn)
        v_raw.addLayout(btn_h)

        self.raw_table = QTableWidget(0, 7)
        self.raw_table.setHorizontalHeaderLabels(
            ["Code", "Material", "Current", "Unit", "Low Alert", "Unit Cost", "Actions"])
        self.raw_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.raw_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.raw_table.verticalHeader().setVisible(False)
        self.raw_table.setAlternatingRowColors(True)
        self.raw_table.setEditTriggers(QTableWidget.NoEditTriggers)
        v_raw.addWidget(self.raw_table)
        
        self.tabs.addTab(tab_raw, "Raw Materials Stock")

        # --- Tab 2: Stock History (SRV, SIV, SAV) ---
        tab_hist = QWidget()
        v_hist = QVBoxLayout(tab_hist)
        
        from app.ui.widgets.search_box import SearchBox
        self.search = SearchBox(None, placeholder="Search stock movements by material, voucher, type, user, note...")
        v_hist.addWidget(self.search)
        
        self.hist_table = PaginatedTableWidget(
            ["When", "Material", "Qty", "Unit", "Voucher Type", "User", "Reference/Note"],
            lambda limit, offset: inventory_service.stock_history(limit=limit, offset=offset),
            self._fill_hist_table
        )
        self.search.attach(self.hist_table.table)
        v_hist.addWidget(self.hist_table)
        
        self.tabs.addTab(tab_hist, "Raw Stock History")

        # --- Tab 3: Yard Transfers (FGTV) ---
        tab_transfer = QWidget()
        v_trans = QVBoxLayout(tab_transfer)

        gb = QGroupBox("Record Finished Goods Transfer Voucher (FGTV)")
        form = QFormLayout(gb)

        self.trans_category = QComboBox()
        self.trans_category.addItems(["HCB", "TERAZO", "PIPE"])
        self.trans_category.currentTextChanged.connect(self._reload_transfer_products)
        form.addRow("Product Category:", self.trans_category)

        self.trans_product = QComboBox()
        self.trans_product.currentIndexChanged.connect(self._transfer_product_changed)
        form.addRow("Product Model:", self.trans_product)

        self.curing_stock_lbl = QLabel("—")
        self.curing_stock_lbl.setStyleSheet("color: #E67E22; font-weight: bold;")
        form.addRow("Curing Yard Stock (WIP):", self.curing_stock_lbl)

        self.trans_qty = QDoubleSpinBox()
        self.trans_qty.setRange(0, 1_000_000)
        self.trans_qty.setDecimals(2)
        form.addRow("Transfer Quantity to Sales Yard:", self.trans_qty)

        self.trans_note = QLineEdit()
        self.trans_note.setPlaceholderText("Optional transfer reference details")
        form.addRow("Note:", self.trans_note)

        v_trans.addWidget(gb)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_post_fgtv = QPushButton("✓ Post FGTV Transfer")
        btn_post_fgtv.setObjectName("success")
        btn_post_fgtv.clicked.connect(self._post_fgtv)
        btn_row.addWidget(btn_post_fgtv)
        v_trans.addLayout(btn_row)

        trans_title = QLabel("Yard Transfer History (FGTV)")
        trans_title.setStyleSheet("font-weight: bold; color: #1F4E79; margin-top: 10px;")
        v_trans.addWidget(trans_title)

        self.search_fgtv = SearchBox(None, placeholder="Search transfers by product, voucher, note...")
        v_trans.addWidget(self.search_fgtv)

        self.transfer_log = PaginatedTableWidget(
            ["Voucher No", "Date", "Product", "Qty", "Unit", "User", "Reference/Note"],
            lambda limit, offset: product_service.list_fgtv(limit=limit, offset=offset),
            self._fill_fgtv_table
        )
        self.search_fgtv.attach(self.transfer_log.table)
        v_trans.addWidget(self.transfer_log)

        self.tabs.addTab(tab_transfer, "Yard Transfers (FGTV)")

        outer.addWidget(self.tabs)
        self._reload_transfer_products()

    def refresh(self):
        # 1. Refresh Raw Materials Stock Table
        mats = inventory_service.list_materials()
        self.raw_table.setRowCount(len(mats))
        for r, m in enumerate(mats):
            self.raw_table.setItem(r, 0, QTableWidgetItem(m["code"]))
            self.raw_table.setItem(r, 1, QTableWidgetItem(m["name"]))
            stock_item = QTableWidgetItem(f"{m['current_stock']:.3f}")
            if m["current_stock"] <= m["low_stock_alert"]:
                stock_item.setForeground(Qt.red)
            self.raw_table.setItem(r, 2, stock_item)
            self.raw_table.setItem(r, 3, QTableWidgetItem(m["unit"]))
            self.raw_table.setItem(r, 4, QTableWidgetItem(f"{m['low_stock_alert']:.3f}"))
            self.raw_table.setItem(r, 5, QTableWidgetItem(f"{m['unit_cost']:.2f}"))

            actions = QWidget(); h = QHBoxLayout(actions); h.setContentsMargins(0,0,0,0); h.setSpacing(4)
            adj = QPushButton("Post SAV"); adj.clicked.connect(lambda _, mid=m["id"]: self._adjust(mid))
            settings = QPushButton("⚙"); settings.setMaximumWidth(34)
            settings.clicked.connect(lambda _, mid=m["id"]: self._settings(mid))
            h.addWidget(adj); h.addWidget(settings)
            self.raw_table.setCellWidget(r, 6, actions)

        # 2. Refresh Raw Stock History (Paginated)
        self.hist_table.refresh()
        if hasattr(self, "search"):
            self.search.reapply()

        # 3. Refresh Finished Goods Yard Transfers (Paginated)
        self._transfer_product_changed()
        self.transfer_log.refresh()
        if hasattr(self, "search_fgtv"):
            self.search_fgtv.reapply()

    def _fill_hist_table(self, table, data):
        for r, h in enumerate(data):
            table.setItem(r, 0, QTableWidgetItem(h["created_at"]))
            table.setItem(r, 1, QTableWidgetItem(h["material_name"]))
            item = QTableWidgetItem(f"{h['qty']:+.3f}")
            item.setForeground(Qt.darkGreen if h["qty"] > 0 else Qt.red)
            table.setItem(r, 2, item)
            table.setItem(r, 3, QTableWidgetItem(h["unit"]))
            table.setItem(r, 4, QTableWidgetItem(h["movement"]))
            table.setItem(r, 5, QTableWidgetItem(h.get("user_name") or ""))
            
            ref_and_note = f"[{h.get('reference') or ''}] {h.get('note') or ''}"
            table.setItem(r, 6, QTableWidgetItem(ref_and_note))

    def _fill_fgtv_table(self, table, data):
        for r, row in enumerate(data):
            table.setItem(r, 0, QTableWidgetItem(row.get("voucher_no") or ""))
            table.setItem(r, 1, QTableWidgetItem(row["created_at_str"]))
            table.setItem(r, 2, QTableWidgetItem(f"{row['product_code']} — {row['product_name']}"))
            table.setItem(r, 3, QTableWidgetItem(f"{row['quantity']:.2f}"))
            table.setItem(r, 4, QTableWidgetItem(row["unit"]))
            table.setItem(r, 5, QTableWidgetItem(row.get("user_name") or ""))
            table.setItem(r, 6, QTableWidgetItem(row.get("note") or ""))

    def _post_srv(self):
        if not auth_service.has_permission(self.user["id"], "inventory:add-stock"):
            from app.ui.widgets.override_dialog import request_override
            if not request_override("inventory:add-stock", self):
                return

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
        if not auth_service.has_permission(self.user["id"], "inventory:add-stock"):
            from app.ui.widgets.override_dialog import request_override
            if not request_override("inventory:add-stock", self):
                return

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
        if not auth_service.has_permission(self.user["id"], "inventory:adjust"):
            from app.ui.widgets.override_dialog import request_override
            if not request_override("inventory:adjust", self):
                return

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
        if not auth_service.has_permission(self.user["id"], "system:update-price"):
            from app.ui.widgets.override_dialog import request_override
            if not request_override("system:update-price", self):
                return

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

    def _reload_transfer_products(self):
        cat = self.trans_category.currentText()
        prods = product_service.list_products(category=cat)
        self.trans_product.clear()
        for p in prods:
            self.trans_product.addItem(f"{p['code']} — {p['name']}", p["id"])
        self._transfer_product_changed()

    def _transfer_product_changed(self):
        pid = self.trans_product.currentData()
        if pid is None:
            self.curing_stock_lbl.setText("0.00")
            return
            
        session = inventory_service.get_session()
        try:
            curing_qty = inventory_service.ledger_service.get_current_stock(session, pid, "WAREHOUSE")
            prod = product_service.get_product(pid)
            unit = "pcs" if prod["input_unit"] == "piece" else "m²"
            self.curing_stock_lbl.setText(f"{curing_qty:.2f} {unit}")
        finally:
            session.close()

    def _post_fgtv(self):
        if not auth_service.has_permission(self.user["id"], "inventory:add-stock"):
            from app.ui.widgets.override_dialog import request_override
            if not request_override("inventory:add-stock", self):
                return

        pid = self.trans_product.currentData()
        qty = self.trans_qty.value()
        if pid is None or qty <= 0:
            QMessageBox.warning(self, "Invalid Transfer", "Select a product and enter a positive transfer quantity.")
            return
            
        try:
            product_service.record_fgtv(
                product_id=pid,
                quantity=qty,
                user_id=self.user["id"],
                note=self.trans_note.text().strip() or None
            )
            QMessageBox.information(self, "Posted", "Finished Goods Transfer Voucher (FGTV) posted successfully.")
            self.trans_qty.setValue(0.0)
            self.trans_note.clear()
            self.refresh()
        except ValueError as e:
            QMessageBox.warning(self, "Transfer Failed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
