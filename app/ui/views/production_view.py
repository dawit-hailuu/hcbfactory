"""
Production view: select product, enter quantity, live consumption preview,
and post Production Vouchers. History tab displays registered vouchers in a paginated log.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QDoubleSpinBox, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QFormLayout, QLineEdit,
                             QMessageBox, QTabWidget, QCompleter)

from app.services import product_service, production_service
from app.ui.widgets.paginated_table import PaginatedTableWidget


class ProductionView(QWidget):
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

        t = QLabel("Production Vouchers")
        t.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        outer.addWidget(t)

        self.tabs = QTabWidget()

        # --- New production tab ---
        new_tab = QWidget(); v = QVBoxLayout(new_tab)

        gb = QGroupBox("Record Production Voucher")
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

        # Made by — worker who physically molded the items
        self.made_by = QLineEdit()
        self.made_by.setPlaceholderText("Worker name (e.g. Abebe)")
        self._refresh_made_by_completer()
        form.addRow("Made by (Operator):", self.made_by)

        self.note = QLineEdit(); self.note.setPlaceholderText("Optional batch notes")
        form.addRow("Note:", self.note)

        v.addWidget(gb)

        # Preview table
        prev_label = QLabel("Material Consumption (Preview)")
        prev_label.setStyleSheet("font-weight: bold; color: #1F4E79; margin-top: 6px;")
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
        self.confirm_btn = QPushButton("✓ Post Production Voucher")
        self.confirm_btn.setObjectName("success")
        self.confirm_btn.clicked.connect(self._confirm)
        btn_row.addWidget(self.confirm_btn)
        v.addLayout(btn_row)

        self.tabs.addTab(new_tab, "New Production Voucher")

        # --- History tab ---
        hist_tab = QWidget(); vh = QVBoxLayout(hist_tab)
        from app.ui.widgets.search_box import SearchBox
        self.search = SearchBox(None, placeholder="Search production by voucher, product, made-by, note…")
        vh.addWidget(self.search)

        self.history = PaginatedTableWidget(
            ["Voucher No", "Date", "Product", "Quantity", "Unit", "Made By", "User", "Note"],
            lambda limit, offset: production_service.list_production(limit=limit, offset=offset),
            self._fill_history_table
        )
        self.search.attach(self.history.table)
        vh.addWidget(self.history)
        self.tabs.addTab(hist_tab, "Voucher History")

        outer.addWidget(self.tabs)
        self._reload_products()

    def _refresh_made_by_completer(self):
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
            return
        try:
            rows = production_service.calculate_consumption(pid, q)
        except Exception:
            self.preview.setRowCount(0)
            return

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

    def _confirm(self):
        pid = self.product.currentData()
        q = self.qty.value()
        if pid is None or q <= 0:
            QMessageBox.warning(self, "Invalid", "Pick a product and quantity > 0.")
            return
        made_by_val = self.made_by.text().strip() or None
        try:
            production_service.record_production(
                product_id=pid, 
                quantity=q,
                user_id=self.user["id"], 
                note=self.note.text() or None,
                made_by=made_by_val,
                allow_negative_stock=False,
            )
            QMessageBox.information(self, "Done", "Production Voucher posted successfully.")
            self.qty.setValue(0); self.note.clear(); self.made_by.clear()
            self._refresh_made_by_completer()
            self.refresh()
        except ValueError as e:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Cannot proceed")
            box.setText(str(e))
            box.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._update_preview()
        self.history.refresh()
        if hasattr(self, "search"):
            self.search.reapply()

    def _fill_history_table(self, table, data):
        for r, row in enumerate(data):
            table.setItem(r, 0, QTableWidgetItem(row.get("voucher_no") or ""))
            table.setItem(r, 1, QTableWidgetItem(row["production_date"]))
            table.setItem(r, 2, QTableWidgetItem(f"{row['product_code']} — {row['product_name']}"))
            table.setItem(r, 3, QTableWidgetItem(f"{row['quantity']:.2f}"))
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            table.setItem(r, 4, QTableWidgetItem(unit))
            table.setItem(r, 5, QTableWidgetItem(row.get("made_by") or ""))
            table.setItem(r, 6, QTableWidgetItem(row.get("user_name") or ""))
            table.setItem(r, 7, QTableWidgetItem(row.get("note") or ""))
