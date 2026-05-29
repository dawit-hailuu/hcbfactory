"""Bulk production entry — record many products at once.
One row per product line, common "made by" at the top, single Submit button.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QComboBox, QDoubleSpinBox, QLineEdit, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QCompleter)

from app.services import product_service, production_service


class BulkProductionView(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        # Keep the product list fresh in case admin added products elsewhere
        try:
            self._products = product_service.list_products()
            # Rebuild combobox contents in all existing rows (preserve current selection if possible)
            for r in range(self.table.rowCount()):
                cb = self.table.cellWidget(r, 0)
                if cb is None: continue
                old_pid = cb.currentData()
                cb.blockSignals(True)
                cb.clear()
                for p in self._products:
                    cb.addItem(f"{p['category']:7s}  {p['code']} — {p['name']}", p["id"])
                if old_pid is not None:
                    idx = cb.findData(old_pid)
                    if idx >= 0:
                        cb.setCurrentIndex(idx)
                cb.blockSignals(False)
                self._update_unit(r)
            # Refresh made_by completer too
            names = production_service.recent_made_by(limit=10)
            c = QCompleter(names, self.made_by)
            c.setCaseSensitivity(Qt.CaseInsensitive)
            c.setFilterMode(Qt.MatchContains)
            self.made_by.setCompleter(c)
        except Exception:
            pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)

        t = QLabel("Bulk Production Entry")
        t.setObjectName("pagetitle")
        outer.addWidget(t)
        outer.addWidget(QLabel(
            "Record several products produced today in one go. "
            "Add rows, fill in quantities, set 'Made by', then Submit."))

        head = QHBoxLayout()
        head.addWidget(QLabel("Made by:"))
        self.made_by = QLineEdit()
        self.made_by.setPlaceholderText("Worker name (applied to every row below)")
        names = production_service.recent_made_by(limit=10)
        c = QCompleter(names, self.made_by); c.setCaseSensitivity(Qt.CaseInsensitive)
        c.setFilterMode(Qt.MatchContains)
        self.made_by.setCompleter(c)
        head.addWidget(self.made_by, stretch=1)

        head.addWidget(QLabel("Note:"))
        self.note = QLineEdit(); self.note.setPlaceholderText("Optional, applies to all rows")
        head.addWidget(self.note, stretch=1)
        outer.addLayout(head)

        # Table: product, qty, unit
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Product","Quantity","Unit"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        outer.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        add = QPushButton("➕ Add Row"); add.clicked.connect(self._add_row)
        rm  = QPushButton("➖ Remove Selected"); rm.setObjectName("secondary"); rm.clicked.connect(self._remove_row)
        clr = QPushButton("Clear All"); clr.setObjectName("secondary"); clr.clicked.connect(self._clear)
        btn_row.addWidget(add); btn_row.addWidget(rm); btn_row.addWidget(clr); btn_row.addStretch()
        submit = QPushButton("✓ Submit All"); submit.setObjectName("success")
        submit.clicked.connect(self._submit)
        btn_row.addWidget(submit)
        outer.addLayout(btn_row)

        # Cache products for combo population
        self._products = product_service.list_products()

        # Start with 3 blank rows
        for _ in range(3):
            self._add_row()

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        # Product combobox
        cb = QComboBox()
        for p in self._products:
            cb.addItem(f"{p['category']:7s}  {p['code']} — {p['name']}", p["id"])
        cb.currentIndexChanged.connect(lambda _, r=row: self._update_unit(r))
        self.table.setCellWidget(row, 0, cb)
        # Quantity
        sp = QDoubleSpinBox(); sp.setRange(0, 1_000_000); sp.setDecimals(2)
        self.table.setCellWidget(row, 1, sp)
        # Unit label
        unit = QLabel("pieces")
        self.table.setCellWidget(row, 2, unit)
        self._update_unit(row)

    def _update_unit(self, row):
        cb = self.table.cellWidget(row, 0)
        pid = cb.currentData() if cb else None
        unit_lbl = self.table.cellWidget(row, 2)
        if pid is None or unit_lbl is None:
            return
        p = next((pp for pp in self._products if pp["id"] == pid), None)
        if p:
            unit_lbl.setText("pieces" if p["input_unit"] == "piece" else "m²")

    def _remove_row(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        if self.table.rowCount() == 0:
            self._add_row()

    def _clear(self):
        self.table.setRowCount(0)
        for _ in range(3):
            self._add_row()
        self.made_by.clear(); self.note.clear()

    def _submit(self):
        made_by = self.made_by.text().strip() or None
        note    = self.note.text().strip() or None

        # Collect & validate rows
        entries = []
        for r in range(self.table.rowCount()):
            cb = self.table.cellWidget(r, 0)
            qty_w = self.table.cellWidget(r, 1)
            if cb is None or qty_w is None: continue
            pid = cb.currentData()
            qty = qty_w.value()
            if pid is None or qty <= 0:
                continue
            entries.append((pid, qty))

        if not entries:
            QMessageBox.warning(self, "Nothing to submit", "Add at least one row with quantity > 0.")
            return

        confirm = QMessageBox.question(
            self, "Confirm bulk production",
            f"Record {len(entries)} production line(s)?",
            QMessageBox.Yes | QMessageBox.Cancel
        )
        if confirm != QMessageBox.Yes:
            return

        ok_count = 0
        errors = []
        failed_pids = set()
        for pid, qty in entries:
            try:
                production_service.record_production(
                    product_id=pid, quantity=qty,
                    user_id=self.user["id"], note=note, made_by=made_by,
                )
                ok_count += 1
            except ValueError as e:
                p = next((pp for pp in self._products if pp["id"] == pid), {"code": str(pid)})
                errors.append(f"{p['code']}: {e}")
                failed_pids.add(pid)

        msg = f"Recorded {ok_count} of {len(entries)} lines."
        if errors:
            msg += "\n\nFailures (rows kept so you can fix and resubmit):\n" + "\n".join(errors)
            QMessageBox.warning(self, "Done with errors", msg)
            # Remove only the succeeded rows; keep the failed ones
            for r in range(self.table.rowCount() - 1, -1, -1):
                cb = self.table.cellWidget(r, 0)
                qty_w = self.table.cellWidget(r, 1)
                if cb is None or qty_w is None: continue
                pid = cb.currentData()
                qty = qty_w.value()
                if pid is None or qty <= 0:
                    self.table.removeRow(r)
                    continue
                if pid not in failed_pids:
                    self.table.removeRow(r)
            # Ensure at least one blank row remains for further edits
            if self.table.rowCount() == 0:
                self._add_row()
        else:
            QMessageBox.information(self, "Done", msg)
            self._clear()
