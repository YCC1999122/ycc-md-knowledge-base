"""Library picker: open / create knowledge bases.

Multiple libraries coexist (each tailored to a device / scenario); kb.yaml
carries an optional `parent` so kb-level hierarchies (e.g. a room AC base
under the room base) can build on it later.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout,
)

from ..core import db, kb, paths


class LibraryDialog(QDialog):
    def __init__(self, parent=None, allow_cancel: bool = True):
        super().__init__(parent)
        self.setWindowTitle("选择知识库")
        self.setMinimumWidth(560)
        self.setMinimumHeight(360)
        self.selected: Path | None = None

        lay = QVBoxLayout(self)
        hint = QLabel("选择需要编辑的知识库。层级即父子关系（子库挂在父库下，"
                      "如“房间·空调库”属于“房间库”）；可新建或修改父库。")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(lambda *_: self._open())
        lay.addWidget(self.tree, 1)

        btns = QHBoxLayout()
        btn_new = QPushButton("新建知识库")
        btn_new.clicked.connect(self._create)
        btns.addWidget(btn_new)
        btn_parent = QPushButton("修改父库")
        btn_parent.setToolTip("把选中的知识库挂到另一个父库下（或取消挂载）")
        btn_parent.clicked.connect(self._reparent)
        btns.addWidget(btn_parent)
        btns.addStretch()
        btn_open = QPushButton("打开")
        btn_open.setObjectName("primary")
        btn_open.clicked.connect(self._open)
        btns.addWidget(btn_open)
        if allow_cancel:
            btn_cancel = QPushButton("取消")
            btn_cancel.clicked.connect(self.reject)
            btns.addWidget(btn_cancel)
        lay.addLayout(btns)

        self._reload()

    def _note_count(self, lib: Path) -> int:
        conn = db.connect(lib)
        n = conn.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]
        conn.close()
        return n

    def _reload(self):
        keep = self.tree.currentItem().data(0, 32) if self.tree.currentItem() else None
        self.tree.clear()
        libs = paths.list_libraries()
        names = {lib.name for lib in libs}
        visited: set[str] = set()

        def add_node(parent_item, lib: Path):
            if lib.name in visited:          # cycle guard (hand-edited yaml)
                return
            visited.add(lib.name)
            meta = kb.library_meta(lib)
            text = f"{meta['name']} · {self._note_count(lib)} 篇笔记"
            if meta["description"]:
                text += f" — {meta['description']}"
            it = QTreeWidgetItem([text])
            it.setData(0, 32, str(lib))
            if parent_item is None:
                self.tree.addTopLevelItem(it)
            else:
                parent_item.addChild(it)
            for child in kb.library_children(meta["name"]):
                add_node(it, child)

        for lib in libs:  # top level = no parent or parent missing
            if kb.library_meta(lib)["parent"] not in names:
                add_node(None, lib)
        for lib in libs:  # orphans of a broken cycle still show up
            if lib.name not in visited:
                add_node(None, lib)
        self.tree.expandAll()
        target = None
        if keep:
            target = self._find_item(keep)
        if target is None and self.tree.topLevelItemCount():
            target = self.tree.topLevelItem(0)
        if target is not None:
            self.tree.setCurrentItem(target)

    def _find_item(self, key: str):
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            it = stack.pop()
            if it.data(0, 32) == key:
                return it
            stack.extend(it.child(i) for i in range(it.childCount()))
        return None

    def _open(self):
        it = self.tree.currentItem()
        if not it:
            QMessageBox.warning(self, "选择知识库", "请先选择或新建一个知识库。")
            return
        self.selected = Path(it.data(0, 32))
        self.accept()

    def _create(self):
        dlg = NewLibraryDialog(self)
        if dlg.exec() and dlg.name:
            lib = paths.LIBRARIES_DIR / dlg.name
            kb.create_library(lib, dlg.name, dlg.desc, parent=dlg.parent_name)
            self._reload()
            it = self._find_item(str(lib))
            if it is not None:
                self.tree.setCurrentItem(it)

    def _reparent(self):
        it = self.tree.currentItem()
        if not it:
            QMessageBox.warning(self, "修改父库", "请先选择一个知识库。")
            return
        lib = Path(it.data(0, 32))
        meta = kb.library_meta(lib)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"修改父库 — {meta['name']}")
        form = QFormLayout(dlg)
        combo = QComboBox()
        combo.addItem("（无 — 顶级知识库）", "")
        for other in paths.list_libraries():
            if other.name != meta["name"]:
                combo.addItem(other.name, other.name)
        combo.setCurrentIndex(combo.findData(meta["parent"]) if meta["parent"] else 0)
        form.addRow("父知识库", combo)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if not dlg.exec():
            return
        try:
            kb.set_library_parent(lib, combo.currentData())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "修改父库失败", str(e))
            return
        self._reload()


class NewLibraryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建知识库")
        self.setMinimumWidth(420)
        self.name = ""
        self.desc = ""
        self.parent_name = ""

        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：空调知识库、会议室知识库")
        form.addRow("名称", self.name_edit)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("用途：适配的设备/场景，供智能体查询的内容范围")
        form.addRow("用途描述", self.desc_edit)
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("（无 — 顶级知识库）", "")
        for lib in paths.list_libraries():
            self.parent_combo.addItem(lib.name, lib.name)
        form.addRow("父知识库", self.parent_combo)
        lay.addLayout(form)

        hint = QLabel("父知识库用于库间层级/关联登记（如“房间·空调库”挂在“房间库”下），"
                      "后续关联检索、绑定关系基于此字段扩展。")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._ok)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _ok(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "新建知识库", "名称不能为空。")
            return
        if "/" in name or "\\" in name or ":" in name:
            QMessageBox.warning(self, "新建知识库", "名称不能包含路径符号。")
            return
        if (paths.LIBRARIES_DIR / name).exists():
            QMessageBox.warning(self, "新建知识库", "同名知识库已存在。")
            return
        self.name = name
        self.desc = self.desc_edit.text().strip()
        self.parent_name = self.parent_combo.currentData()
        self.accept()
