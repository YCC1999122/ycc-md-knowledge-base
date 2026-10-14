"""Main window: sidebar navigation + stacked pages + current operator badge."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from ..core import auth, db, kb, paths
from . import theme
from .library_dialog import LibraryDialog
from .pages import browse, import_page, logs, operators, overview, search_page

NAV_ITEMS = [
    ("概览", "overview"),
    ("导入文档", "import"),
    ("知识库浏览", "browse"),
    ("检索", "search"),
    ("变更记录", "logs"),
    ("操作人员", "operators"),
]

PAGE_CLASSES = {
    "overview": overview.OverviewPage,
    "import": import_page.ImportPage,
    "browse": browse.BrowsePage,
    "search": search_page.SearchPage,
    "logs": logs.LogsPage,
    "operators": operators.OperatorsPage,
}


class MainWindow(QMainWindow):
    def __init__(self, lib: Path, username: str):
        super().__init__()
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)
        self._username = username
        self._op = username

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        # sidebar on the left, page content on the right
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- sidebar ----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        title = QLabel("知识库管理工具")
        title.setObjectName("appTitle")
        sb.addWidget(title)
        sub = QLabel("离线 · 标准化 Markdown")
        sub.setObjectName("appSub")
        sb.addWidget(sub)

        # current library badge + switch button
        self.lib_badge = QLabel()
        self.lib_badge.setObjectName("appSub")
        self.lib_badge.setWordWrap(True)
        sb.addWidget(self.lib_badge)
        btn_switch_lib = QPushButton("切换知识库")
        btn_switch_lib.setObjectName("nav")
        btn_switch_lib.clicked.connect(self.switch_library)
        sb.addWidget(btn_switch_lib)

        # nav buttons
        self.nav_buttons: list[QPushButton] = []
        for label, key in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(lambda _, k=key: self._switch(k))
            sb.addWidget(btn)
            self.nav_buttons.append(btn)

        sb.addStretch()

        # export button
        btn_export = QPushButton("导出知识库")
        btn_export.setObjectName("nav")
        btn_export.clicked.connect(self.export_library)
        sb.addWidget(btn_export)

        # rebuild semantic index button
        btn_embed = QPushButton("重建语义索引")
        btn_embed.setObjectName("nav")
        btn_embed.clicked.connect(self.rebuild_semantic_index)
        sb.addWidget(btn_embed)

        # current operator badge
        self.op_badge = QPushButton()
        self.op_badge.setObjectName("opButton")
        self.op_badge.clicked.connect(lambda: self._switch("operators"))
        sb.addWidget(self.op_badge)

        root.addWidget(sidebar)

        # ---- content area ----
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.pages: dict[str, QWidget] = {}
        self.set_library(lib)

    # ---------- library ----------

    def set_library(self, lib: Path):
        """Open a library: (re)build all pages against it."""
        self.lib = Path(lib)
        conn = db.connect(self.lib)
        db.ensure_operator(conn, self._username, auth.role(self._username))
        db.set_current_operator(conn, self._username)
        conn.commit()
        conn.close()

        for w in self.pages.values():
            self.stack.removeWidget(w)
            w.deleteLater()
        self.pages = {key: cls(self.lib, self) for key, cls in PAGE_CLASSES.items()}
        for _, key in NAV_ITEMS:
            self.stack.addWidget(self.pages[key])

        name = kb.library_name(self.lib)
        parent = kb.library_meta(self.lib)["parent"]
        self.setWindowTitle(f"知识库管理工具 — {name}")
        self.lib_badge.setText(f"当前库：{name}" + (f"（父库：{parent}）" if parent else ""))
        self._update_op_badge()
        self.nav_buttons[0].setChecked(True)
        self._switch("overview")

    def switch_library(self):
        dlg = LibraryDialog(self)
        if dlg.exec() and dlg.selected and dlg.selected != self.lib:
            self.set_library(dlg.selected)

    # ---------- navigation ----------

    def _switch(self, key: str):
        page = self.pages.get(key)
        if not page:
            return
        # sync nav button checked state
        for i, (_, k) in enumerate(NAV_ITEMS):
            self.nav_buttons[i].setChecked(k == key)
        self.stack.setCurrentWidget(page)
        if hasattr(page, "refresh"):
            page.refresh()

    # ---------- operator ----------

    def current_operator(self) -> str:
        return self._op

    def set_current_operator(self, name: str):
        self._op = name
        self._update_op_badge()

    def _update_op_badge(self):
        self.op_badge.setText(f"当前操作人：{self._op}")

    # ---------- refresh ----------

    def refresh_all(self, keep=None):
        """Refresh all pages. If keep is a tuple of page keys, only refresh those."""
        keys = keep if keep else list(self.pages)
        for k in keys:
            page = self.pages.get(k)
            if page and hasattr(page, "refresh"):
                page.refresh()
        self._update_op_badge()

    # ---------- cross-page actions ----------

    def open_note(self, note_id: str):
        self._switch("browse")
        page: browse.BrowsePage = self.pages["browse"]
        page.focus_note(note_id)

    # ---------- export ----------

    def export_library(self):
        out = QFileDialog.getExistingDirectory(self, "选择导出目录", str(paths.EXPORTS_DIR))
        if not out:
            return
        import shutil
        src = self.lib
        dst = Path(out) / f"{src.name}_导出_{db.today_compact()}"
        try:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("index"))
            QMessageBox.information(
                self, "导出完成",
                f"知识库已导出到：\n{dst}\n\n包含笔记 Markdown、资产图片、INDEX.md 和 llms.txt。")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))

    # ---------- semantic index ----------

    def rebuild_semantic_index(self):
        from PySide6.QtCore import QThread, Signal

        class EmbedWorker(QThread):
            done = Signal(int)
            failed = Signal(str)

            def __init__(self, lib):
                super().__init__()
                self.lib = lib

            def run(self):
                try:
                    conn = db.connect(self.lib)
                    try:
                        n = semantic.rebuild_embeddings(self.lib, conn)
                    finally:
                        conn.close()
                    self.done.emit(n)
                except Exception as e:  # noqa: BLE001
                    self.failed.emit(str(e))

        from ..core import semantic
        if not semantic.available():
            QMessageBox.warning(
                self, "重建语义索引",
                "语义模型不可用：需要 fastembed 组件与模型缓存\n"
                "（runtime\\packages 中的 fastembed + models\\fastembed_cache）。\n"
                "当前仍可使用关键词检索。")
            return

        worker = EmbedWorker(self.lib)
        self._embed_worker = worker  # keep reference

        def on_done(n: int):
            self._embed_worker = None
            QMessageBox.information(self, "重建语义索引", f"完成：{n} 个知识分块已嵌入。")
            self.refresh_all()

        def on_fail(msg: str):
            self._embed_worker = None
            QMessageBox.critical(self, "重建语义索引失败", msg)

        worker.done.connect(on_done)
        worker.failed.connect(on_fail)
        worker.start()
