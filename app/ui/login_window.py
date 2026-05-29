"""Login dialog."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFrame, QMessageBox)

from app.services import auth_service


class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MN Construction — Login")
        self.setFixedSize(420, 380)
        self.authenticated_user = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(14)

        title = QLabel("🏭  MN Construction")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1F4E79;")
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        sub = QLabel("Sign in to continue")
        sub.setStyleSheet("color: #6B7B8C;")
        sub.setAlignment(Qt.AlignCenter)
        outer.addWidget(sub)

        outer.addSpacing(10)

        outer.addWidget(QLabel("Username"))
        self.username = QLineEdit()
        self.username.setPlaceholderText("admin")
        outer.addWidget(self.username)

        outer.addWidget(QLabel("Password"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("••••••••")
        outer.addWidget(self.password)

        outer.addSpacing(8)
        btn = QPushButton("Sign In")
        btn.clicked.connect(self._do_login)
        outer.addWidget(btn)

        hint = QLabel("Default: admin / admin123")
        hint.setStyleSheet("color: #B0BAC8; font-size: 11px;")
        hint.setAlignment(Qt.AlignCenter)
        outer.addWidget(hint)

        outer.addStretch()
        self.password.returnPressed.connect(self._do_login)
        self.username.returnPressed.connect(self._do_login)

    def _do_login(self):
        user = auth_service.authenticate(self.username.text().strip(),
                                         self.password.text())
        if user is None:
            QMessageBox.warning(self, "Login failed", "Invalid username or password.")
            return
        self.authenticated_user = user
        self.accept()
