"""
PaginatedTableWidget:
Wraps QTableWidget and adds pagination footer controls (Prev, Next, Page Size)
to handle large scale databases without UI thread freeze.
Accepts a data fetcher and a populate callback.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QLabel, QComboBox, QHeaderView


class PaginatedTableWidget(QWidget):
    def __init__(self, headers, data_callback, populate_callback, parent=None):
        """
        :param headers: list of column title strings
        :param data_callback: callable taking (limit, offset) and returning a list of dicts
        :param populate_callback: callable taking (table_widget, data_list) to paint the rows
        """
        super().__init__(parent)
        self.headers = headers
        self.data_callback = data_callback
        self.populate_callback = populate_callback
        self.limit = 50
        self.offset = 0
        self.page = 1
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Inner Table
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Footer Pagination Row
        footer = QHBoxLayout()
        
        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.setFixedWidth(70)
        self.prev_btn.clicked.connect(self._prev)
        footer.addWidget(self.prev_btn)

        self.page_lbl = QLabel("Page 1")
        self.page_lbl.setAlignment(Qt.AlignCenter)
        self.page_lbl.setStyleSheet("font-weight: bold; color: #1F4E79;")
        footer.addWidget(self.page_lbl)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setFixedWidth(70)
        self.next_btn.clicked.connect(self._next)
        footer.addWidget(self.next_btn)

        footer.addStretch()

        footer.addWidget(QLabel("Page Size:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["50", "100", "200"])
        self.size_combo.currentTextChanged.connect(self._size_changed)
        footer.addWidget(self.size_combo)

        layout.addLayout(footer)

    def _prev(self):
        if self.offset >= self.limit:
            self.offset -= self.limit
            self.page -= 1
            self.refresh()

    def _next(self):
        self.offset += self.limit
        self.page += 1
        self.refresh()

    def _size_changed(self, text):
        self.limit = int(text)
        self.offset = 0
        self.page = 1
        self.refresh()

    def refresh(self):
        # Call data supplier
        data = self.data_callback(self.limit, self.offset)
        
        # Populate table via callback
        self.table.setRowCount(len(data))
        self.populate_callback(self.table, data)
        
        # Enable/Disable pagination buttons based on results
        self.prev_btn.setEnabled(self.offset > 0)
        self.next_btn.setEnabled(len(data) >= self.limit)
        
        self.page_lbl.setText(f"Page {self.page}")
        return data
