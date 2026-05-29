"""
User Audits View: Groups Reports & Audit Trails, Product Formulas, 
and User Management into a single admin control view.
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from app.ui.views.reports_view import ReportsView
from app.ui.views.products_view import ProductsView
from app.ui.views.users_view import UsersView
from app.services import auth_service


class UserAuditsView(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self._build()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("User Management & Audits")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        layout.addWidget(title)

        self.tabs = QTabWidget()

        self.voucher_browser = None
        self.reports_sub = None
        self.products_sub = None
        self.users_sub = None

        # Build sub-views based on permissions
        if auth_service.has_permission(self.user["id"], "audit:view"):
            from app.ui.views.voucher_browser_view import VoucherBrowserView
            self.voucher_browser = VoucherBrowserView(self.user)
            self.tabs.addTab(self.voucher_browser, "🧾 Voucher Browser")

            self.reports_sub = ReportsView()
            self.tabs.addTab(self.reports_sub, "📊 Reports & Audit Trails")

        if auth_service.has_permission(self.user["id"], "system:update-price"):
            self.products_sub = ProductsView(self.user)
            # Override products view layout margins to look nested
            self.products_sub.layout().setContentsMargins(10, 10, 10, 10)
            self.tabs.addTab(self.products_sub, "⚙ Product Formulas")

        if auth_service.has_permission(self.user["id"], "user:manage"):
            self.users_sub = UsersView(self.user)
            # Override users view layout margins to look nested
            self.users_sub.layout().setContentsMargins(10, 10, 10, 10)
            self.tabs.addTab(self.users_sub, "👥 User Management")

        layout.addWidget(self.tabs)

    def refresh(self):
        # Refresh any instantiated subviews
        if self.voucher_browser and hasattr(self.voucher_browser, "refresh"):
            try: 
                self.voucher_browser.refresh()
            except Exception: 
                pass
        if self.reports_sub and hasattr(self.reports_sub, "refresh"):
            try: 
                self.reports_sub.refresh()
            except Exception: 
                pass
        if self.products_sub and hasattr(self.products_sub, "refresh"):
            try: 
                self.products_sub.refresh()
            except Exception: 
                pass
        if self.users_sub and hasattr(self.users_sub, "refresh"):
            try: 
                self.users_sub.refresh()
            except Exception: 
                pass
