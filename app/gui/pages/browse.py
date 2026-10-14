"""Browse page: category tree | notes | content (view / edit / classify / move / delete).

Categories are fully user-defined: any depth, created / renamed / deleted here;
paths are slash-joined slugs stored in the categories table.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QStackedWidget, QTextBrowser, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ...core import db, kb, pipeline
from ..widgets import hbox, make_panel, page_header


class NewNoteDialog(QDialog):
    def __init__(self, parent, entries: list[tuple[str, str]]):
        """entries: (indented display text, category path)"""
        super().__init__(parent)
        self.setWindowTitle("新建笔记")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("例如：设备巡检注意事项")
        form.addRow("标题", self.title_edit)
        self.topic_combo = QComboBox()
        self.topic_combo.setEditable(True)
        for text, path in entries:
            self.topic_combo.addItem(text, path)
        form.addRow("分类", self.topic_combo)
        lay.addLayout(form)
        hint = QLabel("内容以 Markdown 编写，首个 # 标题将作为笔记标题。\n"
                      "分类可输入新路径，用 / 分层（如 gong-si/cai-wu），层级会自动创建。")
        hint.setObjectName("muted")
        lay.addWidget(hint)
        self.content_edit = QPlainTextEdit()
        self.content_edit.setMinimumHeight(220)
        lay.addWidget(self.content_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def values(self) -> tuple[str, str, str]:
        title = self.title_edit.text().strip()
        idx = self.topic_combo.currentIndex()
        if idx >= 0 and self.topic_combo.currentText() == self.topic_combo.itemText(idx):
            topic = self.topic_combo.itemData(idx)
        else:
            topic = self.topic_combo.currentText().strip()
        content = self.content_edit.toPlainText().strip() or f"# {title}\n\n"
        return title, topic, content


class BrowsePage(QWidget):
    def __init__(self, lib: Path, mw):
        super().__init__()
        self.lib, self.mw = lib, mw
        self.current_note: dict | None = None
        self.editing = False
        self._cats: dict[str, str] = {}            # path -> display name
        self._cat_items: dict[str, QTreeWidgetItem] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        root.addWidget(page_header("知识库浏览", "分类层级可自定义：新建、重命名、删除，所有操作均记录变更"))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        # ---- left: category tree ----
        left, left_lay = make_panel("分类")
        left.setMinimumWidth(200)
        left.setMaximumWidth(280)
        self.topic_tree = QTreeWidget()
        self.topic_tree.setHeaderHidden(True)
        self.topic_tree.currentItemChanged.connect(self._on_topic)
        left_lay.addWidget(self.topic_tree)
        btn_new_cat = QPushButton("新建分类")
        btn_new_cat.setToolTip("在选中分类下新建子分类；未选中则建顶级分类")
        btn_new_cat.clicked.connect(self.new_category)
        left_lay.addWidget(btn_new_cat)
        btn_ren_cat = QPushButton("重命名")
        btn_ren_cat.clicked.connect(self.rename_category)
        left_lay.addWidget(btn_ren_cat)
        btn_del_cat = QPushButton("删除分类")
        btn_del_cat.setObjectName("danger")
        btn_del_cat.setToolTip("仅可删除没有笔记、没有子分类的分类")
        btn_del_cat.clicked.connect(self.delete_category)
        left_lay.addWidget(btn_del_cat)
        splitter.addWidget(left)

        # ---- middle: notes ----
        mid, mid_lay = make_panel("笔记")
        mid.setMinimumWidth(220)
        mid.setMaximumWidth(320)
        self.note_list = QListWidget()
        self.note_list.currentRowChanged.connect(self._on_note)
        mid_lay.addWidget(self.note_list)
        btns = hbox(6)
        self.btn_new = QPushButton("新建")
        self.btn_new.clicked.connect(self.new_note)
        self.btn_move = QPushButton("移动")
        self.btn_move.setToolTip("移动到其他分类")
        self.btn_move.clicked.connect(self.move_note)
        self.btn_del = QPushButton("删除")
        self.btn_del.setObjectName("danger")
        self.btn_del.clicked.connect(self.delete_note)
        for b in (self.btn_new, self.btn_move, self.btn_del):
            btns.addWidget(b)
        mid_lay.addLayout(btns)
        splitter.addWidget(mid)

        # ---- right: content ----
        right, right_lay = make_panel()
        self.title_label = QLabel("（请选择笔记）")
        self.title_label.setObjectName("panelTitle")
        right_lay.addWidget(self.title_label)
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("muted")
        self.meta_label.setWordWrap(True)
        right_lay.addWidget(self.meta_label)

        # toolbar: view/edit + classification
        bar = hbox(6)
        self.btn_edit = QPushButton("编辑")
        self.btn_edit.clicked.connect(self.start_edit)
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self.save_edit)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.cancel_edit)
        bar.addWidget(self.btn_edit)
        bar.addWidget(self.btn_save)
        bar.addWidget(self.btn_cancel)
        bar.addSpacing(14)
        bar.addWidget(QLabel("状态"))
        self.status_combo = QComboBox()
        for key, label in kb.STATUSES.items():
            self.status_combo.addItem(label, key)
        bar.addWidget(self.status_combo)
        bar.addWidget(QLabel("标签"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setMaximumWidth(180)
        self.tags_edit.setPlaceholderText("逗号分隔")
        bar.addWidget(self.tags_edit)
        self.btn_classify = QPushButton("应用分类")
        self.btn_classify.clicked.connect(self.apply_classification)
        bar.addWidget(self.btn_classify)
        bar.addStretch()
        right_lay.addLayout(bar)

        self.stack = QStackedWidget()
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(False)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("# 标题\n\n在此编写 Markdown 内容…")
        self.stack.addWidget(self.viewer)
        self.stack.addWidget(self.editor)
        right_lay.addWidget(self.stack, 1)
        splitter.addWidget(right)

        splitter.setSizes([220, 260, 620])
        self._set_editing(False)
        self._update_buttons()

    # ---------- category helpers ----------

    def _display(self, path: str) -> str:
        """Full display path: '父名 / 子名'."""
        parts = path.split("/")
        return " / ".join(
            self._cats.get("/".join(parts[: i + 1]), parts[i]) for i in range(len(parts)))

    def _cat_entries(self) -> list[tuple[str, str]]:
        """(indented display, path) for every category, parents first."""
        return [("　" * p.count("/") + self._cats[p], p) for p in sorted(self._cats)]

    def _load_categories(self) -> None:
        conn = db.connect(self.lib)
        kb.ensure_categories(conn)
        conn.commit()
        self._cats = {r["path"]: r["name"] for r in db.list_categories(conn)}
        self._counts = kb.category_counts(conn)
        conn.close()

    # ---------- data loading ----------

    def refresh(self) -> None:
        keep_topic = self._sel_topic()
        keep_note = self.current_note["note_id"] if self.current_note else None
        self._load_categories()

        self.topic_tree.blockSignals(True)
        self.topic_tree.clear()
        self._cat_items = {}
        for path in sorted(self._cats):
            it = QTreeWidgetItem([f"{self._cats[path]}（{self._counts.get(path, 0)}）"])
            it.setData(0, 32, path)
            it.setToolTip(0, f"{self._display(path)}\n路径：{path}")
            self._cat_items[path] = it
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            if parent and parent in self._cat_items:
                self._cat_items[parent].addChild(it)
            else:
                self.topic_tree.addTopLevelItem(it)
        self.topic_tree.expandAll()
        self.topic_tree.blockSignals(False)

        sel = self._cat_items.get(keep_topic) if keep_topic else None
        if sel is None and self._cat_items:
            sel = next(iter(self._cat_items.values()))
        if sel is not None:
            self.topic_tree.setCurrentItem(sel)
            self._on_topic(sel, None)
        else:
            self.note_list.clear()
            self._show_note(None)
        if keep_note:
            self._select_note(keep_note)

    def _sel_topic(self) -> str | None:
        it = self.topic_tree.currentItem()
        return it.data(0, 32) if it else None

    def _on_topic(self, item, _previous=None):
        if item is None:
            return
        topic = item.data(0, 32)
        conn = db.connect(self.lib)
        notes = conn.execute(
            "SELECT note_id, title FROM notes WHERE topic=? OR topic LIKE ? ORDER BY topic, title",
            (topic, topic + "/%")).fetchall()
        conn.close()
        self.note_list.blockSignals(True)
        self.note_list.clear()
        for n in notes:
            it = QListWidgetItem(n["title"])
            it.setData(32, n["note_id"])
            self.note_list.addItem(it)
        self.note_list.blockSignals(False)
        if self.note_list.count():
            self.note_list.setCurrentRow(0)
        else:
            self._show_note(None)

    def _on_note(self, row: int):
        if row < 0:
            return
        note_id = self.note_list.item(row).data(32)
        conn = db.connect(self.lib)
        r = conn.execute("SELECT * FROM notes WHERE note_id=?", (note_id,)).fetchone()
        conn.close()
        if r:
            note = dict(r)
            note["tags"] = json.loads(note["tags"] or "[]")
            self._show_note(note)

    def _select_note(self, note_id: str):
        for i in range(self.note_list.count()):
            if self.note_list.item(i).data(32) == note_id:
                self.note_list.setCurrentRow(i)
                return

    def focus_note(self, note_id: str):
        """Jump here from the search page."""
        conn = db.connect(self.lib)
        r = conn.execute("SELECT topic FROM notes WHERE note_id=?", (note_id,)).fetchone()
        conn.close()
        if not r:
            return
        it = self._cat_items.get(r["topic"])
        if it is not None:
            self.topic_tree.setCurrentItem(it)
        self._select_note(note_id)

    # ---------- view / edit ----------

    def _show_note(self, note: dict | None):
        self.current_note = note
        self._set_editing(False)
        if not note:
            self.title_label.setText("（请选择笔记）")
            self.meta_label.setText("")
            self.viewer.clear()
            self.editor.clear()
        else:
            self.title_label.setText(note["title"])
            self.meta_label.setText(
                f"ID：{note['note_id']}    分类：{self._display(note['topic'])}    "
                f"更新：{note['updated']}    操作人：{note['updated_by'] or '-'}    "
                f"来源：{note['source_path'] or '手工创建'}")
            self.status_combo.setCurrentIndex(list(kb.STATUSES).index(note["status"]))
            self.tags_edit.setText(", ".join(note["tags"]))
            # render markdown; resolve ../../assets/... against the note file
            note_file = self.lib / note["rel_path"]
            self.viewer.document().setBaseUrl(QUrl.fromLocalFile(str(note_file)))
            self.viewer.setMarkdown(note["content"])
            self.editor.setPlainText(note["content"])
        self._update_buttons()

    def _set_editing(self, on: bool):
        self.editing = on
        self.stack.setCurrentWidget(self.editor if on else self.viewer)

    def _update_buttons(self):
        has = self.current_note is not None
        self.btn_edit.setVisible(has and not self.editing)
        self.btn_save.setVisible(has and self.editing)
        self.btn_cancel.setVisible(has and self.editing)
        for b in (self.btn_move, self.btn_del, self.btn_classify):
            b.setEnabled(has and not self.editing)
        for w in (self.status_combo, self.tags_edit):
            w.setEnabled(has and not self.editing)

    def start_edit(self):
        if self.current_note:
            self._set_editing(True)
            self._update_buttons()
            self.editor.setFocus()

    def save_edit(self):
        note = self.current_note
        content = self.editor.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "保存", "内容不能为空。")
            return
        try:
            updated = pipeline.update_note(self.lib, note["note_id"],
                                           self.mw.current_operator(), content=content)
            updated["tags"] = json.loads(updated["tags"] or "[]") if isinstance(updated["tags"], str) else updated["tags"]
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self.mw.refresh_all(keep=("browse",))
        self._show_note(updated)
        self._reload_lists(updated["note_id"])

    def cancel_edit(self):
        if self.current_note:
            self.editor.setPlainText(self.current_note["content"])
        self._set_editing(False)
        self._update_buttons()

    # ---------- category mutations ----------

    def new_category(self):
        parent = self._sel_topic() or ""
        hint = f"在「{self._display(parent)}」下" if parent else "在顶级"
        name, ok = QInputDialog.getText(self, "新建分类", f"{hint}新建分类，输入名称：")
        name = name.strip()
        if not ok or not name:
            return
        try:
            path = pipeline.create_category(self.lib, parent, name, self.mw.current_operator())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "新建分类失败", str(e))
            return
        self.mw.refresh_all(keep=("browse",))
        self.refresh()
        if path in self._cat_items:
            self.topic_tree.setCurrentItem(self._cat_items[path])

    def rename_category(self):
        path = self._sel_topic()
        if not path:
            return
        old_name = self._cats.get(path, path)
        new, ok = QInputDialog.getText(
            self, "重命名分类",
            f"将分类「{old_name}」（{path}）重命名为：", text=old_name)
        new = new.strip()
        if not ok or not new or new == old_name:
            return
        try:
            pipeline.rename_category(self.lib, path, new, self.mw.current_operator())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "重命名失败", str(e))
            return
        self.mw.refresh_all()

    def delete_category(self):
        path = self._sel_topic()
        if not path:
            return
        if QMessageBox.question(
                self, "删除分类",
                f"确定删除分类「{self._display(path)}」（{path}）？\n"
                "仅可删除没有笔记、没有子分类的分类；删除动作会记录在变更记录中。") \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            pipeline.delete_category(self.lib, path, self.mw.current_operator())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "删除分类失败", str(e))
            return
        self.mw.refresh_all()

    # ---------- note mutations ----------

    def new_note(self):
        entries = self._cat_entries()
        if not entries:
            QMessageBox.warning(self, "新建笔记", "请先新建一个分类。")
            return
        dlg = NewNoteDialog(self, entries)
        sel = self._sel_topic()
        if sel:
            idx = next((i for i, (_, p) in enumerate(entries) if p == sel), 0)
            dlg.topic_combo.setCurrentIndex(idx)
        if not dlg.exec():
            return
        title, topic, content = dlg.values()
        if not title:
            QMessageBox.warning(self, "新建笔记", "标题不能为空。")
            return
        if not topic:
            QMessageBox.warning(self, "新建笔记", "分类不能为空。")
            return
        try:
            note = pipeline.create_note(self.lib, self.mw.current_operator(),
                                        title, content, topic)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "新建失败", str(e))
            return
        self.mw.refresh_all(keep=("browse",))
        self.refresh()
        self.focus_note(note["note_id"])

    def delete_note(self):
        note = self.current_note
        if not note:
            return
        if QMessageBox.question(
                self, "删除笔记",
                f"确定删除笔记「{note['title']}」？\n删除动作会记录在变更记录中（含删除前内容）。") \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            pipeline.delete_note(self.lib, note["note_id"], self.mw.current_operator())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "删除失败", str(e))
            return
        self.current_note = None
        self.mw.refresh_all()

    def move_note(self):
        note = self.current_note
        if not note:
            return
        entries = self._cat_entries()
        items = [t for t, _ in entries]
        cur = next((i for i, (_, p) in enumerate(entries) if p == note["topic"]), 0)
        text, ok = QInputDialog.getItem(
            self, "移动分类", "选择目标分类（可输入新路径，用 / 分层）：", items, cur, True)
        if not ok or not text.strip():
            return
        mapping = dict(entries)
        target = mapping.get(text, text.strip())
        if target == note["topic"]:
            return
        try:
            pipeline.update_note(self.lib, note["note_id"], self.mw.current_operator(), topic=target)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "移动失败", str(e))
            return
        self.mw.refresh_all()

    def apply_classification(self):
        note = self.current_note
        if not note:
            return
        tags = [t.strip() for t in self.tags_edit.text().replace("，", ",").split(",") if t.strip()]
        try:
            pipeline.update_note(
                self.lib, note["note_id"], self.mw.current_operator(),
                tags=tags or [note["topic"]],
                status=self.status_combo.currentData())
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "分类失败", str(e))
            return
        self.mw.refresh_all()

    def _reload_lists(self, note_id: str):
        """Refresh left/middle columns after an in-place save."""
        self.refresh()
        self.focus_note(note_id)
