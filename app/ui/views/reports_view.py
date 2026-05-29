"""
Reports view — per-category sub-tables, customer filter, global search,
finished-goods sub-tab, detailed columns, PDF export.

Layout:
  filter row: Period | From | To | Customer | Run | Export PDF
  search row
  status line
  tabs:
    [Production] → 3 sub-tables (HCB / Terazo / Pipes)
    [Material Usage] → 1 table (opening / used / purchased / remaining)
    [Sales]      → 3 sub-tables (HCB / Terazo / Pipes)
    [Finished Goods] → 3 sub-tables (HCB / Terazo / Pipes)
"""
from pathlib import Path
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
                             QDateEdit, QFileDialog, QMessageBox, QTabWidget)

from app.services import report_service
from app.ui.widgets.search_box import SearchBox


CATS = (("HCB", "HCB"), ("TERAZO", "Terazo"), ("PIPE", "Pipes (ቱቦ)"))


class ReportsView(QWidget):
    def __init__(self):
        super().__init__()
        self._suppress_period_signal = False
        self._build()
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self._reload_customers()
            self.refresh()
        except Exception:
            pass

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(10)

        t = QLabel("Reports")
        t.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        outer.addWidget(t)

        # Filter row
        f = QHBoxLayout()
        f.addWidget(QLabel("Period:"))
        self.period = QComboBox()
        self.period.addItems(["Today", "This Week", "This Month", "This Year", "All Time", "Custom"])
        self.period.currentTextChanged.connect(self._period_changed)
        f.addWidget(self.period)

        self.dfrom = QDateEdit(); self.dfrom.setCalendarPopup(True); self.dfrom.setDisplayFormat("yyyy-MM-dd")
        self.dto   = QDateEdit(); self.dto.setCalendarPopup(True);   self.dto.setDisplayFormat("yyyy-MM-dd")
        self.dfrom.setDate(QDate.currentDate())
        self.dto.setDate(QDate.currentDate())
        self.dfrom.dateChanged.connect(self._date_edited)
        self.dto.dateChanged.connect(self._date_edited)
        f.addWidget(QLabel("From:")); f.addWidget(self.dfrom)
        f.addWidget(QLabel("To:"));   f.addWidget(self.dto)

        f.addWidget(QLabel("Customer:"))
        self.customer = QComboBox()
        self.customer.setMinimumWidth(160)
        self.customer.currentIndexChanged.connect(self.refresh)
        f.addWidget(self.customer)

        f.addStretch()

        run = QPushButton("Run"); run.clicked.connect(self.refresh)
        f.addWidget(run)
        exp = QPushButton("📄 Export PDF"); exp.setObjectName("success"); exp.clicked.connect(self._export_pdf)
        f.addWidget(exp)
        outer.addLayout(f)

        # Search row
        self.search = SearchBox(None, placeholder="Search any column across all tables (product, code, customer, made-by, date, note, total)...")
        outer.addWidget(self.search)

        # Status line
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #6B7B8C; font-size: 12px; padding: 2px;")
        self.status_lbl.setWordWrap(True)
        outer.addWidget(self.status_lbl)

        # Tabs with per-category sub-tables
        self.tabs = QTabWidget()

        # PRODUCTION tab
        prod_tab = QWidget(); pv = QVBoxLayout(prod_tab); pv.setContentsMargins(0, 6, 0, 0); pv.setSpacing(6)
        self.tbl_prod = {}
        for code, label in CATS:
            lbl = QLabel(label); lbl.setStyleSheet("font-weight: bold; color: #1F4E79; font-size: 13px;")
            pv.addWidget(lbl)
            t = self._make_table(["Date","Code","Product","Quantity","Unit","Made By","Runs","Notes"])
            self.tbl_prod[code] = t
            self.search.attach(t)
            pv.addWidget(t)
        self.tabs.addTab(prod_tab, "Production")

        # MATERIAL USAGE tab
        mat_tab = QWidget(); mv = QVBoxLayout(mat_tab); mv.setContentsMargins(0, 6, 0, 0)
        self.tbl_mat = self._make_table(
            ["Code","Material","Opening Stock","Total Used","Purchased","Remaining","Unit"])
        self.search.attach(self.tbl_mat)
        mv.addWidget(self.tbl_mat)
        self.tabs.addTab(mat_tab, "Material Usage")

        # SALES tab
        sales_tab = QWidget(); sv = QVBoxLayout(sales_tab); sv.setContentsMargins(0, 6, 0, 0); sv.setSpacing(6)
        self.tbl_sales = {}
        for code, label in CATS:
            lbl = QLabel(label); lbl.setStyleSheet("font-weight: bold; color: #1F4E79; font-size: 13px;")
            sv.addWidget(lbl)
            t = self._make_table(
                ["Date","Code","Product","Customer","Quantity","Unit","Unit Price","Total (ETB)","Notes"])
            self.tbl_sales[code] = t
            self.search.attach(t)
            sv.addWidget(t)
        self.tabs.addTab(sales_tab, "Sales")

        # FINISHED GOODS tab
        fin_tab = QWidget(); fv = QVBoxLayout(fin_tab); fv.setContentsMargins(0, 6, 0, 0); fv.setSpacing(6)
        self.tbl_finished = {}
        for code, label in CATS:
            lbl = QLabel(label); lbl.setStyleSheet("font-weight: bold; color: #1F4E79; font-size: 13px;")
            fv.addWidget(lbl)
            t = self._make_table(["Code","Product","Produced","Sold","In Stock","Unit"])
            self.tbl_finished[code] = t
            self.search.attach(t)
            fv.addWidget(t)
        self.tabs.addTab(fin_tab, "Finished Goods")

        outer.addWidget(self.tabs, stretch=1)

        self._reload_customers()
        self._period_changed("Today")

    def _make_table(self, headers):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        return t

    def _reload_customers(self):
        current = self.customer.currentText() if self.customer.count() else ""
        self.customer.blockSignals(True)
        self.customer.clear()
        self.customer.addItem("(All customers)", None)
        for c in report_service.distinct_customers():
            self.customer.addItem(c, c)
        idx = self.customer.findText(current)
        if idx >= 0:
            self.customer.setCurrentIndex(idx)
        self.customer.blockSignals(False)

    def _period_changed(self, p):
        if self._suppress_period_signal:
            return
        today = datetime.now().date()
        self.dfrom.blockSignals(True); self.dto.blockSignals(True)
        if p == "Today":
            self.dfrom.setDate(QDate.currentDate()); self.dto.setDate(QDate.currentDate())
        elif p == "This Week":
            start = today - timedelta(days=6)
            self.dfrom.setDate(QDate(start.year, start.month, start.day))
            self.dto.setDate(QDate.currentDate())
        elif p == "This Month":
            start = today - timedelta(days=29)
            self.dfrom.setDate(QDate(start.year, start.month, start.day))
            self.dto.setDate(QDate.currentDate())
        elif p == "This Year":
            self.dfrom.setDate(QDate(today.year, 1, 1))
            self.dto.setDate(QDate.currentDate())
        elif p == "All Time":
            self.dfrom.setDate(QDate(2000, 1, 1))
            self.dto.setDate(QDate(2100, 12, 31))
        # Custom: leave as-is
        self.dfrom.blockSignals(False); self.dto.blockSignals(False)
        self.refresh()

    def _date_edited(self, *_):
        if self._suppress_period_signal:
            return
        self._suppress_period_signal = True
        try:
            if self.period.currentText() != "Custom":
                self.period.setCurrentText("Custom")
        finally:
            self._suppress_period_signal = False
        self.refresh()

    def _date_range(self):
        return (self.dfrom.date().toString("yyyy-MM-dd"),
                self.dto.date().toString("yyyy-MM-dd"))

    def _selected_customer(self):
        return self.customer.currentData()

    def refresh(self):
        df, dt = self._date_range()
        customer = self._selected_customer()

        total_prod_rows = 0
        for cat, _label in CATS:
            rows = report_service.production_report(df, dt, category=cat)
            self._fill_production_table(self.tbl_prod[cat], rows)
            total_prod_rows += len(rows)

        mat_rows = report_service.material_usage_report(df, dt)
        self._fill_material_table(self.tbl_mat, mat_rows)

        total_sales_rows = 0
        for cat, _label in CATS:
            rows = report_service.sales_report(df, dt, category=cat, customer=customer)
            self._fill_sales_table(self.tbl_sales[cat], rows)
            total_sales_rows += len(rows)

        fin_rows = report_service.finished_goods_report(df, dt)
        for cat, _label in CATS:
            sub = [r for r in fin_rows if r["category"] == cat]
            self._fill_finished_table(self.tbl_finished[cat], sub)

        self.search.reapply()

        total_records = total_prod_rows + total_sales_rows + len(mat_rows)
        cust_hint = f"  -  Customer: {customer}" if customer else ""
        if total_records > 0:
            self.status_lbl.setText(
                f"Showing {df} -> {dt}{cust_hint}  -  "
                f"Production rows: {total_prod_rows}   "
                f"Sales rows: {total_sales_rows}   "
                f"Materials: {len(mat_rows)}"
            )
            self.status_lbl.setStyleSheet("color: #27AE60; font-size: 12px; padding: 2px;")
        else:
            hint = self._build_no_data_hint(df, dt, customer)
            self.status_lbl.setText(hint)
            self.status_lbl.setStyleSheet("color: #C0392B; font-size: 12px; padding: 2px;")

    def _build_no_data_hint(self, df, dt, customer):
        from app.database.db import get_connection
        conn = get_connection()
        try:
            prod_total = conn.execute(
                "SELECT COUNT(*) AS c FROM vouchers WHERE voucher_type = 'PRODUCTION' AND state = 'POSTED'"
            ).fetchone()["c"]
            sales_total = conn.execute(
                "SELECT COUNT(*) AS c FROM vouchers WHERE voucher_type IN ('CASH_SALE', 'CREDIT_SALE') AND state = 'POSTED'"
            ).fetchone()["c"]
            if prod_total == 0 and sales_total == 0:
                return f"No records in {df} -> {dt}. There is no data in the database yet."
            mn = conn.execute(
                """SELECT MIN(d) AS mn, MAX(d) AS mx FROM (
                     SELECT date(created_at) AS d FROM vouchers
                     WHERE state = 'POSTED' AND voucher_type IN ('PRODUCTION', 'CASH_SALE', 'CREDIT_SALE')
                   )"""
            ).fetchone()
            extra = f" filtered by customer '{customer}'" if customer else ""
            if mn["mn"]:
                return (f"No records in {df} -> {dt}{extra}. "
                        f"Data exists between {mn['mn']} and {mn['mx']}. "
                        f"Try 'All Time' or 'This Year'.")
            return f"No records in {df} -> {dt}{extra} for the selected parameters."
        finally:
            conn.close()

    def _fill_production_table(self, table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            cells = [
                row["production_date"], row["code"], row["name"],
                f"{row['total_qty']:.2f}", unit,
                row.get("made_by") or "",
                str(row["runs"]),
                row.get("notes") or "",
            ]
            for c, val in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(val))

    def _fill_sales_table(self, table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            cells = [
                row["sale_date"], row["code"], row["name"],
                row.get("customer_name") or "",
                f"{row['quantity']:.2f}", unit,
                f"{row['unit_price']:,.2f}", f"{row['total']:,.2f}",
                row.get("note") or "",
            ]
            for c, val in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(val))

    def _fill_material_table(self, table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            cells = [
                row["code"], row["name"],
                f"{row['opening_stock']:.3f}",
                f"{row['total_used']:.3f}",
                f"{row['purchased']:.3f}",
                f"{row['remaining']:.3f}",
                row["unit"],
            ]
            for c, val in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(val))

    def _fill_finished_table(self, table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            cells = [
                row["code"], row["name"],
                f"{row['produced']:.2f}",
                f"{row['sold']:.2f}",
                f"{row['current_stock']:.2f}",
                unit,
            ]
            for c, val in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(val))

    def _export_pdf(self):
        df, dt = self._date_range()
        customer = self._selected_customer()
        suffix = f"_for_{customer.replace(' ','_')}" if customer else ""
        default = Path.cwd() / "exports" / f"MN_Construction_report_{df}_to_{dt}{suffix}.pdf"
        default.parent.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", str(default), "PDF Files (*.pdf)")
        if not path:
            return
        try:
            report_service.export_pdf("combined", df, dt, path, customer=customer)
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
