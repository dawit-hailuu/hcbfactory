"""User management view (admin only)."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QDialog, QFormLayout, QLineEdit, QComboBox, QMessageBox)

from app.services import auth_service


class _NewUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New User")
        self.setMinimumWidth(380)
        f = QFormLayout(self)
        self.username = QLineEdit(); f.addRow("Username:", self.username)
        self.fullname = QLineEdit(); f.addRow("Full name:", self.fullname)
        self.role = QComboBox(); self.role.addItems(["worker","admin"]); f.addRow("Role:", self.role)
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        f.addRow("Password:", self.password)
        self.password2 = QLineEdit(); self.password2.setEchoMode(QLineEdit.Password)
        f.addRow("Confirm password:", self.password2)
        br = QHBoxLayout()
        ok = QPushButton("Create"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(ok); br.addWidget(cancel); f.addRow(br)


class _PasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.setMinimumWidth(340)
        f = QFormLayout(self)
        self.pw = QLineEdit(); self.pw.setEchoMode(QLineEdit.Password)
        f.addRow("New password:", self.pw)
        self.pw2 = QLineEdit(); self.pw2.setEchoMode(QLineEdit.Password)
        f.addRow("Confirm password:", self.pw2)
        br = QHBoxLayout()
        ok = QPushButton("Save"); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.setObjectName("secondary"); cancel.clicked.connect(self.reject)
        br.addWidget(ok); br.addWidget(cancel); f.addRow(br)


class UsersView(QWidget):
    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self._build(); self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        try: self.refresh()
        except Exception: pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)
        head = QHBoxLayout()
        t = QLabel("Users"); t.setObjectName("pagetitle")
        head.addWidget(t); head.addStretch()
        add = QPushButton("➕ New User"); add.setObjectName("success"); add.clicked.connect(self._new)
        head.addWidget(add)
        outer.addLayout(head)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Username","Full Name","Role","Created","Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        outer.addWidget(self.table)

    def refresh(self):
        users = auth_service.list_users()
        self.table.setRowCount(len(users))
        for r, u in enumerate(users):
            self.table.setItem(r, 0, QTableWidgetItem(u["username"]))
            self.table.setItem(r, 1, QTableWidgetItem(u.get("full_name") or ""))
            self.table.setItem(r, 2, QTableWidgetItem(u["role"]))
            self.table.setItem(r, 3, QTableWidgetItem(u["created_at"]))

            actions = QWidget(); h = QHBoxLayout(actions); h.setContentsMargins(0,0,0,0); h.setSpacing(4)
            pw = QPushButton("Password"); pw.clicked.connect(lambda _, uid=u["id"]: self._change_pw(uid))
            h.addWidget(pw)
            if u["id"] != self.current_user["id"]:
                rm = QPushButton("Delete"); rm.setObjectName("danger")
                rm.clicked.connect(lambda _, uid=u["id"], un=u["username"]: self._delete(uid, un))
                h.addWidget(rm)
            self.table.setCellWidget(r, 4, actions)

    def _new(self):
        dlg = _NewUserDialog(self)
        if dlg.exec_() != QDialog.Accepted: return
        username = dlg.username.text().strip()
        pw = dlg.password.text()
        pw2 = dlg.password2.text()
        if not username or not pw:
            QMessageBox.warning(self, "Required", "Username and password are required."); return
        if len(pw) < 4:
            QMessageBox.warning(self, "Password too short", "Use at least 4 characters."); return
        if pw != pw2:
            QMessageBox.warning(self, "Passwords don't match", "The two passwords must be identical."); return
        try:
            auth_service.create_user(
                username, pw,
                dlg.fullname.text().strip(), dlg.role.currentText())
            self.refresh()
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err.upper():
                QMessageBox.warning(self, "Username taken",
                                    f"A user named '{username}' already exists.")
            else:
                QMessageBox.critical(self, "Error", err)

    def _change_pw(self, uid):
        dlg = _PasswordDialog(self)
        if dlg.exec_() != QDialog.Accepted: return
        pw = dlg.pw.text(); pw2 = dlg.pw2.text()
        if not pw:
            return
        if len(pw) < 4:
            QMessageBox.warning(self, "Password too short", "Use at least 4 characters."); return
        if pw != pw2:
            QMessageBox.warning(self, "Passwords don't match", "The two passwords must be identical."); return
        auth_service.change_password(uid, pw)
        QMessageBox.information(self, "Done", "Password updated.")

    def _delete(self, uid, username):
        if QMessageBox.question(self, "Delete user",
            f"Delete user '{username}'? This cannot be undone.") != QMessageBox.Yes:
            return
        auth_service.delete_user(uid)
        self.refresh()
