"""
Main application window with sidebar navigation, 
permission-based layout assembly, and auto-lockout security filter.
Exposes exactly 9 views: Dashboard, Logistics, Production, Bulk Entry, Sales, Customers, Expenses, User / Audits, and Tools.
"""
from PyQt5.QtCore import Qt, QTimer, QObject, QEvent
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QStackedWidget, QLabel, QFrame,
                             QApplication, QStatusBar, QMessageBox, QDialog, QLineEdit)

from app.ui.views.dashboard_view import DashboardView
from app.ui.views.logistics_view import LogisticsView
from app.ui.views.production_view import ProductionView
from app.ui.views.bulk_production_view import BulkProductionView
from app.ui.views.sales_view import SalesView
from app.ui.views.customers_view import CustomersView
from app.ui.views.expenses_view import ExpensesView
from app.ui.views.user_audits_view import UserAuditsView
from app.ui.views.tools_view import ToolsView

from app.services import auth_service
from app.utils.theme import toggle_theme


class LockDialog(QDialog):
    """Secure modal dialog displayed during inactivity lockout."""
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("SuperERP — Locked")
        self.setFixedSize(380, 260)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(12)

        icon = QLabel("🔒")
        icon.setStyleSheet("font-size: 32px;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("Locked Due to Inactivity")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1F4E79;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        info = QLabel(f"User: {self.user['username']}")
        info.setStyleSheet("color: #6B7B8C;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Enter your password to unlock")
        self.password.returnPressed.connect(self._unlock)
        layout.addWidget(self.password)

        self.btn = QPushButton("Unlock")
        self.btn.clicked.connect(self._unlock)
        layout.addWidget(self.btn)

        layout.addStretch()

    def _unlock(self):
        success = auth_service.authenticate(self.user["username"], self.password.text())
        if success:
            self.accept()
        else:
            QMessageBox.warning(self, "Access Denied", "Incorrect password.")
            self.password.clear()
            self.password.setFocus()

    def reject(self):
        """Force quit the application if user attempts to dismiss the lock screen."""
        if QMessageBox.question(self, "Exit App", "Exit the application?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            QApplication.instance().quit()


class InactivityFilter(QObject):
    """PyQt global event filter resetting a timer on any key/mouse events."""
    def __init__(self, timeout_ms, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.timer = QTimer(self)
        self.timer.setInterval(timeout_ms)
        self.timer.timeout.connect(self.callback)
        self.timer.start()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.KeyPress, QEvent.MouseButtonPress, 
                            QEvent.MouseMove, QEvent.Wheel):
            self.timer.start()
        return False


class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"SuperERP — {user['username']} ({user['role'].upper()})")
        self.resize(1280, 800)
        self._build()
        self._setup_lockout()

    def _setup_lockout(self):
        # Auto lockout after 120 seconds of user inactivity
        self.inactivity_filter = InactivityFilter(120 * 1000, self._lock_screen, self)
        QApplication.instance().installEventFilter(self.inactivity_filter)

    def _lock_screen(self):
        self.inactivity_filter.timer.stop()
        lock = LockDialog(self.user, self)
        if lock.exec_() == QDialog.Accepted:
            self.inactivity_filter.timer.start()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)

        # ----- Sidebar -----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0,0,0,12)
        sl.setSpacing(2)

        brand = QLabel("🏭  SuperERP")
        brand.setObjectName("brand")
        sl.addWidget(brand)

        info = QLabel(f"Signed in: {self.user['username']}\nRole: {self.user['role'].upper()}")
        info.setObjectName("userlabel")
        sl.addWidget(info)
        sl.addSpacing(8)

        # Nav buttons — conditionally loaded based on permissions
        self.buttons = []
        self.stack = QStackedWidget()

        nav_items = [
            ("📊  Dashboard",   DashboardView())
        ]
        
        # Action-level permission check for Logistics
        if (auth_service.has_permission(self.user["id"], "inventory:add-stock") or
            auth_service.has_permission(self.user["id"], "inventory:adjust")):
            nav_items.append(("📦  Logistics", LogisticsView(self.user)))
            
        if auth_service.has_permission(self.user["id"], "production:create"):
            nav_items.append(("🏗  Production", ProductionView(self.user)))
            nav_items.append(("⚡  Bulk Entry", BulkProductionView(self.user)))
            
        if auth_service.has_permission(self.user["id"], "sale:create"):
            nav_items.append(("🛒  Sales", SalesView(self.user)))
            nav_items.append(("👥  Customers", CustomersView(self.user)))
            
        # Manager/Owner can view and manage Expenses
        if self.user["role"] in ("owner", "manager"):
            nav_items.append(("💵  Expenses", ExpensesView(self.user)))
            
        # Action-level permission check for User / Audits
        if (auth_service.has_permission(self.user["id"], "audit:view") or
            auth_service.has_permission(self.user["id"], "system:update-price") or
            auth_service.has_permission(self.user["id"], "user:manage")):
            nav_items.append(("👥  User / Audits", UserAuditsView(self.user)))

        # Manager/Owner can view Tools (backup/restore, Peachtree export)
        if self.user["role"] in ("owner", "manager"):
            nav_items.append(("🛠  Tools", ToolsView(self.user)))

        for label, view in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, w=view, b=btn: self._switch(w, b))
            sl.addWidget(btn)
            self.stack.addWidget(view)
            self.buttons.append((btn, view))

        sl.addStretch()

        theme_btn = QPushButton("🌓  Toggle Dark Mode")
        theme_btn.clicked.connect(self._toggle_theme)
        sl.addWidget(theme_btn)

        logout = QPushButton("⎋  Logout")
        logout.clicked.connect(self._logout)
        sl.addWidget(logout)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack, stretch=1)

        # Status bar
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage(f"Ready — logged in as {self.user['username']}")

        # Select first tab
        if self.buttons:
            self._switch(self.buttons[0][1], self.buttons[0][0])

    def _switch(self, view, button):
        for b, _ in self.buttons:
            b.setChecked(b is button)
        self.stack.setCurrentWidget(view)
        if hasattr(view, "refresh"):
            try: 
                view.refresh()
            except Exception: 
                pass

    def _toggle_theme(self):
        toggle_theme(QApplication.instance())

    def _logout(self):
        if QMessageBox.question(self, "Logout", "Sign out and exit?") == QMessageBox.Yes:
            QApplication.instance().quit()
