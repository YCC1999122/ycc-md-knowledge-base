"""Login dialog: global accounts from config/users.json (initial admin/admin)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout,
)

from ..core import auth


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录 — 知识库管理工具")
        self.setMinimumWidth(340)
        self.username = ""

        lay = QVBoxLayout(self)
        title = QLabel("知识库管理工具")
        title.setObjectName("panelTitle")
        lay.addWidget(title)
        sub = QLabel("请使用账号登录（离线本地账号）")
        sub.setObjectName("muted")
        lay.addWidget(sub)

        form = QFormLayout()
        self.user_edit = QLineEdit("admin")
        self.pwd_edit = QLineEdit()
        self.pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_edit.setPlaceholderText("初始密码 admin")
        self.pwd_edit.returnPressed.connect(self._try_login)
        form.addRow("用户名", self.user_edit)
        form.addRow("密码", self.pwd_edit)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("登录")
        btns.accepted.connect(self._try_login)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _try_login(self):
        u = self.user_edit.text().strip()
        if auth.verify(u, self.pwd_edit.text()):
            self.username = u
            self.accept()
        else:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误。")
