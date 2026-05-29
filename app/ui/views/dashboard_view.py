"""Dashboard: top-level metrics + low-stock alerts + finished-product summary.

Stat cards (Revenue Today, Sales Today, Production Today, Low Stock) are
CLICKABLE — each opens a popup with the underlying detail rows.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDialog)

from app.services import report_service
from app.ui.widgets.stat_card import StatCard


class _DetailDialog(QDialog):
    """Generic recent-activity popup. Takes title + headers + rows of strings."""
    def __init__(self, title, headers, rows, parent=None, empty_msg="No records today."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 380)
        v = QVBoxLayout(self)

        h = QLabel(title)
        h.setStyleSheet("font-size: 16px; font-weight: bold; color: #1F4E79; padding: 4px 0;")
        v.addWidget(h)

        if not rows:
            empty = QLabel(empty_msg)
            empty.setStyleSheet("color: #6B7B8C; padding: 20px;")
            empty.setAlignment(Qt.AlignCenter)
            v.addWidget(empty)
        else:
            tbl = QTableWidget(len(rows), len(headers))
            tbl.setHorizontalHeaderLabels(headers)
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.verticalHeader().setVisible(False)
            tbl.setAlternatingRowColors(True)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    tbl.setItem(r, c, QTableWidgetItem(str(val)))
            v.addWidget(tbl)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        close = QPushButton("Close"); close.setObjectName("secondary"); close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        v.addLayout(btn_row)


class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self._build()
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        try: self.refresh()
        except Exception: pass

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        header.addWidget(title)
        header.addStretch()
        hint = QLabel("Tip: click any card below to see today's details")
        hint.setStyleSheet("color: #6B7B8C; font-size: 12px;")
        header.addWidget(hint)
        refresh = QPushButton("⟳ Refresh")
        refresh.setObjectName("secondary")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        outer.addLayout(header)

        # Top stat cards — all clickable
        self.card_revenue  = StatCard("Revenue Today",   "0.00", "ETB",    clickable=True)
        self.card_sales    = StatCard("Sales Today",     "0",    "items",  clickable=True)
        self.card_prod     = StatCard("Production Today","0",    "items",  clickable=True)
        self.card_lowstock = StatCard("Low Stock Alerts","0",    "materials", clickable=True)

        self.card_revenue.clicked.connect(self._show_today_sales)
        self.card_sales.clicked.connect(self._show_today_sales)
        self.card_prod.clicked.connect(self._show_today_production)
        self.card_lowstock.clicked.connect(self._show_low_stock)

        row = QHBoxLayout()
        row.setSpacing(12)
        for c in (self.card_revenue, self.card_sales, self.card_prod, self.card_lowstock):
            row.addWidget(c)
        outer.addLayout(row)

        # Material stock cards (also clickable -> low-stock popup for the same material)
        mats_label = QLabel("Raw Materials")
        mats_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1F4E79; margin-top: 6px;")
        outer.addWidget(mats_label)

        self.materials_grid = QGridLayout()
        self.materials_grid.setSpacing(10)
        wrap = QWidget(); wrap.setLayout(self.materials_grid)
        outer.addWidget(wrap)

        # Low stock summary table
        bottom_label_low = QLabel("Low-Stock Alerts")
        bottom_label_low.setStyleSheet("font-size: 16px; font-weight: bold; color: #C0392B; margin-top: 6px;")
        outer.addWidget(bottom_label_low)
        self.low_table = QTableWidget(0, 4)
        self.low_table.setHorizontalHeaderLabels(["Material", "Current Stock", "Threshold", "Unit"])
        self.low_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.low_table.verticalHeader().setVisible(False)
        self.low_table.setAlternatingRowColors(True)
        self.low_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.low_table.setMaximumHeight(180)
        outer.addWidget(self.low_table)

        outer.addStretch()

    def refresh(self):
        data = report_service.dashboard_summary()

        self.card_revenue.set_value(f"{data['sales_today_revenue']:,.2f}", "ETB")
        self.card_sales.set_value(f"{data['sales_today_qty']:,.0f}", "items sold")
        self.card_prod.set_value(f"{data['production_today_qty']:,.0f}", "items produced")
        self.card_lowstock.set_value(str(len(data["low_stock"])), "materials",
                                     alert=len(data["low_stock"]) > 0)

        # Material grid: clear & rebuild
        while self.materials_grid.count():
            item = self.materials_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        for i, m in enumerate(data["materials"]):
            alert = m["current_stock"] <= m["low_stock_alert"]
            card = StatCard(m["name"], f"{m['current_stock']:.2f}", m["unit"], alert=alert)
            self.materials_grid.addWidget(card, i // 4, i % 4)

        # Low stock table
        self.low_table.setRowCount(len(data["low_stock"]))
        for r, m in enumerate(data["low_stock"]):
            self.low_table.setItem(r, 0, QTableWidgetItem(m["name"]))
            self.low_table.setItem(r, 1, QTableWidgetItem(f"{m['current_stock']:.3f}"))
            self.low_table.setItem(r, 2, QTableWidgetItem(f"{m['low_stock_alert']:.3f}"))
            self.low_table.setItem(r, 3, QTableWidgetItem(m["unit"]))

    # ── Popup handlers ─────────────────────────────────────────────────────
    def _show_today_sales(self):
        rows = report_service.todays_sales()
        data = []
        for s in rows:
            unit = "pieces" if s["input_unit"] == "piece" else "m²"
            data.append([
                s["sale_date"],
                s.get("customer_name") or "—",
                f"{s['code']} — {s['name']}",
                f"{s['quantity']:.2f} {unit}",
                f"{s['unit_price']:,.2f}",
                f"{s['total']:,.2f} ETB",
            ])
        dlg = _DetailDialog(
            "Today's Sales",
            ["Date","Customer","Product","Quantity","Unit Price","Total"],
            data, parent=self,
            empty_msg="No sales recorded today yet."
        )
        dlg.exec_()

    def _show_today_production(self):
        rows = report_service.todays_production()
        data = []
        for p in rows:
            unit = "pieces" if p["input_unit"] == "piece" else "m²"
            data.append([
                p["production_date"],
                f"{p['code']} — {p['name']}",
                f"{p['quantity']:.2f} {unit}",
                p.get("made_by") or "—",
                p.get("note") or "",
            ])
        dlg = _DetailDialog(
            "Today's Production",
            ["Date","Product","Quantity","Made By","Note"],
            data, parent=self,
            empty_msg="No production runs recorded today yet."
        )
        dlg.exec_()

    def _show_low_stock(self):
        from app.services import inventory_service
        low = inventory_service.low_stock_materials()
        data = [
            [m["name"], f"{m['current_stock']:.3f}",
             f"{m['low_stock_alert']:.3f}", m["unit"]]
            for m in low
        ]
        dlg = _DetailDialog(
            "Low-Stock Materials",
            ["Material","Current Stock","Threshold","Unit"],
            data, parent=self,
            empty_msg="All materials are above their thresholds. 👍"
        )
        dlg.exec_()
