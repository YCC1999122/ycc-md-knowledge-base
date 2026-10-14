"""Search page: full-text search over notes, double-click jumps to browse page."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ...core import db, retriever
from ..widgets import hbox, page_header, style_table


class SearchPage(QWidget):
    def __init__(self, lib: Path, mw):
        super().__init__()
        self.lib, self.mw = lib, mw
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        root.addWidget(page_header("检索", "全文检索所有笔记（中文已适配），双击结果跳转到浏览页"))

        bar = hbox()
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入关键词，例如：巡护 / 出入管理 / 故障 …")
        self.input.returnPressed.connect(self.run_search)
        bar.addWidget(self.input, 1)
        btn = QPushButton("搜索")
        btn.setObjectName("primary")
        btn.clicked.connect(self.run_search)
        bar.addWidget(btn)
        root.addLayout(bar)

        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        root.addWidget(self.hint)

        self.table = QTableWidget()
        style_table(self.table, ["标题", "主题", "匹配片段", "更新", "操作人"])
        self.table.doubleClicked.connect(self._open)
        root.addWidget(self.table, 1)

    def run_search(self):
        q = self.input.text().strip()
        if not q:
            return
        conn = db.connect(self.lib)
        results = retriever.search(conn, q, limit=50)
        conn.close()
        self.hint.setText(f"「{q}」共 {len(results)} 条结果")
        self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            t = QTableWidgetItem(r["title"])
            t.setData(32, r["note_id"])
            self.table.setItem(i, 0, t)
            self.table.setItem(i, 1, QTableWidgetItem(r["topic"]))
            snip = r["snippet"].replace("\n", " ")
            self.table.setItem(i, 2, QTableWidgetItem(snip))
            self.table.setItem(i, 3, QTableWidgetItem(r["updated"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["updated_by"] or "-"))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _open(self, index):
        row = index.row()
        item = self.table.item(row, 0)
        if item:
            self.mw.open_note(item.data(32))

    def refresh(self) -> None:
        if self.input.text().strip():
            self.run_search()
