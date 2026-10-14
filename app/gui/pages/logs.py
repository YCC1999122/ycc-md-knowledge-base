"""Change-log page: filterable audit trail with before/after comparison dialog."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from ...core import db
from ..widgets import hbox, make_panel, page_header, style_table

ACTIONS = {
    "import": "导入", "create": "新建", "update": "编辑", "delete": "删除",
    "move": "移动", "reclassify": "重分类", "reimport": "重新导入",
}


class DiffDialog(QDialog):
    def __init__(self, parent, title: str, before: str, after: str):
        super().__init__(parent)
        self.setWindowTitle(f"变更对比 — {title}")
        self.resize(900, 560)
        lay = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left, ll = make_panel("变更前")
        b = QPlainTextEdit()
        b.setReadOnly(True)
        b.setPlainText(before or "（无）")
        ll.addWidget(b)
        splitter.addWidget(left)

        right, rl = make_panel("变更后")
        a = QPlainTextEdit()
        a.setReadOnly(True)
        a.setPlainText(after or "（无）")
        rl.addWidget(a)
        splitter.addWidget(right)

        lay.addWidget(splitter)
        btn = QPushButton("关闭")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


class LogsPage(QWidget):
    def __init__(self, lib: Path, mw):
        super().__init__()
        self.lib, self.mw = lib, mw
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        root.addWidget(page_header("变更记录", "谁在什么时间对哪篇笔记做了什么操作，双击查看前后内容对比"))

        bar = hbox()
        bar.addWidget(QLabel("操作人"))
        self.op_combo = QComboBox()
        self.op_combo.addItem("全部", "")
        bar.addWidget(self.op_combo)
        bar.addWidget(QLabel("动作"))
        self.action_combo = QComboBox()
        self.action_combo.addItem("全部", "")
        for key, label in ACTIONS.items():
            self.action_combo.addItem(f"{key}（{label}）", key)
        bar.addWidget(self.action_combo)
        bar.addWidget(QLabel("关键词"))
        self.kw = QLineEdit()
        self.kw.setPlaceholderText("标题 / ID / 详情")
        self.kw.setMaximumWidth(220)
        self.kw.returnPressed.connect(self.refresh)
        bar.addWidget(self.kw)
        btn = QPushButton("查询")
        btn.setObjectName("primary")
        btn.clicked.connect(self.refresh)
        bar.addWidget(btn)
        bar.addStretch()
        self.count_label = QLabel("")
        self.count_label.setObjectName("muted")
        bar.addWidget(self.count_label)
        root.addLayout(bar)

        self.table = QTableWidget()
        style_table(self.table, ["时间", "操作人", "动作", "对象类型", "标题", "详情"])
        self.table.doubleClicked.connect(self._show_diff)
        root.addWidget(self.table, 1)
        self._rows = []

    def refresh(self) -> None:
        conn = db.connect(self.lib)
        # operator options
        cur_ops = [self.op_combo.itemText(i) for i in range(1, self.op_combo.count())]
        ops = [r["name"] for r in db.list_operators(conn)]
        if ops != cur_ops:
            keep = self.op_combo.currentData()
            self.op_combo.clear()
            self.op_combo.addItem("全部", "")
            for name in ops:
                self.op_combo.addItem(name, name)
            idx = self.op_combo.findData(keep)
            self.op_combo.setCurrentIndex(max(0, idx))
        self._rows = db.list_changes(
            conn,
            operator=self.op_combo.currentData() or "",
            action=self.action_combo.currentData() or "",
            keyword=self.kw.text().strip(),
            limit=500)
        conn.close()

        self.count_label.setText(f"共 {len(self._rows)} 条")
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["ts"]))
            self.table.setItem(i, 1, QTableWidgetItem(r["operator"]))
            act = ACTIONS.get(r["action"], r["action"])
            self.table.setItem(i, 2, QTableWidgetItem(f"{r['action']}（{act}）"))
            self.table.setItem(i, 3, QTableWidgetItem(r["target_type"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["title"] or r["target_id"]))
            self.table.setItem(i, 5, QTableWidgetItem(r["detail"] or ""))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _show_diff(self, index):
        r = self._rows[index.row()]
        dlg = DiffDialog(self, r["title"] or r["target_id"],
                         r["before_text"] or "", r["after_text"] or "")
        dlg.exec()
