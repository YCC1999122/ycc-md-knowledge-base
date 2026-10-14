"""Operators page: manage who operates the library (audit identity)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ...core import db
from ..widgets import align, hbox, page_header, style_table

ROLES = ["管理员", "编辑", "查看"]


class AddOperatorDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("添加操作人")
        form = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("姓名，例如：赵六")
        form.addRow("姓名", self.name_edit)
        self.role_combo = QComboBox()
        self.role_combo.addItems(ROLES)
        self.role_combo.setCurrentIndex(1)
        form.addRow("角色", self.role_combo)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self) -> tuple[str, str]:
        return self.name_edit.text().strip(), self.role_combo.currentText()


class OperatorsPage(QWidget):
    def __init__(self, lib: Path, mw):
        super().__init__()
        self.lib, self.mw = lib, mw
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        root.addWidget(page_header(
            "操作人员", "所有导入、编辑、删除动作都会记录到操作人名下；当前操作人显示在左侧栏底部"))

        bar = hbox()
        btn_add = QPushButton("添加操作人")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.add_operator)
        self.btn_toggle = QPushButton("停用 / 启用")
        self.btn_toggle.clicked.connect(self.toggle_active)
        self.btn_current = QPushButton("设为当前操作人")
        self.btn_current.clicked.connect(self.set_current)
        for b in (btn_add, self.btn_toggle, self.btn_current):
            bar.addWidget(b)
        bar.addStretch()
        self.cur_label = QLabel("")
        self.cur_label.setObjectName("muted")
        bar.addWidget(self.cur_label)
        root.addLayout(bar)

        self.table = QTableWidget()
        style_table(self.table, ["姓名", "角色", "创建时间", "状态", "备注"])
        root.addWidget(self.table, 1)

    def refresh(self) -> None:
        conn = db.connect(self.lib)
        rows = db.list_operators(conn)
        current = db.current_operator(conn)
        conn.close()
        self.cur_label.setText(f"当前操作人：{current or '（未设置）'}")
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["name"]))
            self.table.setItem(i, 1, align(QTableWidgetItem(r["role"] or "-")))
            self.table.setItem(i, 2, align(QTableWidgetItem(r["created"] or "-")))
            self.table.setItem(i, 3, align(QTableWidgetItem("启用" if r["active"] else "停用")))
            self.table.setItem(i, 4, align(QTableWidgetItem("当前操作人" if r["name"] == current else "")))
        self.table.resizeColumnsToContents()

    def _selected_name(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).text()

    def add_operator(self):
        dlg = AddOperatorDialog(self)
        if not dlg.exec():
            return
        name, role = dlg.values()
        if not name:
            QMessageBox.warning(self, "添加操作人", "姓名不能为空。")
            return
        conn = db.connect(self.lib)
        db.ensure_operator(conn, name, role)
        conn.commit()
        conn.close()
        self.mw.refresh_all()

    def toggle_active(self):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "停用 / 启用", "请先选择一个操作人。")
            return
        conn = db.connect(self.lib)
        row = next((r for r in db.list_operators(conn) if r["name"] == name), None)
        if row is None:
            conn.close()
            return
        if name == db.current_operator(conn) and row["active"]:
            conn.close()
            QMessageBox.warning(self, "停用", "不能停用当前操作人，请先切换。")
            return
        db.set_operator_active(conn, name, not row["active"])
        conn.commit()
        conn.close()
        self.mw.refresh_all()

    def set_current(self):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "设为当前操作人", "请先选择一个操作人。")
            return
        conn = db.connect(self.lib)
        row = next((r for r in db.list_operators(conn) if r["name"] == name), None)
        if row and not row["active"]:
            conn.close()
            QMessageBox.warning(self, "设为当前操作人", "该操作人已停用。")
            return
        db.set_current_operator(conn, name)
        conn.commit()
        conn.close()
        self.mw.refresh_all()
