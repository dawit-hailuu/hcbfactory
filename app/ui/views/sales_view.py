"""Sales view: record sale + history table."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QDoubleSpinBox, QLineEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox, QFormLayout, QMessageBox, QTabWidget)

from app.services import product_service, sales_service


class SalesView(QWidget):
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

        t = QLabel("Sales")
        t.setObjectName("pagetitle")
        outer.addWidget(t)

        self.tabs = QTabWidget()

        # New sale
        new = QWidget(); v = QVBoxLayout(new)

        gb = QGroupBox("Record Sale")
        form = QFormLayout(gb)

        self.category = QComboBox(); self.category.addItems(["HCB","TERAZO","PIPE"])
        self.category.currentTextChanged.connect(self._reload_products)
        form.addRow("Category:", self.category)

        self.product = QComboBox()
        self.product.currentIndexChanged.connect(self._product_changed)
        form.addRow("Product:", self.product)

        self.stock_lbl = QLabel("—"); self.stock_lbl.setObjectName("hintmedium")
        form.addRow("In stock:", self.stock_lbl)

        self.customer = QLineEdit(); self.customer.setPlaceholderText("Customer name")
        form.addRow("Customer:", self.customer)

        self.qty = QDoubleSpinBox(); self.qty.setRange(0, 1_000_000); self.qty.setDecimals(2)
        self.qty.valueChanged.connect(self._recalc_total)
        self.qty_unit = QLabel("pieces")
        qr = QHBoxLayout(); qr.addWidget(self.qty); qr.addWidget(self.qty_unit); qr.addStretch()
        form.addRow("Quantity:", qr)

        self.price = QDoubleSpinBox(); self.price.setRange(0, 1_000_000); self.price.setDecimals(2)
        self.price.valueChanged.connect(self._recalc_total)
        form.addRow("Unit price (ETB):", self.price)

        self.total_lbl = QLabel("0.00 ETB")
        self.total_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #27AE60;")
        form.addRow("Total:", self.total_lbl)

        self.paid = QDoubleSpinBox(); self.paid.setRange(0, 1_000_000_000); self.paid.setDecimals(2)
        form.addRow("Amount paid now (0 = full cash):", self.paid)

        self.note = QLineEdit(); self.note.setPlaceholderText("Optional note")
        form.addRow("Note:", self.note)

        v.addWidget(gb)
        btn_row = QHBoxLayout(); btn_row.addStretch()
        btn = QPushButton("✓ Record Sale"); btn.setObjectName("success"); btn.clicked.connect(self._confirm)
        btn_row.addWidget(btn)
        v.addLayout(btn_row)

        self.tabs.addTab(new, "New Sale")

        # History
        ht = QWidget(); vh = QVBoxLayout(ht)
        # Search bar above history table
        from app.ui.widgets.search_box import SearchBox
        self.search = SearchBox(None, placeholder="Search sales by product, customer, date, note, total…")
        vh.addWidget(self.search)

        self.history = QTableWidget(0, 11)
        self.history.setHorizontalHeaderLabels(
            ["Date","Product","Customer","Qty","Unit Price","Total","Paid","Balance","User","Note","Actions"])
        self.history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeToContents)
        self.history.verticalHeader().setVisible(False)
        self.history.setAlternatingRowColors(True)
        self.history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search.attach(self.history)
        vh.addWidget(self.history)
        self.tabs.addTab(ht, "Sales History")

        outer.addWidget(self.tabs)
        self._reload_products()

    def _reload_products(self):
        cat = self.category.currentText()
        prods = product_service.list_products(category=cat)
        self.product.clear()
        for p in prods:
            self.product.addItem(f"{p['code']} — {p['name']}", p["id"])
        self._product_changed()

    def _product_changed(self):
        pid = self.product.currentData()
        if pid is None:
            self.stock_lbl.setText("—"); self.qty_unit.setText(""); self.price.setValue(0); return
        p = product_service.get_product(pid)
        unit = "pieces" if p["input_unit"] == "piece" else "m²"
        self.qty_unit.setText(unit)
        self.stock_lbl.setText(f"{p['stock']:.2f} {unit}")
        if p["sell_price"] > 0:
            self.price.setValue(p["sell_price"])
        self._recalc_total()

    def _recalc_total(self):
        self.total_lbl.setText(f"{self.qty.value() * self.price.value():,.2f} ETB")

    def _confirm(self):
        pid = self.product.currentData()
        if pid is None or self.qty.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Pick a product and quantity > 0."); return
        # Empty customer name is fine (anonymous cash sale) — no warning needed.
        try:
            paid = self.paid.value() if self.paid.value() > 0 else None
            sale_id = sales_service.record_sale(
                product_id=pid,
                customer_name=self.customer.text().strip() or None,
                quantity=self.qty.value(),
                unit_price=self.price.value(),
                user_id=self.user["id"],
                note=self.note.text() or None,
                amount_paid=paid,
            )
            sale = sales_service.get_sale(sale_id)
            vno = (sale or {}).get("voucher_no") or "-"
            if QMessageBox.question(
                self, "Sale recorded",
                f"Sale recorded as {vno}.\nPrint receipt now?"
            ) == QMessageBox.Yes:
                self._print_receipt(sale_id)
            self.qty.setValue(0); self.customer.clear(); self.note.clear()
            self.paid.setValue(0)
            self.refresh()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot proceed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _print_receipt(self, sale_id):
        from app.services import sales_service, voucher_pdf_service
        from app.utils.paths import RECEIPTS
        from PyQt5.QtWidgets import QFileDialog
        sale = sales_service.get_sale(sale_id)
        if not sale or not sale.get("voucher_no"):
            QMessageBox.warning(self, "No voucher", "This sale has no voucher number.")
            return
        vno = sale["voucher_no"]
        RECEIPTS.mkdir(parents=True, exist_ok=True)
        out = RECEIPTS / f"{vno}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save receipt", str(out), "PDF Files (*.pdf)")
        if not path:
            return
        try:
            voucher_pdf_service.export_voucher(vno, path)
            QMessageBox.information(self, "Receipt saved", f"Saved to:\n{path}")
        except PermissionError:
            QMessageBox.critical(self, "Cannot save",
                f"Cannot write to:\n{path}\n\n"
                "The file may be open in another program. Close it and try again.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._product_changed()
        rows = sales_service.list_sales(limit=500)
        self.history.setRowCount(len(rows))
        for r, s in enumerate(rows):
            self.history.setItem(r, 0, QTableWidgetItem(s["sale_date"]))
            self.history.setItem(r, 1, QTableWidgetItem(f"{s['product_code']} — {s['product_name']}"))
            self.history.setItem(r, 2, QTableWidgetItem(s.get("customer_name") or ""))
            self.history.setItem(r, 3, QTableWidgetItem(f"{s['quantity']:.2f}"))
            self.history.setItem(r, 4, QTableWidgetItem(f"{s['unit_price']:,.2f}"))
            self.history.setItem(r, 5, QTableWidgetItem(f"{s['total']:,.2f}"))
            paid = s.get("amount_paid") or 0
            self.history.setItem(r, 6, QTableWidgetItem(f"{paid:,.2f}"))
            bal = (s.get("balance") or 0)
            bal_item = QTableWidgetItem(f"{bal:,.2f}")
            if bal > 0:
                bal_item.setForeground(Qt.red)
            self.history.setItem(r, 7, bal_item)
            self.history.setItem(r, 8, QTableWidgetItem(s.get("user_name") or ""))
            self.history.setItem(r, 9, QTableWidgetItem(s.get("note") or ""))

            actions = QWidget(); ah = QHBoxLayout(actions); ah.setContentsMargins(0,0,0,0); ah.setSpacing(4)
            rb = QPushButton("🖨"); rb.setMaximumWidth(34); rb.setToolTip("Receipt")
            rb.clicked.connect(lambda _, sid=s["id"]: self._print_receipt(sid))
            ah.addWidget(rb)
            if self.user["role"] == "admin":
                eb = QPushButton("✎"); eb.setMaximumWidth(34); eb.setToolTip("Edit")
                eb.clicked.connect(lambda _, sid=s["id"]: self._edit_sale(sid))
                db = QPushButton("🗑"); db.setObjectName("danger"); db.setMaximumWidth(34); db.setToolTip("Delete")
                db.clicked.connect(lambda _, sid=s["id"]: self._delete_sale(sid))
                ah.addWidget(eb); ah.addWidget(db)
            self.history.setCellWidget(r, 10, actions)
        if hasattr(self, "search"):
            self.search.reapply()

    def _edit_sale(self, sale_id):
        from app.ui.views.dialogs.edit_sale_dialog import EditSaleDialog
        try:
            dlg = EditSaleDialog(sale_id, self.user, self)
        except ValueError as e:
            QMessageBox.warning(self, "Not available", str(e)); return
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return
        if dlg.exec_() == dlg.Accepted:
            self.refresh()

    def _delete_sale(self, sale_id):
        from PyQt5.QtWidgets import QInputDialog
        reason, ok = QInputDialog.getText(self, "Delete sale", "Reason (required):")
        if not ok or not reason.strip():
            return
        try:
            sales_service.delete_sale(sale_id, user_id=self.user["id"], reason=reason.strip())
            QMessageBox.information(self, "Deleted", "Sale deleted; stock restored.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
