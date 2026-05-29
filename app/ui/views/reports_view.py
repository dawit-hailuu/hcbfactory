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
        t.setObjectName("pagetitle")
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
        self.status_lbl.setObjectName("hintmedium")
        self.status_lbl.setWordWrap(True)
        outer.addWidget(self.status_lbl)

        # Tabs with per-category sub-tables
        self.tabs = QTabWidget()

        # PRODUCTION tab
        prod_tab = QWidget(); pv = QVBoxLayout(prod_tab); pv.setContentsMargins(0, 6, 0, 0); pv.setSpacing(6)
        self.tbl_prod = {}
        for code, label in CATS:
            lbl = QLabel(label); lbl.setObjectName("subhead")
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
            lbl = QLabel(label); lbl.setObjectName("subhead")
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
            lbl = QLabel(label); lbl.setObjectName("subhead")
            fv.addWidget(lbl)
            t = self._make_table(["Code","Product","Produced","Sold","In Stock","Unit"])
            self.tbl_finished[code] = t
            self.search.attach(t)
            fv.addWidget(t)
        self.tabs.addTab(fin_tab, "Finished Goods")

        # PROFIT & LOSS tab
        pl_tab = QWidget(); plv = QVBoxLayout(pl_tab); plv.setContentsMargins(0, 6, 0, 0); plv.setSpacing(6)
        self.pl_summary_lbl = QLabel("")
        self.pl_summary_lbl.setObjectName("summarybox")
        self.pl_summary_lbl.setWordWrap(True)
        plv.addWidget(self.pl_summary_lbl)

        sh = QLabel("Profit by Product"); sh.setObjectName("subhead")
        plv.addWidget(sh)
        self.tbl_profit = self._make_table(
            ["Category","Code","Product","Sold","Revenue (ETB)","Cost (ETB)","Profit (ETB)"])
        self.search.attach(self.tbl_profit)
        plv.addWidget(self.tbl_profit)

        sh = QLabel("Expenses by Category"); sh.setObjectName("subhead")
        plv.addWidget(sh)
        self.tbl_expenses = self._make_table(["Category","Total (ETB)","Entries"])
        self.search.attach(self.tbl_expenses)
        plv.addWidget(self.tbl_expenses)
        self.tabs.addTab(pl_tab, "Profit & Loss")

        # WASTE tab
        waste_tab = QWidget(); wv = QVBoxLayout(waste_tab); wv.setContentsMargins(0, 6, 0, 0)
        self.tbl_waste = self._make_table(
            ["Category","Code","Product","Total Wasted","Unit","Events"])
        self.search.attach(self.tbl_waste)
        wv.addWidget(self.tbl_waste)
        self.tabs.addTab(waste_tab, "Waste")

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
        from app.utils import clock
        today = clock.today_date()  # actual local date
        self.dfrom.blockSignals(True); self.dto.blockSignals(True)
        if p == "Today":
            self.dfrom.setDate(QDate.currentDate()); self.dto.setDate(QDate.currentDate())
        elif p == "This Week":
            # Monday of current week through today
            start = today - timedelta(days=today.weekday())
            self.dfrom.setDate(QDate(start.year, start.month, start.day))
            self.dto.setDate(QDate.currentDate())
        elif p == "This Month":
            # First day of current month through today
            self.dfrom.setDate(QDate(today.year, today.month, 1))
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
        try:
            self._refresh_impl()
        except Exception as e:
            self.status_lbl.setText(f"Unable to load reports: {e}")
            self.status_lbl.setStyleSheet("color: #C0392B; font-size: 12px; padding: 2px;")

    def _refresh_impl(self):
        df, dt = self._date_range()
        customer = self._selected_customer()

        # Validate: From must be <= To. If reversed, silently swap and tell the user.
        if df > dt:
            df, dt = dt, df
            self.dfrom.blockSignals(True); self.dto.blockSignals(True)
            try:
                fy, fm, fd = [int(x) for x in df.split("-")]
                ty, tm, td = [int(x) for x in dt.split("-")]
                self.dfrom.setDate(QDate(fy, fm, fd))
                self.dto.setDate(QDate(ty, tm, td))
            finally:
                self.dfrom.blockSignals(False); self.dto.blockSignals(False)

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

        # Profit & Loss
        ps = report_service.profit_summary(df, dt)
        self.pl_summary_lbl.setText(
            f"<b>Revenue:</b> {ps['revenue']:,.2f} ETB "
            f"&nbsp;&nbsp; <b>Cost of Sales:</b> {ps['cost_of_sales']:,.2f} ETB "
            f"&nbsp;&nbsp; <b>Gross Profit:</b> {ps['gross_profit']:,.2f} ETB "
            f"({ps['margin_pct']:.1f}% margin)"
            f"<br/><b>Operating Expenses:</b> {ps['operating_expenses']:,.2f} ETB "
            f"&nbsp;&nbsp; <b>Net Profit:</b> {ps['net_profit']:,.2f} ETB"
        )
        pp_rows = report_service.profit_by_product(df, dt)
        self.tbl_profit.setRowCount(len(pp_rows))
        for r, row in enumerate(pp_rows):
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            cells = [row["category"], row["code"], row["name"],
                     f"{row['qty_sold']:.2f} {unit}",
                     f"{row['revenue']:,.2f}",
                     f"{(row['cost'] or 0):,.2f}",
                     f"{(row['profit'] or 0):,.2f}"]
            for c, v in enumerate(cells):
                self.tbl_profit.setItem(r, c, QTableWidgetItem(v))

        from app.services import expense_service
        es = expense_service.expense_summary(df, dt)
        self.tbl_expenses.setRowCount(len(es))
        for r, row in enumerate(es):
            self.tbl_expenses.setItem(r, 0, QTableWidgetItem(row["category"]))
            self.tbl_expenses.setItem(r, 1, QTableWidgetItem(f"{row['total']:,.2f}"))
            self.tbl_expenses.setItem(r, 2, QTableWidgetItem(str(row["count"])))

        # Waste
        from app.services import waste_service
        wr = waste_service.waste_summary(df, dt)
        self.tbl_waste.setRowCount(len(wr))
        for r, row in enumerate(wr):
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            self.tbl_waste.setItem(r, 0, QTableWidgetItem(row["category"]))
            self.tbl_waste.setItem(r, 1, QTableWidgetItem(row["code"]))
            self.tbl_waste.setItem(r, 2, QTableWidgetItem(row["name"]))
            self.tbl_waste.setItem(r, 3, QTableWidgetItem(f"{row['total_waste']:.2f}"))
            self.tbl_waste.setItem(r, 4, QTableWidgetItem(unit))
            self.tbl_waste.setItem(r, 5, QTableWidgetItem(str(row["waste_events"])))

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
            prod_total = conn.execute("SELECT COUNT(*) AS c FROM production").fetchone()["c"]
            sales_total = conn.execute("SELECT COUNT(*) AS c FROM sales").fetchone()["c"]
            if prod_total == 0 and sales_total == 0:
                return f"No records in {df} -> {dt}. There is no data in the database yet."
            mn = conn.execute(
                """SELECT MIN(d) AS mn, MAX(d) AS mx FROM (
                     SELECT production_date AS d FROM production
                     UNION ALL SELECT sale_date AS d FROM sales)"""
            ).fetchone()
            extra = f" filtered by customer '{customer}'" if customer else ""
            return (f"No records in {df} -> {dt}{extra}. "
                    f"Data exists between {mn['mn']} and {mn['mx']}. "
                    f"Try 'All Time' or 'This Year'.")
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
        from app.utils.paths import EXPORTS
        df, dt = self._date_range()
        customer = self._selected_customer()
        suffix = f"_for_{customer.replace(' ','_')}" if customer else ""
        EXPORTS.mkdir(parents=True, exist_ok=True)
        default = EXPORTS / f"MN_Construction_report_{df}_to_{dt}{suffix}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", str(default), "PDF Files (*.pdf)")
        if not path:
            return
        try:
            report_service.export_pdf("combined", df, dt, path, customer=customer)
            QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
        except PermissionError:
            QMessageBox.critical(
                self, "Cannot save",
                f"Cannot write to:\n{path}\n\n"
                "The file may be open in another program (close it and try again), "
                "or you may not have permission to write to that folder."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
