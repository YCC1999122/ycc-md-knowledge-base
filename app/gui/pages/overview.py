"""Overview page: library statistics + recent documents + recent changes."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QGridLayout, QLabel, QTableWidgetItem, QVBoxLayout

from ...core import db, kb
from ..widgets import align, fmt_size, hbox, make_panel, page_header, style_table
from PySide6.QtWidgets import QFrame, QHBoxLayout, QTableWidget, QWidget

STAT_DEFS = [
    ("documents", "文档"),
    ("notes", "笔记"),
    ("chunks", "知识分块"),
    ("change_logs", "变更记录"),
    ("operators", "操作人员"),
]

ACTION_LABELS = {
    "import": "导入", "create": "新建", "update": "编辑", "delete": "删除",
    "move": "移动", "reclassify": "重分类", "reimport": "重新导入",
}


class OverviewPage(QWidget):
    def __init__(self, lib: Path, mw):
        super().__init__()
        self.lib, self.mw = lib, mw
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)
        root.addWidget(page_header("概览", "知识库整体规模与最近动态"))

        # stat cards
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.stat_labels: dict[str, QLabel] = {}
        for key, label in STAT_DEFS:
            card = QFrame()
            card.setObjectName("panel")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(16, 12, 16, 12)
            num = QLabel("0")
            num.setObjectName("statNum")
            lab = QLabel(label)
            lab.setObjectName("statLabel")
            lay.addWidget(num)
            lay.addWidget(lab)
            self.stat_labels[key] = num
            cards.addWidget(card)
        root.addLayout(cards)

        # kb-level hierarchy (parent / children by kb.yaml registration)
        hier_panel, hier_lay = make_panel("知识库层级")
        self.hier_label = QLabel("")
        self.hier_label.setObjectName("muted")
        self.hier_label.setWordWrap(True)
        hier_lay.addWidget(self.hier_label)
        root.addWidget(hier_panel)

        # recent documents / recent changes
        row = hbox(12)
        doc_panel, doc_lay = make_panel("最近导入文档")
        self.doc_table = QTableWidget()
        style_table(self.doc_table, ["文件名", "类型", "大小", "导入人", "导入时间"])
        doc_lay.addWidget(self.doc_table)
        row.addWidget(doc_panel, 3)

        log_panel, log_lay = make_panel("最近变更")
        self.log_table = QTableWidget()
        style_table(self.log_table, ["时间", "操作人", "动作", "对象"])
        log_lay.addWidget(self.log_table)
        row.addWidget(log_panel, 2)
        root.addLayout(row, 1)

    def refresh(self) -> None:
        conn = db.connect(self.lib)
        s = db.stats(conn)
        for key, _ in STAT_DEFS:
            self.stat_labels[key].setText(str(s[key]))
        conn.close()

        # kb-level hierarchy: parent chain + child libraries with note counts
        meta = kb.library_meta(self.lib)
        lines = []
        if meta["parent"]:
            lines.append(f"父知识库：{meta['parent']}")
        children = kb.library_children(meta["name"])
        if children:
            subs = []
            for c in children:
                cconn = db.connect(c)
                n = cconn.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]
                cconn.close()
                cm = kb.library_meta(c)
                subs.append(f"{cm['name']}（{n} 篇" + (f"，{cm['description']}" if cm["description"] else "") + "）")
            lines.append("子知识库：" + "、".join(subs))
        self.hier_label.setText(
            "\n".join(lines) if lines
            else "独立知识库（无父库、无子库）。层级在“切换知识库”中通过新建/修改父库维护。")

        conn = db.connect(self.lib)
        docs = conn.execute(
            "SELECT filename, ext, size, imported_by, imported_at FROM documents "
            "ORDER BY imported_at DESC LIMIT 8").fetchall()
        self.doc_table.setRowCount(len(docs))
        for i, d in enumerate(docs):
            self.doc_table.setItem(i, 0, QTableWidgetItem(d["filename"]))
            self.doc_table.setItem(i, 1, align(QTableWidgetItem(d["ext"] or "-")))
            self.doc_table.setItem(i, 2, align(QTableWidgetItem(fmt_size(d["size"]))))
            self.doc_table.setItem(i, 3, align(QTableWidgetItem(d["imported_by"] or "-")))
            self.doc_table.setItem(i, 4, align(QTableWidgetItem(d["imported_at"] or "-")))
        self.doc_table.resizeColumnsToContents()

        logs = db.list_changes(conn, limit=8)
        self.log_table.setRowCount(len(logs))
        for i, r in enumerate(logs):
            self.log_table.setItem(i, 0, QTableWidgetItem(r["ts"]))
            self.log_table.setItem(i, 1, align(QTableWidgetItem(r["operator"])))
            self.log_table.setItem(i, 2, align(QTableWidgetItem(
                ACTION_LABELS.get(r["action"], r["action"]))))
            self.log_table.setItem(i, 3, QTableWidgetItem(r["title"] or r["target_id"]))
        self.log_table.resizeColumnsToContents()
        conn.close()
