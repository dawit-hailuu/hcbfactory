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
        title.setObjectName("pagetitle")
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        sub = QLabel("Sign in to continue")
        sub.setObjectName("hintmedium")
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
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        outer.addWidget(hint)

        outer.addStretch()
        self.password.returnPressed.connect(self._do_login)
        self.username.returnPressed.connect(self._do_login)

    def _do_login(self):
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(self, "Required", "Enter both username and password.")
            (self.username if not username else self.password).setFocus()
            return
        user = auth_service.authenticate(username, password)
        if user is None:
            QMessageBox.warning(self, "Login failed", "Invalid username or password.")
            self.password.clear()
            self.password.setFocus()
            return
        self.authenticated_user = user
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        # Focus the first empty field on open
        if not self.username.text():
            self.username.setFocus()
        else:
            self.password.setFocus()
