"""Reusable dashboard stat card. Can be made clickable with on_click."""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel


class StatCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, value: str = "—", unit: str = "",
                 alert: bool = False, clickable: bool = False):
        super().__init__()
        self.setObjectName("card")
        self.setProperty("alert", "true" if alert else "false")
        self.setProperty("clickable", "true" if clickable else "false")
        self.setMinimumHeight(110)
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("cardtitle")
        lay.addWidget(self.title_lbl)

        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName("cardvalue")
        lay.addWidget(self.value_lbl)

        self.unit_lbl = QLabel(unit)
        self.unit_lbl.setObjectName("cardunit")
        lay.addWidget(self.unit_lbl)

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_value(self, value: str, unit: str = None, alert: bool = None):
        self.value_lbl.setText(value)
        if unit is not None:
            self.unit_lbl.setText(unit)
        if alert is not None:
            self.setProperty("alert", "true" if alert else "false")
            self.style().unpolish(self); self.style().polish(self)
