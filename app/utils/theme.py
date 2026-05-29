"""Theme manager: light + dark stylesheets for a modern look."""
from PyQt5.QtWidgets import QApplication


PRIMARY      = "#1F4E79"
PRIMARY_DARK = "#163A5C"
ACCENT       = "#2E86C1"
SUCCESS      = "#27AE60"
DANGER       = "#C0392B"
WARNING      = "#E67E22"

LIGHT_QSS = f"""
QMainWindow, QDialog {{ background: #F4F6FA; }}
QLabel {{ color: #1B2733; font-size: 13px; }}
QLabel#pagetitle {{ font-size: 22px; font-weight: bold; color: {PRIMARY}; }}
QLabel#sectionhead {{ font-size: 16px; font-weight: bold; color: {PRIMARY}; margin-top: 6px; }}
QLabel#subhead {{ font-weight: bold; color: {PRIMARY}; font-size: 13px; }}
QLabel#hint {{ color: #6B7B8C; font-size: 11px; }}
QLabel#hintmedium {{ color: #6B7B8C; font-size: 12px; }}
QLabel#emptystate {{ color: #6B7B8C; padding: 24px; }}
QLabel#summarybox {{
    background: #E8EEF7; padding: 10px; border-radius: 6px;
    color: {PRIMARY}; font-weight: bold;
}}
QLabel#dangerhead {{ font-size: 16px; font-weight: bold; color: {DANGER}; margin-top: 6px; }}
#sidebar {{ background: {PRIMARY}; }}
#sidebar QPushButton {{
    color: white; background: transparent; border: none;
    text-align: left; padding: 12px 18px; font-size: 14px;
    border-radius: 6px; margin: 2px 8px;
}}
#sidebar QPushButton:hover {{ background: {PRIMARY_DARK}; }}
#sidebar QPushButton:checked {{ background: {ACCENT}; font-weight: bold; }}
#sidebar #brand {{
    color: white; font-size: 18px; font-weight: bold;
    padding: 22px 18px 16px 18px;
}}
#sidebar #userlabel {{ color: #cfe2f3; padding: 8px 18px; font-size: 12px; }}

#card {{
    background: white; border: 1px solid #DDE3EC; border-radius: 10px;
}}
#card #cardtitle {{ color: #6B7B8C; font-size: 12px; font-weight: bold;
                     text-transform: uppercase; letter-spacing: 1px; }}
#card #cardvalue {{ color: {PRIMARY}; font-size: 26px; font-weight: bold; }}
#card #cardunit  {{ color: #6B7B8C; font-size: 12px; }}
#card[alert="true"] #cardvalue {{ color: {DANGER}; }}

QTableView, QTableWidget {{
    background: white; gridline-color: #E1E6EE;
    border: 1px solid #DDE3EC; border-radius: 6px;
    selection-background-color: {ACCENT}; selection-color: white;
    alternate-background-color: #F8FAFD; font-size: 12px;
}}
QHeaderView::section {{
    background: {PRIMARY}; color: white; padding: 8px;
    border: none; font-weight: bold; font-size: 12px;
}}

QPushButton {{
    background: {ACCENT}; color: white; border: none;
    padding: 8px 16px; border-radius: 6px; font-size: 13px;
    min-height: 18px;
}}
QPushButton:hover {{ background: {PRIMARY}; }}
QPushButton:disabled {{ background: #B0BAC8; color: #EFEFEF; }}
QPushButton#danger {{ background: {DANGER}; }}
QPushButton#danger:hover {{ background: #922B1F; }}
QPushButton#success {{ background: {SUCCESS}; }}
QPushButton#secondary {{ background: #6B7B8C; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
    background: white; border: 1px solid #C4CCD8; border-radius: 5px;
    padding: 6px 8px; font-size: 13px; min-height: 18px;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}

QGroupBox {{
    background: white; border: 1px solid #DDE3EC; border-radius: 8px;
    margin-top: 12px; padding-top: 12px; font-weight: bold;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {PRIMARY}; }}

QTabWidget::pane {{ border: 1px solid #DDE3EC; border-radius: 6px; background: white; }}
QTabBar::tab {{
    background: #E8EEF7; padding: 8px 16px; border-top-left-radius: 6px;
    border-top-right-radius: 6px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {PRIMARY}; color: white; }}

QStatusBar {{ background: #E8EEF7; color: #1B2733; }}
"""

DARK_QSS = f"""
QMainWindow, QDialog {{ background: #1A1F2B; }}
QLabel {{ color: #DDE3EC; font-size: 13px; }}
QLabel#pagetitle {{ font-size: 22px; font-weight: bold; color: #6FB3F2; }}
QLabel#sectionhead {{ font-size: 16px; font-weight: bold; color: #6FB3F2; margin-top: 6px; }}
QLabel#subhead {{ font-weight: bold; color: #6FB3F2; font-size: 13px; }}
QLabel#hint {{ color: #8B97A8; font-size: 11px; }}
QLabel#hintmedium {{ color: #8B97A8; font-size: 12px; }}
QLabel#emptystate {{ color: #8B97A8; padding: 24px; }}
QLabel#summarybox {{
    background: #242B3D; padding: 10px; border-radius: 6px;
    color: #6FB3F2; font-weight: bold;
}}
QLabel#dangerhead {{ font-size: 16px; font-weight: bold; color: #FF6B6B; margin-top: 6px; }}
#sidebar {{ background: #0F1420; }}
#sidebar QPushButton {{
    color: #DDE3EC; background: transparent; border: none;
    text-align: left; padding: 12px 18px; font-size: 14px;
    border-radius: 6px; margin: 2px 8px;
}}
#sidebar QPushButton:hover {{ background: #1A2236; }}
#sidebar QPushButton:checked {{ background: {ACCENT}; color: white; font-weight: bold; }}
#sidebar #brand {{ color: white; font-size: 18px; font-weight: bold; padding: 22px 18px 16px 18px; }}
#sidebar #userlabel {{ color: #8B97A8; padding: 8px 18px; font-size: 12px; }}

#card {{ background: #242B3D; border: 1px solid #2E3650; border-radius: 10px; }}
#card #cardtitle {{ color: #8B97A8; font-size: 12px; font-weight: bold;
                    text-transform: uppercase; letter-spacing: 1px; }}
#card #cardvalue {{ color: #6FB3F2; font-size: 26px; font-weight: bold; }}
#card #cardunit  {{ color: #8B97A8; font-size: 12px; }}
#card[alert="true"] #cardvalue {{ color: #FF6B6B; }}

QTableView, QTableWidget {{
    background: #242B3D; gridline-color: #2E3650; color: #DDE3EC;
    border: 1px solid #2E3650; border-radius: 6px;
    selection-background-color: {ACCENT}; selection-color: white;
    alternate-background-color: #1F2433; font-size: 12px;
}}
QHeaderView::section {{
    background: #0F1420; color: #DDE3EC; padding: 8px;
    border: none; font-weight: bold; font-size: 12px;
}}

QPushButton {{
    background: {ACCENT}; color: white; border: none;
    padding: 8px 16px; border-radius: 6px; font-size: 13px;
    min-height: 18px;
}}
QPushButton:hover {{ background: #1F76B0; }}
QPushButton:disabled {{ background: #404A5E; color: #8B97A8; }}
QPushButton#danger {{ background: {DANGER}; }}
QPushButton#success {{ background: {SUCCESS}; }}
QPushButton#secondary {{ background: #525E78; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
    background: #1A1F2B; border: 1px solid #2E3650; border-radius: 5px;
    padding: 6px 8px; font-size: 13px; color: #DDE3EC; min-height: 18px;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}

QGroupBox {{
    background: #242B3D; border: 1px solid #2E3650; border-radius: 8px;
    margin-top: 12px; padding-top: 12px; font-weight: bold; color: #DDE3EC;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #6FB3F2; }}

QTabWidget::pane {{ border: 1px solid #2E3650; border-radius: 6px; background: #242B3D; }}
QTabBar::tab {{
    background: #1F2433; color: #DDE3EC; padding: 8px 16px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {ACCENT}; color: white; }}

QStatusBar {{ background: #0F1420; color: #DDE3EC; }}
"""


_current_dark = False

def apply_theme(app: QApplication, dark: bool = False):
    global _current_dark
    _current_dark = dark
    app.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)


def is_dark() -> bool:
    return _current_dark


def toggle_theme(app: QApplication):
    apply_theme(app, not _current_dark)
