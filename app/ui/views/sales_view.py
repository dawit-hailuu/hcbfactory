"""
Sales view: handles Cash Sale Vouchers (CSV), Credit Sale Vouchers (CrSV), 
and Cash Receipt Vouchers (CRV) for customer collections.
Uses PaginatedTableWidget to prevent UI freeze on large logs.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QDoubleSpinBox, QLineEdit, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QGroupBox, QFormLayout, QMessageBox, QTabWidget)

from app.services import product_service, sales_service
from app.ui.widgets.paginated_table import PaginatedTableWidget


class SalesView(QWidget):
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

        t = QLabel("Sales Vouchers")
        t.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        outer.addWidget(t)

        self.tabs = QTabWidget()

        # --- Tab 1: New Sale (CSV / CrSV) ---
        new_sale_tab = QWidget(); v = QVBoxLayout(new_sale_tab)

        gb = QGroupBox("Record Sale Voucher")
        form = QFormLayout(gb)

        self.category = QComboBox()
        self.category.addItems(["HCB", "TERAZO", "PIPE"])
        self.category.currentTextChanged.connect(self._reload_products)
        form.addRow("Category:", self.category)

        self.product = QComboBox()
        self.product.currentIndexChanged.connect(self._product_changed)
        form.addRow("Product:", self.product)

        self.stock_lbl = QLabel("—")
        self.stock_lbl.setStyleSheet("color: #6B7B8C;")
        form.addRow("Available Stock:", self.stock_lbl)

        self.payment_type = QComboBox()
        self.payment_type.addItems(["Cash (CSV)", "Credit (CrSV)"])
        form.addRow("Payment Term:", self.payment_type)

        self.customer = QLineEdit()
        self.customer.setPlaceholderText("Customer Name")
        form.addRow("Customer Name:", self.customer)

        self.qty = QDoubleSpinBox()
        self.qty.setRange(0, 1_000_000); self.qty.setDecimals(2)
        self.qty.valueChanged.connect(self._recalc_total)
        self.qty_unit = QLabel("pieces")
        qr = QHBoxLayout(); qr.addWidget(self.qty); qr.addWidget(self.qty_unit); qr.addStretch()
        form.addRow("Quantity sold:", qr)

        self.price = QDoubleSpinBox()
        self.price.setRange(0, 1_000_000); self.price.setDecimals(2)
        self.price.valueChanged.connect(self._recalc_total)
        form.addRow("Unit price (ETB):", self.price)

        self.total_lbl = QLabel("0.00 ETB")
        self.total_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #27AE60;")
        form.addRow("Valuation Total:", self.total_lbl)

        self.note = QLineEdit(); self.note.setPlaceholderText("Optional memo note")
        form.addRow("Note:", self.note)

        v.addWidget(gb)
        
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = QPushButton("✓ Post Sale Voucher")
        btn.setObjectName("success")
        btn.clicked.connect(self._confirm_sale)
        btn_row.addWidget(btn)
        v.addLayout(btn_row)

        self.tabs.addTab(new_sale_tab, "New Sale Voucher")

        # --- Tab 2: Cash Receipts (CRV) Debt Collection ---
        crv_tab = QWidget(); v_crv = QVBoxLayout(crv_tab)
        
        gb_crv = QGroupBox("Record Cash Receipt Voucher (CRV)")
        form_crv = QFormLayout(gb_crv)
        
        self.crv_customer = QLineEdit()
        self.crv_customer.setPlaceholderText("Customer name (depositing payment)")
        form_crv.addRow("Customer Name:", self.crv_customer)
        
        self.crv_amount = QDoubleSpinBox()
        self.crv_amount.setRange(0, 50_000_000)
        self.crv_amount.setDecimals(2)
        form_crv.addRow("Amount Collected (ETB):", self.crv_amount)
        
        self.crv_note = QLineEdit()
        self.crv_note.setPlaceholderText("Check number, Bank transfer receipt reference")
        form_crv.addRow("Collection Reference / Note:", self.crv_note)
        
        v_crv.addWidget(gb_crv)
        
        btn_row_crv = QHBoxLayout()
        btn_row_crv.addStretch()
        btn_crv = QPushButton("✓ Post CRV Receipt")
        btn_crv.setObjectName("success")
        btn_crv.clicked.connect(self._confirm_crv)
        btn_row_crv.addWidget(btn_crv)
        v_crv.addLayout(btn_row_crv)
        
        self.tabs.addTab(crv_tab, "Cash Receipt (CRV)")

        # --- Tab 3: Sales History ---
        sales_hist_tab = QWidget(); vh = QVBoxLayout(sales_hist_tab)
        from app.ui.widgets.search_box import SearchBox
        self.search = SearchBox(None, placeholder="Search sales by product, customer, date, note…")
        vh.addWidget(self.search)

        self.history = PaginatedTableWidget(
            ["Voucher No", "Date", "Product", "Customer", "Qty", "Unit Price", "Total", "User", "Note"],
            lambda limit, offset: sales_service.list_sales(limit=limit, offset=offset),
            self._fill_sales_table
        )
        self.search.attach(self.history.table)
        vh.addWidget(self.history)
        self.tabs.addTab(sales_hist_tab, "Sales Voucher History")

        # --- Tab 4: CRV Collection History ---
        crv_hist_tab = QWidget(); vh_crv = QVBoxLayout(crv_hist_tab)
        self.search_crv = SearchBox(None, placeholder="Search cash receipts by customer, voucher, note…")
        vh_crv.addWidget(self.search_crv)

        self.crv_history = PaginatedTableWidget(
            ["Voucher No", "Date/Time", "Customer", "Amount Collected", "Recorded By", "Reference/Note"],
            lambda limit, offset: sales_service.list_cash_receipts(limit=limit, offset=offset),
            self._fill_crv_table
        )
        self.search_crv.attach(self.crv_history.table)
        vh_crv.addWidget(self.crv_history)
        self.tabs.addTab(crv_hist_tab, "Cash Receipt History")

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

    def _confirm_sale(self):
        pid = self.product.currentData()
        if pid is None or self.qty.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Pick a product and quantity > 0.")
            return
        if not self.customer.text().strip():
            if QMessageBox.question(self, "No customer name",
                "Customer name is empty. Continue?") != QMessageBox.Yes:
                return
                
        payment_term = "CASH" if "Cash" in self.payment_type.currentText() else "CREDIT"
        try:
            sales_service.record_sale(
                product_id=pid,
                customer_name=self.customer.text().strip() or None,
                quantity=self.qty.value(),
                unit_price=self.price.value(),
                user_id=self.user["id"],
                note=self.note.text() or None,
                payment_type=payment_term
            )
            QMessageBox.information(self, "Posted", "Sales Voucher posted successfully.")
            self.qty.setValue(0); self.customer.clear(); self.note.clear()
            self.refresh()
        except ValueError as e:
            QMessageBox.warning(self, "Cannot proceed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _confirm_crv(self):
        customer = self.crv_customer.text().strip()
        amount = self.crv_amount.value()
        if not customer:
            QMessageBox.warning(self, "Missing Customer", "Customer name is required.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Collection amount must be positive.")
            return
            
        try:
            sales_service.record_cash_receipt(
                customer_name=customer,
                amount=amount,
                user_id=self.user["id"],
                note=self.crv_note.text().strip() or None
            )
            QMessageBox.information(self, "Posted", "Cash Receipt Voucher (CRV) posted successfully.")
            self.crv_customer.clear()
            self.crv_amount.setValue(0.0)
            self.crv_note.clear()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        self._product_changed()
        self.history.refresh()
        if hasattr(self, "search"):
            self.search.reapply()
        self.crv_history.refresh()
        if hasattr(self, "search_crv"):
            self.search_crv.reapply()

    def _fill_sales_table(self, table, data):
        for r, s in enumerate(data):
            table.setItem(r, 0, QTableWidgetItem(s.get("voucher_no") or ""))
            table.setItem(r, 1, QTableWidgetItem(s["sale_date"]))
            table.setItem(r, 2, QTableWidgetItem(f"{s['product_code']} — {s['product_name']}"))
            table.setItem(r, 3, QTableWidgetItem(s.get("customer_name") or ""))
            table.setItem(r, 4, QTableWidgetItem(f"{s['quantity']:.2f}"))
            table.setItem(r, 5, QTableWidgetItem(f"{s['unit_price']:,.2f}"))
            table.setItem(r, 6, QTableWidgetItem(f"{s['total']:,.2f}"))
            table.setItem(r, 7, QTableWidgetItem(s.get("user_name") or ""))
            table.setItem(r, 8, QTableWidgetItem(s.get("note") or ""))

    def _fill_crv_table(self, table, data):
        for r, c in enumerate(data):
            table.setItem(r, 0, QTableWidgetItem(c.get("voucher_no") or ""))
            table.setItem(r, 1, QTableWidgetItem(c["created_at"]))
            table.setItem(r, 2, QTableWidgetItem(c["customer_name"]))
            table.setItem(r, 3, QTableWidgetItem(f"{c['amount']:,.2f}"))
            table.setItem(r, 4, QTableWidgetItem(c.get("user_name") or ""))
            table.setItem(r, 5, QTableWidgetItem(c.get("note") or ""))
