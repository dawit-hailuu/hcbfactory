"""
Production view: select product, enter quantity, see live consumption preview,
confirm production run.  History tab shows past runs and the materials each used.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QDoubleSpinBox, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QFormLayout, QLineEdit,
                             QMessageBox, QTabWidget, QCompleter)

from app.services import product_service, production_service


class ProductionView(QWidget):
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
        t = QLabel("Production")
        t.setObjectName("pagetitle")
        head.addWidget(t); head.addStretch()
        waste_btn = QPushButton("🗑 Record Waste / Damaged")
        waste_btn.setObjectName("danger")
        waste_btn.clicked.connect(self._record_waste)
        head.addWidget(waste_btn)
        outer.addLayout(head)

        self.tabs = QTabWidget()

        # --- New production tab -----------------------------------------------
        new_tab = QWidget(); v = QVBoxLayout(new_tab)

        gb = QGroupBox("Record Production")
        form = QFormLayout(gb)

        self.category = QComboBox()
        self.category.addItems(["HCB", "TERAZO", "PIPE"])
        self.category.currentTextChanged.connect(self._reload_products)
        form.addRow("Category:", self.category)

        self.product = QComboBox()
        self.product.currentIndexChanged.connect(self._product_changed)
        form.addRow("Product:", self.product)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 1_000_000); self.qty.setDecimals(2); self.qty.setValue(0)
        self.qty.valueChanged.connect(self._update_preview)
        self.qty_unit_lbl = QLabel("pieces")
        qty_row = QHBoxLayout(); qty_row.addWidget(self.qty); qty_row.addWidget(self.qty_unit_lbl); qty_row.addStretch()
        form.addRow("Quantity:", qty_row)

        # Made by — worker who physically made it (free-text, autocompletes from history)
        self.made_by = QLineEdit()
        self.made_by.setPlaceholderText("Worker name (e.g. Abebe)")
        self._refresh_made_by_completer()
        form.addRow("Made by:", self.made_by)

        self.note = QLineEdit(); self.note.setPlaceholderText("Optional note")
        form.addRow("Note:", self.note)

        v.addWidget(gb)

        # Preview table
        prev_label = QLabel("Material Consumption (Preview)")
        prev_label.setObjectName("subhead")
        v.addWidget(prev_label)

        self.preview = QTableWidget(0, 6)
        self.preview.setHorizontalHeaderLabels(
            ["Material", "Per Unit", "Needed", "Available", "Unit", "Status"])
        self.preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setAlternatingRowColors(True)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.setMaximumHeight(240)
        v.addWidget(self.preview)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.confirm_btn = QPushButton("✓ Confirm Production")
        self.confirm_btn.setObjectName("success")
        self.confirm_btn.clicked.connect(self._confirm)
        btn_row.addWidget(self.confirm_btn)
        v.addLayout(btn_row)

        self.tabs.addTab(new_tab, "New Production")

        # --- History tab ------------------------------------------------------
        hist_tab = QWidget(); vh = QVBoxLayout(hist_tab)
        from app.ui.widgets.search_box import SearchBox
        self.search = SearchBox(None, placeholder="Search production by product, made-by, date, note…")
        vh.addWidget(self.search)

        self.history = QTableWidget(0, 8)
        self.history.setHorizontalHeaderLabels(
            ["Date", "Product", "Quantity", "Unit", "Made By", "User", "Note", "Actions"])
        self.history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.history.verticalHeader().setVisible(False)
        self.history.setAlternatingRowColors(True)
        self.history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search.attach(self.history)
        vh.addWidget(self.history)
        self.tabs.addTab(hist_tab, "History")

        outer.addWidget(self.tabs)
        self._reload_products()

    def _refresh_made_by_completer(self):
        """Rebuild the autocomplete word list from recent production entries."""
        names = production_service.recent_made_by(limit=10)
        completer = QCompleter(names, self.made_by)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.made_by.setCompleter(completer)

    def _reload_products(self):
        cat = self.category.currentText()
        products = product_service.list_products(category=cat)
        self.product.clear()
        for p in products:
            self.product.addItem(f"{p['code']} — {p['name']}", p["id"])
        self._product_changed()

    def _product_changed(self):
        pid = self.product.currentData()
        if pid is None:
            self.qty_unit_lbl.setText("")
            self.preview.setRowCount(0)
            return
        prod = product_service.get_product(pid)
        unit_text = "pieces" if prod["input_unit"] == "piece" else "m²"
        self.qty_unit_lbl.setText(unit_text)
        self._update_preview()

    def _update_preview(self):
        pid = self.product.currentData()
        q = self.qty.value()
        if pid is None or q <= 0:
            self.preview.setRowCount(0)
            self._update_confirm_state(False)
            return
        try:
            rows = production_service.calculate_consumption(pid, q)
        except Exception:
            self.preview.setRowCount(0)
            self._update_confirm_state(False)
            return

        all_ok = bool(rows)
        self.preview.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.preview.setItem(r, 0, QTableWidgetItem(row["material_name"]))
            self.preview.setItem(r, 1, QTableWidgetItem(f"{row['qty_per_unit']:.5f}"))
            need_item = QTableWidgetItem(f"{row['qty_needed']:.3f}")
            self.preview.setItem(r, 2, need_item)
            self.preview.setItem(r, 3, QTableWidgetItem(f"{row['available']:.3f}"))
            self.preview.setItem(r, 4, QTableWidgetItem(row["unit"]))
            status = QTableWidgetItem("✓ OK" if row["sufficient"] else "✗ SHORT")
            status.setForeground(Qt.darkGreen if row["sufficient"] else Qt.red)
            self.preview.setItem(r, 5, status)
            if not row["sufficient"]:
                all_ok = False
        self._update_confirm_state(all_ok)

    def _update_confirm_state(self, can_confirm: bool):
        if not hasattr(self, "confirm_btn"): return
        self.confirm_btn.setEnabled(can_confirm)
        if can_confirm:
            self.confirm_btn.setToolTip("")
        else:
            self.confirm_btn.setToolTip(
                "Cannot confirm: pick a product, set quantity > 0, "
                "and ensure all materials show ✓ OK."
            )

    def _confirm(self):
        pid = self.product.currentData()
        q = self.qty.value()
        if pid is None or q <= 0:
            QMessageBox.warning(self, "Invalid", "Pick a product and quantity > 0.")
            return
        made_by_val = self.made_by.text().strip() or None
        try:
            new_id = production_service.record_production(
                product_id=pid, quantity=q,
                user_id=self.user["id"], note=self.note.text() or None,
                made_by=made_by_val,
                allow_negative_stock=False,
            )
            # Look up voucher number for confirmation
            rec = production_service.get_production(new_id)
            vno = (rec or {}).get("voucher_no") or "-"
            QMessageBox.information(
                self, "Done",
                f"Production recorded as {vno}.\nMaterials deducted and stock updated."
            )
            self.qty.setValue(0); self.note.clear(); self.made_by.clear()
            self._refresh_made_by_completer()
            self.refresh()
        except ValueError as e:
            # Insufficient materials etc.
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Cannot proceed")
            box.setText(str(e))
            box.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._update_preview()
        rows = production_service.list_production(limit=500)
        self.history.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.history.setItem(r, 0, QTableWidgetItem(row["production_date"]))
            self.history.setItem(r, 1, QTableWidgetItem(f"{row['product_code']} — {row['product_name']}"))
            self.history.setItem(r, 2, QTableWidgetItem(f"{row['quantity']:.2f}"))
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            self.history.setItem(r, 3, QTableWidgetItem(unit))
            self.history.setItem(r, 4, QTableWidgetItem(row.get("made_by") or ""))
            self.history.setItem(r, 5, QTableWidgetItem(row.get("user_name") or ""))
            self.history.setItem(r, 6, QTableWidgetItem(row.get("note") or ""))
            # Actions column (admin only) — edit and delete
            actions = QWidget(); ah = QHBoxLayout(actions); ah.setContentsMargins(0,0,0,0); ah.setSpacing(4)
            if self.user["role"] == "admin":
                eb = QPushButton("✎"); eb.setMaximumWidth(34); eb.setToolTip("Edit this production run")
                eb.clicked.connect(lambda _, rid=row["id"]: self._edit_production(rid))
                db = QPushButton("🗑"); db.setObjectName("danger"); db.setMaximumWidth(34)
                db.setToolTip("Delete (reverses materials and stock)")
                db.clicked.connect(lambda _, rid=row["id"]: self._delete_production(rid))
                ah.addWidget(eb); ah.addWidget(db)
            else:
                ah.addStretch()  # blank for non-admins, no ugly "(admin)" text
            self.history.setCellWidget(r, 7, actions)
        if hasattr(self, "search"):
            self.search.reapply()

    def _record_waste(self):
        """Open waste dialog."""
        from app.ui.views.dialogs.waste_dialog import WasteDialog
        try:
            dlg = WasteDialog(self.user, self)
        except Exception as e:
            QMessageBox.critical(self, "Cannot open", str(e)); return
        if dlg.exec_() == dlg.Accepted:
            self.refresh()

    def _edit_production(self, prod_id):
        from app.ui.views.dialogs.edit_production_dialog import EditProductionDialog
        try:
            dlg = EditProductionDialog(prod_id, self.user, self)
        except ValueError as e:
            QMessageBox.warning(self, "Not available", str(e)); return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return
        if dlg.exec_() == dlg.Accepted:
            self.refresh()

    def _delete_production(self, prod_id):
        from PyQt5.QtWidgets import QInputDialog
        reason, ok = QInputDialog.getText(
            self, "Delete production run",
            "Reason for deletion (required):"
        )
        if not ok or not reason.strip():
            return
        from app.services import production_service
        try:
            production_service.delete_production(prod_id, user_id=self.user["id"],
                                                  reason=reason.strip())
            QMessageBox.information(self, "Deleted",
                "Production run deleted. Materials returned to stock; finished stock reduced.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
