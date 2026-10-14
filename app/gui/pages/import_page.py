"""Import page: drag & drop / file dialog -> background parsing into the library."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from ...core import db, kb, pipeline
from ..widgets import fmt_size, hbox, make_panel, page_header, style_table

FILE_FILTER = ("办公文档 (*.docx *.xlsx *.xlsm *.csv *.pptx *.pdf *.txt *.md "
               "*.png *.jpg *.jpeg *.bmp *.gif *.webp);;所有文件 (*)")


class DropArea(QFrame):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        lay = QVBoxLayout(self)
        lay.addStretch()
        hint = QLabel("将文档拖入此处，或点击“选择文件”")
        hint.setObjectName("dropHint")
        hint.setStyleSheet(f"color:#64748b;")
        from PySide6.QtCore import Qt
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        sub = QLabel("支持 Word / Excel / CSV / PPT / PDF / 图片 / 文本，离线解析，无需联网")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)
        lay.addStretch()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if files:
            self.files_dropped.emit(files)


class ImportWorker(QThread):
    progressed = Signal(int, bool, str)          # row, ok, message
    finished_all = Signal(int, int)              # ok_count, total

    def __init__(self, lib: Path, items: list[tuple[str, str]], operator: str):
        super().__init__()
        self.lib, self.items, self.operator = lib, items, operator

    def run(self):
        ok = 0
        conn = db.connect(self.lib)
        try:
            for i, (fp, doc_type) in enumerate(self.items):
                try:
                    r = pipeline.import_file(self.lib, fp, self.operator, doc_type, conn)
                    ok += 1
                    mark = "重新导入" if r["reimport"] else "导入成功"
                    self.progressed.emit(i, True, f"{Path(fp).name}：{mark}，生成 {len(r['notes'])} 篇笔记")
                except Exception as e:  # noqa: BLE001 - surface parse errors to the user
                    self.progressed.emit(i, False, f"{Path(fp).name}：失败 - {e}")
        finally:
            conn.close()
        self.finished_all.emit(ok, len(self.items))


class ImportPage(QWidget):
    def __init__(self, lib: Path, mw):
        super().__init__()
        self.lib, self.mw = lib, mw
        self.worker: ImportWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        root.addWidget(page_header(
            "导入文档", "解析为标准化 Markdown 笔记，自动分类、建立索引并记录变更"))

        self.drop = DropArea()
        self.drop.files_dropped.connect(self.add_files)
        root.addWidget(self.drop)

        bar = hbox()
        btn_pick = QPushButton("选择文件")
        btn_pick.clicked.connect(self.pick_files)
        bar.addWidget(btn_pick)
        self.op_label = QLabel()
        self.op_label.setObjectName("muted")
        bar.addWidget(self.op_label)
        bar.addStretch()
        self.btn_import = QPushButton("开始导入")
        self.btn_import.setObjectName("primary")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self.start_import)
        bar.addWidget(self.btn_import)
        root.addLayout(bar)

        panel, lay = make_panel("待导入列表")
        self.table = QTableWidget()
        style_table(self.table, ["文件", "大小", "主题分类"], stretch_last=False)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table)
        root.addWidget(panel, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setPlaceholderText("导入结果将显示在这里")
        root.addWidget(self.log)

    # ---------- file selection ----------

    def _cat_entries(self) -> list[tuple[str, str]]:
        """(indented display, path) for every category in the tree."""
        conn = db.connect(self.lib)
        kb.ensure_categories(conn)
        conn.commit()
        rows = db.list_categories(conn)
        conn.close()
        return [("　" * r["path"].count("/") + r["name"], r["path"]) for r in rows]

    @staticmethod
    def _combo_path(combo: QComboBox) -> str:
        idx = combo.currentIndex()
        if idx >= 0 and combo.currentText() == combo.itemText(idx):
            return combo.itemData(idx)
        return combo.currentText().strip()  # typed new path: a/b/c

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择要导入的文档", "", FILE_FILTER)
        if files:
            self.add_files(files)

    def add_files(self, files: list[str]):
        entries = self._cat_entries()
        if not entries:
            QMessageBox.warning(self, "导入", "知识库暂无分类，请先在“知识库浏览”页新建分类。")
            return
        existing = {self.table.item(r, 0).data(32) for r in range(self.table.rowCount())}
        for fp in files:
            p = Path(fp)
            if not p.exists() or str(p) in existing:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(p.name)
            name_item.setData(32, str(p))          # Qt.UserRole = 32
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(fmt_size(p.stat().st_size)))
            combo = QComboBox()
            combo.setEditable(True)                # may type a new a/b/c path
            for text, path in entries:
                combo.addItem(text, path)
            combo.setCurrentIndex(0)
            self.table.setCellWidget(row, 2, combo)
        self.table.resizeColumnsToContents()
        self.btn_import.setEnabled(self.table.rowCount() > 0)

    # ---------- import ----------

    def start_import(self):
        items = []
        for r in range(self.table.rowCount()):
            fp = self.table.item(r, 0).data(32)
            doc_type = self._combo_path(self.table.cellWidget(r, 2)) or "misc"
            items.append((fp, doc_type))
        if not items:
            return
        self.btn_import.setEnabled(False)
        self.log.clear()
        operator = self.mw.current_operator()
        self.worker = ImportWorker(self.lib, items, operator)
        self.worker.progressed.connect(self._on_progress)
        self.worker.finished_all.connect(self._on_done)
        self.worker.start()

    def _on_progress(self, row: int, ok: bool, msg: str):
        self.log.appendPlainText(("✔ " if ok else "✘ ") + msg)

    def _on_done(self, ok: int, total: int):
        self.log.appendPlainText(f"完成：{ok}/{total} 个文档导入成功。")
        self.table.setRowCount(0)
        self.worker = None
        if ok:
            QMessageBox.information(self, "导入完成", f"{ok}/{total} 个文档导入成功。")
        self.mw.refresh_all()

    def refresh(self) -> None:
        self.op_label.setText(f"当前操作人：{self.mw.current_operator()}")
