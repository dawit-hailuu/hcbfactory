"""
Supervisor Override Dialog:
Prompts for supervisor credentials to authorize a restricted action.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QLabel, QMessageBox
from app.services import auth_service


class SupervisorOverrideDialog(QDialog):
    def __init__(self, required_permission: str, parent=None):
        super().__init__(parent)
        self.required_permission = required_permission
        self.authorized_user = None
        self.setWindowTitle("Supervisor Authorization Override")
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        icon = QLabel("⚠️")
        icon.setStyleSheet("font-size: 28px;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        msg = QLabel("The requested action requires elevated permissions.\nAsk a supervisor to input their credentials to authorize this action.")
        msg.setStyleSheet("color: #2C3E50; font-weight: bold;")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("Supervisor Username")
        form.addRow("Username:", self.username)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("••••••••")
        form.addRow("Password:", self.password)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        ok = QPushButton("Authorize Override")
        ok.setObjectName("success")
        ok.clicked.connect(self._authorize)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _authorize(self):
        username = self.username.text().strip()
        password = self.password.text()

        if not username or not password:
            QMessageBox.warning(self, "Invalid Input", "Both username and password are required.")
            return

        # Authenticate supervisor
        user = auth_service.authenticate(username, password)
        if not user:
            QMessageBox.critical(self, "Failed Override", "Incorrect username or password.")
            return

        # Check if supervisor has the necessary permission
        if not auth_service.has_permission(user["id"], self.required_permission):
            QMessageBox.warning(
                self, 
                "Unauthorized", 
                f"User '{username}' is authenticated but does not possess the '{self.required_permission}' permission."
            )
            return

        # Overridden! Save authorized user details and accept
        self.authorized_user = user
        self.accept()


def request_override(required_permission: str, parent=None) -> bool:
    """Helper function to show the dialog and return authorization outcome."""
    dlg = SupervisorOverrideDialog(required_permission, parent)
    return dlg.exec_() == QDialog.Accepted
