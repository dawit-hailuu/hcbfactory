"""
Reusable case-insensitive search box for QTableWidget.

Usage:
    self.search = SearchBox(self.table, placeholder="Search sales...")
    layout.addWidget(self.search)

Optionally limit search to specific columns:
    self.search = SearchBox(self.table, columns=[0, 1, 3], placeholder="...")

You can also attach multiple tables to one search box — every keystroke will
filter all of them at once. Useful in Reports where one search bar drives
several sub-tables.

    sb = SearchBox(None, placeholder="Search...")
    sb.attach(table1)
    sb.attach(table2)
"""
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel


class SearchBox(QWidget):
    def __init__(self, table=None, columns=None, placeholder: str = "Search...",
                 debounce_ms: int = 150, parent=None):
        super().__init__(parent)
        self._tables = []   # list of (QTableWidget, columns_or_None)
        if table is not None:
            self._tables.append((table, columns))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 14px;")
        lay.addWidget(icon)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setClearButtonEnabled(True)
        lay.addWidget(self.input, stretch=1)

        # Debounce so we don't filter on every keystroke instantly
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._apply)
        self.input.textChanged.connect(lambda _: self._timer.start())

    def attach(self, table, columns=None):
        """Register an additional table to filter alongside the primary."""
        self._tables.append((table, columns))

    def text(self) -> str:
        return self.input.text()

    def clear(self):
        self.input.clear()

    def reapply(self):
        """Call after the table data is refreshed to re-apply the current filter."""
        self._apply()

    def _apply(self):
        q = self.input.text().strip().lower()
        for table, columns in self._tables:
            if table is None or table.rowCount() == 0:
                continue
            ncols = table.columnCount()
            cols = columns if columns is not None else range(ncols)
            for row in range(table.rowCount()):
                if not q:
                    table.setRowHidden(row, False)
                    continue
                matched = False
                for c in cols:
                    if c >= ncols:
                        continue
                    item = table.item(row, c)
                    if item is None:
                        continue
                    if q in item.text().lower():
                        matched = True
                        break
                table.setRowHidden(row, not matched)
