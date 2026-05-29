"""
HCB Factory Management System
Offline desktop application for Hollow Concrete Block & Terazo factory operations.

Entry point: launches login window, then main dashboard.
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from app.database.db import init_database
from app.database.seed import seed_initial_data
from app.ui.login_window import LoginWindow
from app.ui.main_window import MainWindow
from app.utils.theme import apply_theme


def main():
    # Initialize SQLite database (creates tables if not exist)
    init_database()
    # Seed materials, products, formulas, and default admin user (idempotent)
    seed_initial_data()

    app = QApplication(sys.argv)
    app.setApplicationName("MN Construction — Factory Manager")
    apply_theme(app, dark=False)  # Default light; user can toggle in main window

    # Login flow
    login = LoginWindow()
    if login.exec_() != LoginWindow.Accepted:
        sys.exit(0)

    user = login.authenticated_user
    main_window = MainWindow(user=user)
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
