"""
Voucher Document Browser View:
Allows browsing, filtering, and transaction-level auditing of all vouchers,
inspecting physical stock movements (Inventory Ledger) and general ledger balances (Journal Entries),
and performing secure supervisor-authorized void cancellations.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QTabWidget, QSplitter, QMessageBox, QFrame)
from app.services import ledger_service, auth_service
from app.ui.widgets.paginated_table import PaginatedTableWidget
from app.ui.widgets.search_box import SearchBox


class VoucherBrowserView(QWidget):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.selected_voucher_id = None
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Main splitter (Top: Search/Filters/Grid, Bottom: Details Split)
        splitter = QSplitter(Qt.Vertical)
        
        # --- Top Widget (Voucher List) ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        # Filters Row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "SRV", "SIV", "SAV", "PRODUCTION", "FGTV", "CASH_SALE", "CREDIT_SALE", "CRV"])
        self.type_filter.currentTextChanged.connect(self.refresh)
        filter_row.addWidget(self.type_filter)

        filter_row.addWidget(QLabel("State:"))
        self.state_filter = QComboBox()
        self.state_filter.addItems(["All", "POSTED", "VOIDED"])
        self.state_filter.currentTextChanged.connect(self.refresh)
        filter_row.addWidget(self.state_filter)

        filter_row.addStretch()
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh)
        filter_row.addWidget(btn_refresh)
        top_layout.addLayout(filter_row)

        # Search Bar
        self.search = SearchBox(None, placeholder="Search vouchers by number, note, customer, username...")
        top_layout.addWidget(self.search)

        # Paginated Table
        self.voucher_table = PaginatedTableWidget(
            ["Voucher No", "Date", "Type", "Created By", "Customer / Operator", "State"],
            lambda limit, offset: ledger_service.list_vouchers_paginated(
                limit=limit,
                offset=offset,
                type_filter=self.type_filter.currentText(),
                state_filter=self.state_filter.currentText(),
                query=self.search.text()
            ),
            self._fill_vouchers_table
        )
        self.search.attach(self.voucher_table.table)
        self.voucher_table.table.itemSelectionChanged.connect(self._row_selected)
        top_layout.addWidget(self.voucher_table)
        
        splitter.addWidget(top_widget)

        # --- Bottom Widget (Detailed Ledger Split) ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 10, 0, 0)
        bottom_layout.setSpacing(8)

        detail_header = QHBoxLayout()
        detail_title = QLabel("Transaction Details & Balances")
        detail_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #1F4E79;")
        detail_header.addWidget(detail_title)
        detail_header.addStretch()
        
        # Red Void Transaction Button
        self.btn_void = QPushButton("🛇 Void Transaction")
        self.btn_void.setObjectName("danger")
        self.btn_void.setEnabled(False)
        self.btn_void.clicked.connect(self._void_selected_voucher)
        detail_header.addWidget(self.btn_void)
        bottom_layout.addLayout(detail_header)

        # Tabs for details
        self.tabs = QTabWidget()
        
        # Tab 1: Physical Inventory Ledger
        self.tab_inv = QWidget()
        self.inv_layout = QVBoxLayout(self.tab_inv)
        self.inv_table = QTableWidget(0, 6)
        self.inv_table.setHorizontalHeaderLabels(["Article Code", "Article Name", "Qty Change", "Unit", "Location", "Cost Rate"])
        self.inv_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inv_layout.addWidget(self.inv_table)
        self.tabs.addTab(self.tab_inv, "📦 Physical Stock movements")

        # Tab 2: Journal Entries (Accounting)
        self.tab_acc = QWidget()
        self.acc_layout = QVBoxLayout(self.tab_acc)
        self.acc_table = QTableWidget(0, 3)
        self.acc_table.setHorizontalHeaderLabels(["Account Code", "Debit (ETB)", "Credit (ETB)"])
        self.acc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.acc_table.verticalHeader().setVisible(False)
        self.acc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.acc_layout.addWidget(self.acc_table)
        
        # Reconciled matching totals
        self.balance_lbl = QLabel("")
        self.balance_lbl.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        self.acc_layout.addWidget(self.balance_lbl)
        self.tabs.addTab(self.tab_acc, "💵 General Ledger Posting")

        bottom_layout.addWidget(self.tabs)
        splitter.addWidget(bottom_widget)

        # Set default proportions: top gets 55%, bottom gets 45%
        splitter.setSizes([450, 350])
        layout.addWidget(splitter)

    def refresh(self):
        self.voucher_table.refresh()
        self.selected_voucher_id = None
        self.btn_void.setEnabled(False)
        self._clear_detail_panels()

    def _fill_vouchers_table(self, table, data):
        for r, row in enumerate(data):
            table.setItem(r, 0, QTableWidgetItem(row["voucher_no"]))
            table.setItem(r, 1, QTableWidgetItem(row["created_at_str"]))
            table.setItem(r, 2, QTableWidgetItem(row["voucher_type"]))
            table.setItem(r, 3, QTableWidgetItem(row.get("created_by_name") or "System"))
            
            operator = row.get("customer_name") or row.get("made_by") or ""
            table.setItem(r, 4, QTableWidgetItem(operator))
            
            state_item = QTableWidgetItem(row["state"])
            if row["state"] == "VOIDED":
                state_item.setForeground(Qt.red)
            else:
                state_item.setForeground(Qt.darkGreen)
            table.setItem(r, 5, state_item)

    def _row_selected(self):
        rows = self.voucher_table.table.selectionModel().selectedRows()
        if not rows:
            return
        r = rows[0].row()
        data = self.voucher_table.table.item(r, 0).data(Qt.UserRole)
        # Wait, how does our PaginatedTableWidget set UserRole? It doesn't by default.
        # Let's override it or get row dict from the paginated rows list!
        # But since PaginatedTableWidget doesn't store data in items by default, 
        # let's look up using the voucher number which is in column 0!
        v_no = self.voucher_table.table.item(r, 0).text()
        state = self.voucher_table.table.item(r, 5).text()
        
        # Query db for this voucher row
        from app.database.db import get_session
        from app.database.models import Voucher
        session = get_session()
        try:
            v = session.query(Voucher).filter_by(voucher_no=v_no).first()
            if v:
                self.selected_voucher_id = v.id
                self.btn_void.setEnabled(v.state == "POSTED")
                self._load_voucher_details(v.id)
        finally:
            session.close()

    def _clear_detail_panels(self):
        self.inv_table.setRowCount(0)
        self.acc_table.setRowCount(0)
        self.balance_lbl.setText("")

    def _load_voucher_details(self, voucher_id):
        details = ledger_service.get_voucher_details(voucher_id)
        
        # Populate Inventory movements
        inv = details["inventory"]
        self.inv_table.setRowCount(len(inv))
        for r, row in enumerate(inv):
            self.inv_table.setItem(r, 0, QTableWidgetItem(row["article_code"]))
            self.inv_table.setItem(r, 1, QTableWidgetItem(row["article_name"]))
            
            # Signed formatting
            qc = row["qty_change"]
            qc_item = QTableWidgetItem(f"{qc:+.3f}")
            if qc < 0:
                qc_item.setForeground(Qt.red)
            else:
                qc_item.setForeground(Qt.darkGreen)
            self.inv_table.setItem(r, 2, qc_item)
            
            self.inv_table.setItem(r, 3, QTableWidgetItem(row["unit"]))
            self.inv_table.setItem(r, 4, QTableWidgetItem(row["location"]))
            self.inv_table.setItem(r, 5, QTableWidgetItem(f"{row['cost_rate']:.2f}"))

        # Populate Accounting split
        acc = details["journal"]
        self.acc_table.setRowCount(len(acc))
        total_debit = 0.0
        total_credit = 0.0
        for r, row in enumerate(acc):
            self.acc_table.setItem(r, 0, QTableWidgetItem(row["account_code"]))
            
            deb = row["debit"]
            total_debit += deb
            self.acc_table.setItem(r, 1, QTableWidgetItem(f"{deb:.2f}" if deb > 0 else ""))
            
            cred = row["credit"]
            total_credit += cred
            self.acc_table.setItem(r, 2, QTableWidgetItem(f"{cred:.2f}" if cred > 0 else ""))

        # Balanced reconcile status
        diff = abs(total_debit - total_credit)
        if diff < 0.01:
            self.balance_lbl.setText(f"✓ Postings balanced: Total Debits: {total_debit:.2f} ETB  |  Total Credits: {total_credit:.2f} ETB (Reconciled)")
            self.balance_lbl.setStyleSheet("color: #27AE60; font-weight: bold;")
        else:
            self.balance_lbl.setText(f"⚠ UNBALANCED DISCREPANCY: Total Debits: {total_debit:.2f} ETB  |  Total Credits: {total_credit:.2f} ETB (Discrepancy: {diff:.2f} ETB)")
            self.balance_lbl.setStyleSheet("color: #C0392B; font-weight: bold;")

    def _void_selected_voucher(self):
        if not self.selected_voucher_id:
            return
            
        # Verify permission to void (sale:void or admin status)
        if not auth_service.has_permission(self.user["id"], "sale:void"):
            from app.ui.widgets.override_dialog import request_override
            if not request_override("sale:void", self):
                return

        # Double check double-reversal confirmation dialog
        confirm = QMessageBox.question(
            self, 
            "Confirm Cancellation", 
            "Are you absolutely sure you want to VOID this transaction?\n"
            "This will post balanced double-reversal entries to inventory and financial ledgers.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            success = ledger_service.void_voucher(self.selected_voucher_id, self.user["id"])
            if success:
                QMessageBox.information(self, "Success", "Transaction has been successfully voided and compensated.")
                self.refresh()
            else:
                QMessageBox.warning(self, "Failed", "Could not void the selected voucher.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process reversal: {str(e)}")
