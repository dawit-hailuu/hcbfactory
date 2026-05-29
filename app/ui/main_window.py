"""Main application window with sidebar nav."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QStackedWidget, QLabel, QFrame,
                             QApplication, QStatusBar, QMessageBox)

from app.ui.views.dashboard_view import DashboardView
from app.ui.views.inventory_view import InventoryView
from app.ui.views.production_view import ProductionView
from app.ui.views.bulk_production_view import BulkProductionView
from app.ui.views.sales_view import SalesView
from app.ui.views.customers_view import CustomersView
from app.ui.views.expenses_view import ExpensesView
from app.ui.views.products_view import ProductsView
from app.ui.views.reports_view import ReportsView
from app.ui.views.tools_view import ToolsView
from app.ui.views.audit_view import AuditLogView
from app.ui.views.users_view import UsersView
from app.utils.theme import toggle_theme


class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"MN Construction — {user['username']} ({user['role']})")
        self.resize(1280, 800)
        self._build()

    def _build(self):
        central = QWidget(); self.setCentralWidget(central)
        layout = QHBoxLayout(central); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)

        # ----- Sidebar -----
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(220)
        sl = QVBoxLayout(sidebar); sl.setContentsMargins(0,0,0,12); sl.setSpacing(2)

        brand = QLabel("🏭  MN Construction"); brand.setObjectName("brand"); sl.addWidget(brand)

        info = QLabel(f"Signed in: {self.user['username']}\nRole: {self.user['role']}")
        info.setObjectName("userlabel"); sl.addWidget(info)
        sl.addSpacing(8)

        # Nav buttons — order matters
        self.buttons = []
        self.stack = QStackedWidget()

        nav_items = [
            ("📊  Dashboard",       DashboardView()),
            ("📦  Inventory",       InventoryView(self.user)),
            ("🏗  Production",      ProductionView(self.user)),
            ("📋  Bulk Entry",      BulkProductionView(self.user)),
            ("🛒  Sales",           SalesView(self.user)),
            ("👤  Customers",       CustomersView(self.user)),
            ("📈  Reports",         ReportsView()),
        ]
        # Admin-only screens
        if self.user["role"] == "admin":
            nav_items.append(("💸  Expenses",  ExpensesView(self.user)))
            nav_items.append(("⚙  Products",   ProductsView(self.user)))
            nav_items.append(("🛠  Tools",     ToolsView(self.user)))
            nav_items.append(("📜  Audit Log", AuditLogView(self.user)))
            nav_items.append(("👥  Users",     UsersView(self.user)))

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
        sb = QStatusBar(); self.setStatusBar(sb)
        sb.showMessage(f"Ready — logged in as {self.user['username']}")

        # Select first tab
        if self.buttons:
            self._switch(self.buttons[0][1], self.buttons[0][0])

    def _switch(self, view, button):
        # uncheck others
        for b, _ in self.buttons:
            b.setChecked(b is button)
        self.stack.setCurrentWidget(view)
        # refresh on switch so data stays in sync
        if hasattr(view, "refresh"):
            try: view.refresh()
            except Exception: pass

    def _toggle_theme(self):
        toggle_theme(QApplication.instance())

    def _logout(self):
        if QMessageBox.question(self, "Logout", "Sign out and exit?") == QMessageBox.Yes:
            QApplication.instance().quit()
