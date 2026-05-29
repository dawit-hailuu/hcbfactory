"""Theme manager: light + dark stylesheets for a modern look."""
from PyQt5.QtWidgets import QApplication


PRIMARY      = "#1F4E79"
PRIMARY_DARK = "#163A5C"
ACCENT       = "#2E86C1"
SUCCESS      = "#27AE60"
DANGER       = "#C0392B"
WARNING      = "#E67E22"

LIGHT_QSS = f"""
QMainWindow, QDialog {{ background: #F8FAFD; }}
QLabel {{ color: #1E293B; font-size: 13px; font-family: 'Segoe UI', Inter, sans-serif; }}

/* Sidebar Style */
#sidebar {{ 
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {PRIMARY}, stop:1 {PRIMARY_DARK}); 
    border-right: 1px solid {PRIMARY_DARK};
}}
#sidebar QPushButton {{
    color: #E2E8F0; background: transparent; border: none;
    text-align: left; padding: 12px 18px; font-size: 14px;
    font-weight: 500; border-radius: 8px; margin: 3px 10px;
    font-family: 'Segoe UI', Inter, sans-serif;
}}
#sidebar QPushButton:hover {{ background: rgba(255, 255, 255, 0.1); color: white; }}
#sidebar QPushButton:checked {{ background: {ACCENT}; color: white; font-weight: bold; }}
#sidebar #brand {{
    color: white; font-size: 19px; font-weight: 800;
    padding: 24px 18px 18px 18px;
    letter-spacing: 0.5px;
}}
#sidebar #userlabel {{ color: #A5C2DE; padding: 6px 18px; font-size: 12px; }}

/* Cards */
#card {{
    background: white; border: 1px solid #E2E8F0; border-radius: 12px;
    padding: 12px;
}}
#card #cardtitle {{ color: #64748B; font-size: 11px; font-weight: bold;
                     text-transform: uppercase; letter-spacing: 0.8px; }}
#card #cardvalue {{ color: {PRIMARY}; font-size: 28px; font-weight: bold; }}
#card #cardunit  {{ color: #64748B; font-size: 11px; }}
#card[alert="true"] #cardvalue {{ color: {DANGER}; }}

/* Tables & Grids */
QTableView, QTableWidget {{
    background: white; gridline-color: #E2E8F0; color: #1E293B;
    border: 1px solid #CBD5E1; border-radius: 8px;
    selection-background-color: {ACCENT}; selection-color: white;
    alternate-background-color: #F8FAFC; font-size: 12px;
    font-family: 'Segoe UI', Inter, sans-serif;
}}
QHeaderView::section {{
    background: #EDF2F7; color: #2D3748; padding: 10px;
    border-bottom: 2px solid #CBD5E1; border-right: none;
    font-weight: bold; font-size: 12px;
}}

/* Form elements */
QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
    background: white; border: 1px solid #CBD5E1; border-radius: 6px;
    padding: 6px 10px; font-size: 13px; color: #1E293B; min-height: 20px;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{ 
    border: 1.5px solid {ACCENT};
    background: #FFFFFC;
}}
QComboBox::drop-down {{
    border: none;
}}

/* Buttons */
QPushButton {{
    background: {ACCENT}; color: white; border: none;
    padding: 8px 18px; border-radius: 6px; font-size: 13px;
    font-weight: 600; min-height: 20px;
}}
QPushButton:hover {{ background: {PRIMARY}; }}
QPushButton:pressed {{ background: {PRIMARY_DARK}; }}
QPushButton:disabled {{ background: #E2E8F0; color: #94A3B8; }}
QPushButton#danger {{ background: {DANGER}; }}
QPushButton#danger:hover {{ background: #991B1B; }}
QPushButton#success {{ background: {SUCCESS}; }}
QPushButton#success:hover {{ background: #166534; }}
QPushButton#secondary {{ background: #64748B; }}
QPushButton#secondary:hover {{ background: #475569; }}

/* Group Boxes & Tabs */
QGroupBox {{
    background: white; border: 1px solid #E2E8F0; border-radius: 10px;
    margin-top: 14px; padding-top: 14px; font-weight: bold; color: #1E293B;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: {PRIMARY}; }}

QTabWidget::pane {{ border: 1px solid #E2E8F0; border-radius: 8px; background: white; }}
QTabBar::tab {{
    background: #EDF2F7; color: #4A5568; padding: 10px 18px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 3px;
    font-weight: 500;
}}
QTabBar::tab:selected {{ background: white; color: {PRIMARY}; border-top: 3px solid {ACCENT}; font-weight: bold; }}

/* Modern Custom Scrollbars */
QScrollBar:vertical {{
    border: none; background: #F1F5F9; width: 8px; margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1; min-height: 24px; border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #94A3B8;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none; background: none;
}}
QScrollBar:horizontal {{
    border: none; background: #F1F5F9; height: 8px; margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: #CBD5E1; min-width: 24px; border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #94A3B8;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none; background: none;
}}

QStatusBar {{ background: #EDF2F7; color: #475569; font-size: 11px; }}
"""

DARK_QSS = f"""
QMainWindow, QDialog {{ background: #0F172A; }}
QLabel {{ color: #F1F5F9; font-size: 13px; font-family: 'Segoe UI', Inter, sans-serif; }}

/* Sidebar Style */
#sidebar {{ 
    background: #090D16; 
    border-right: 1px solid #1E293B;
}}
#sidebar QPushButton {{
    color: #94A3B8; background: transparent; border: none;
    text-align: left; padding: 12px 18px; font-size: 14px;
    font-weight: 500; border-radius: 8px; margin: 3px 10px;
    font-family: 'Segoe UI', Inter, sans-serif;
}}
#sidebar QPushButton:hover {{ background: #1E293B; color: white; }}
#sidebar QPushButton:checked {{ background: {ACCENT}; color: white; font-weight: bold; }}
#sidebar #brand {{
    color: white; font-size: 19px; font-weight: 800;
    padding: 24px 18px 18px 18px;
    letter-spacing: 0.5px;
}}
#sidebar #userlabel {{ color: #64748B; padding: 6px 18px; font-size: 12px; }}

/* Cards */
#card {{
    background: #1E293B; border: 1px solid #334155; border-radius: 12px;
    padding: 12px;
}}
#card #cardtitle {{ color: #94A3B8; font-size: 11px; font-weight: bold;
                     text-transform: uppercase; letter-spacing: 0.8px; }}
#card #cardvalue {{ color: #38BDF8; font-size: 28px; font-weight: bold; }}
#card #cardunit  {{ color: #94A3B8; font-size: 11px; }}
#card[alert="true"] #cardvalue {{ color: #EF4444; }}

/* Tables & Grids */
QTableView, QTableWidget {{
    background: #1E293B; gridline-color: #334155; color: #F1F5F9;
    border: 1px solid #334155; border-radius: 8px;
    selection-background-color: {ACCENT}; selection-color: white;
    alternate-background-color: #0F172A; font-size: 12px;
    font-family: 'Segoe UI', Inter, sans-serif;
}}
QHeaderView::section {{
    background: #0B0F19; color: #94A3B8; padding: 10px;
    border-bottom: 2px solid #334155; border-right: none;
    font-weight: bold; font-size: 12px;
}}

/* Form elements */
QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
    background: #0F172A; border: 1px solid #334155; border-radius: 6px;
    padding: 6px 10px; font-size: 13px; color: #F1F5F9; min-height: 20px;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{ 
    border: 1.5px solid {ACCENT};
    background: #0B0F19;
}}
QComboBox::drop-down {{
    border: none;
}}

/* Buttons */
QPushButton {{
    background: {ACCENT}; color: white; border: none;
    padding: 8px 18px; border-radius: 6px; font-size: 13px;
    font-weight: 600; min-height: 20px;
}}
QPushButton:hover {{ background: #0284C7; }}
QPushButton:pressed {{ background: #0369A1; }}
QPushButton:disabled {{ background: #334155; color: #64748B; }}
QPushButton#danger {{ background: {DANGER}; }}
QPushButton#danger:hover {{ background: #991B1B; }}
QPushButton#success {{ background: {SUCCESS}; }}
QPushButton#success:hover {{ background: #166534; }}
QPushButton#secondary {{ background: #475569; }}
QPushButton#secondary:hover {{ background: #334155; }}

/* Group Boxes & Tabs */
QGroupBox {{
    background: #1E293B; border: 1px solid #334155; border-radius: 10px;
    margin-top: 14px; padding-top: 14px; font-weight: bold; color: #F1F5F9;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #38BDF8; }}

QTabWidget::pane {{ border: 1px solid #334155; border-radius: 8px; background: #1E293B; }}
QTabBar::tab {{
    background: #0F172A; color: #94A3B8; padding: 10px 18px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 3px;
    font-weight: 500;
}}
QTabBar::tab:selected {{ background: #1E293B; color: white; border-top: 3px solid {ACCENT}; font-weight: bold; }}

/* Modern Custom Scrollbars */
QScrollBar:vertical {{
    border: none; background: #0B0F19; width: 8px; margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: #334155; min-height: 24px; border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #475569;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none; background: none;
}}
QScrollBar:horizontal {{
    border: none; background: #0B0F19; height: 8px; margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: #334155; min-width: 24px; border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #475569;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none; background: none;
}}

QStatusBar {{ background: #0B0F19; color: #64748B; font-size: 11px; }}
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
