"""Import & management pipeline: every mutation writes a change log with operator."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from . import chunker, db, indexer, kb, parsers


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _row_to_note(row) -> dict:
    note = dict(row)
    note["tags"] = json.loads(note["tags"] or "[]")
    note["ext"] = Path(note["source_path"] or "").suffix.lstrip(".")
    return note


# ---------------- note lifecycle ----------------

def _persist_note(lib: Path, conn, note: dict, operator: str) -> None:
    """Write note file, db row, FTS index, chunks."""
    rel = kb.write_note_file(lib, note)
    note["rel_path"] = rel
    conn.execute(
        "INSERT OR REPLACE INTO notes(note_id,title,topic,tags,status,summary,"
        "source_doc,source_path,rel_path,content,created,updated,updated_by)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (note["note_id"], note["title"], note["topic"], json.dumps(note["tags"], ensure_ascii=False),
         note["status"], note["summary"], note.get("source_doc", ""),
         note.get("source_path", ""), rel, note["content"], note["created"],
         note["updated"], operator))
    indexer.index_note(conn, note["note_id"], note["title"], note["content"])
    conn.execute("DELETE FROM chunks WHERE note_id=?", (note["note_id"],))
    chunks = chunker.chunk_note(note["note_id"], note["content"])
    for c in chunks:
        conn.execute(
            "INSERT INTO chunks(chunk_id,note_id,heading_path,content,tokens,ord) VALUES(?,?,?,?,?,?)",
            (c["chunk_id"], c["note_id"], c["heading_path"], c["content"], c["tokens"], c["ord"]))
    chunks_file = lib / "chunks" / f"{note['note_id']}.jsonl"
    chunks_file.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks) + "\n", encoding="utf-8")
    # incremental semantic embedding (silently skipped if model unavailable)
    try:
        from . import semantic
        if semantic.available():
            semantic.embed_chunks(conn, note["note_id"], note["title"], chunks)
    except Exception:  # noqa: BLE001
        pass


def _wipe_note(lib: Path, conn, note_id: str) -> None:
    row = conn.execute("SELECT rel_path FROM notes WHERE note_id=?", (note_id,)).fetchone()
    if row:
        f = lib / row["rel_path"]
        if f.exists():
            f.unlink()
    chunks_file = lib / "chunks" / f"{note_id}.jsonl"
    if chunks_file.exists():
        chunks_file.unlink()
    indexer.remove_note(conn, note_id)
    conn.execute("DELETE FROM chunks WHERE note_id=?", (note_id,))
    conn.execute("DELETE FROM notes WHERE note_id=?", (note_id,))
    try:
        from . import semantic
        semantic.remove_note(conn, note_id)
    except Exception:  # noqa: BLE001
        pass


# ---------------- import ----------------

def import_file(lib, file_path, operator: str, doc_type: str = "misc", conn=None) -> dict:
    lib = Path(lib)
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(str(src))
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        kb.ensure_categories(conn)
        doc_type = kb.ensure_category_path(conn, doc_type)  # new levels auto-created
        sha = _sha256(src)
        doc_id = "doc-" + sha[:12]
        existing = conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        reimport = existing is not None
        replaced = []
        if reimport:
            old = conn.execute(
                "SELECT note_id, title, content FROM notes WHERE source_doc=?", (doc_id,)).fetchall()
            for n in old:
                replaced.append(n["note_id"])
                db.log_change(conn, operator, "update", "note", n["note_id"], n["title"],
                              detail=f"文档重新导入，旧笔记被替换", before=n["content"])
                _wipe_note(lib, conn, n["note_id"])

        stored = lib / "sources" / f"{db.today()}_{src.name}"
        shutil.copy2(src, stored)
        parsed = parsers.parse_document(src, lib / "assets" / doc_id, doc_id)
        units = kb.split_into_units(parsed["markdown"], parsed["title"])
        source_rel = str(stored.relative_to(lib))

        notes = []
        for u in units:
            note_id = kb.unique_note_id(conn, u["title"])
            note = {
                "note_id": note_id,
                "title": u["title"],
                "topic": doc_type,
                "tags": [doc_type],
                "status": "verified",
                "summary": kb.make_summary(u["content"]),
                "source_doc": doc_id,
                "source_path": source_rel,
                "content": u["content"],
                "created": db.today(),
                "updated": db.today(),
            }
            _persist_note(lib, conn, note, operator)
            notes.append(note)
            db.log_change(conn, operator, "create" if reimport else "import", "note",
                          note_id, u["title"],
                          detail=f"来自文档 {src.name}" + ("（重新导入）" if reimport else ""),
                          after=u["content"])

        conn.execute(
            "INSERT OR REPLACE INTO documents(doc_id,filename,stored_path,ext,size,sha256,"
            "imported_by,imported_at,status) VALUES(?,?,?,?,?,?,?,?,?)",
            (doc_id, src.name, source_rel, src.suffix.lstrip("."), src.stat().st_size,
             sha, operator, db.now(), "active"))
        db.log_change(conn, operator, "reimport" if reimport else "import", "document",
                      doc_id, src.name,
                      detail=f"生成 {len(notes)} 篇笔记" + (f"，替换 {len(replaced)} 篇" if reimport else ""),
                      after="\n".join(n["note_id"] for n in notes))
        kb.rebuild_indexes(lib, conn)
        conn.commit()
        return {"doc_id": doc_id, "title": parsed["title"], "reimport": reimport,
                "replaced": replaced, "notes": notes}
    finally:
        if own:
            conn.close()


# ---------------- manual note operations (GUI) ----------------

def create_note(lib, operator: str, title: str, content: str, topic: str = "misc",
                tags=None, status: str = "draft", conn=None) -> dict:
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        kb.ensure_categories(conn)
        topic = kb.ensure_category_path(conn, topic)  # new levels auto-created
        note_id = kb.unique_note_id(conn, title)
        note = {"note_id": note_id, "title": title, "topic": topic,
                "tags": tags or [topic], "status": status,
                "summary": kb.make_summary(content), "source_doc": "",
                "source_path": "", "content": content,
                "created": db.today(), "updated": db.today()}
        _persist_note(lib, conn, note, operator)
        db.log_change(conn, operator, "create", "note", note_id, title,
                      detail=f"手工创建于主题 {topic}", after=content)
        kb.rebuild_indexes(lib, conn)
        conn.commit()
        return note
    finally:
        if own:
            conn.close()


def update_note(lib, note_id: str, operator: str, conn=None, **fields) -> dict:
    """fields: content / title / tags / topic / status / summary."""
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        row = conn.execute("SELECT * FROM notes WHERE note_id=?", (note_id,)).fetchone()
        if row is None:
            raise KeyError(f"笔记不存在: {note_id}")
        old = _row_to_note(row)
        note = dict(old)
        note.update({k: v for k, v in fields.items() if v is not None})
        if "topic" in fields and fields["topic"]:
            kb.ensure_categories(conn)
            note["topic"] = kb.ensure_category_path(conn, note["topic"])
        if "content" in fields:
            m = re.search(r"^#\s+(.+)$", note["content"], re.M)
            if m:
                note["title"] = m.group(1).strip()
            note["summary"] = kb.make_summary(note["content"])
        note["updated"] = db.today()

        action, detail = "update", "内容编辑"
        if "topic" in fields and fields["topic"] != old["topic"]:
            action, detail = "move", f"主题 {old['topic']} → {note['topic']}"
            old_file = lib / old["rel_path"]
            if old_file.exists():
                old_file.unlink()
        elif any(k in fields for k in ("tags", "status")):
            action, detail = "reclassify", (
                f"标签 {old['tags']}→{note['tags']}，状态 {old['status']}→{note['status']}")

        _persist_note(lib, conn, note, operator)
        db.log_change(conn, operator, action, "note", note_id, note["title"], detail=detail,
                      before=old["content"], after=note["content"])
        kb.rebuild_indexes(lib, conn)
        conn.commit()
        return note
    finally:
        if own:
            conn.close()


def delete_note(lib, note_id: str, operator: str, conn=None) -> None:
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        row = conn.execute("SELECT title, content FROM notes WHERE note_id=?", (note_id,)).fetchone()
        if row is None:
            raise KeyError(f"笔记不存在: {note_id}")
        db.log_change(conn, operator, "delete", "note", note_id, row["title"],
                      detail="笔记删除", before=row["content"])
        _wipe_note(lib, conn, note_id)
        kb.rebuild_indexes(lib, conn)
        conn.commit()
    finally:
        if own:
            conn.close()


# ---------------- category tree management ----------------

def clear_library(lib, operator: str, conn=None) -> dict:
    """Wipe ALL content: notes, documents, chunks, embeddings, categories,
    change logs and generated files. Operators are kept; the library itself
    (kb.yaml, index/kb.db) stays. Returns the removed counts."""
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        stats = db.stats(conn)
        n_cats = len(db.list_categories(conn))
        for table in ("notes", "documents", "chunks", "embeddings",
                      "categories", "change_logs", "notes_fts"):
            conn.execute(f"DELETE FROM {table}")
        for sub in ("topics", "sources", "assets", "chunks"):
            d = lib / sub
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
        for f in ("INDEX.md", "llms.txt"):
            p = lib / f
            if p.exists():
                p.unlink()
        db.log_change(conn, operator, "delete", "library", lib.name, lib.name,
                      detail=f"清空知识库：{stats['notes']} 篇笔记、{stats['documents']} 个文档、"
                             f"{n_cats} 个分类")
        kb.rebuild_indexes(lib, conn)
        conn.commit()
        return {"notes": stats["notes"], "documents": stats["documents"], "categories": n_cats}
    finally:
        if own:
            conn.close()


def create_category(lib, parent: str, name: str, operator: str, conn=None) -> str:
    """Create a category at any depth (parent='' for top level). Returns its path."""
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        name = name.strip()
        if not name:
            raise ValueError("分类名称不能为空")
        kb.ensure_categories(conn)
        parent = parent.strip().strip("/")
        if parent:
            parent = kb.ensure_category_path(conn, parent)
        path = kb.unique_category_path(conn, parent, name)
        db.ensure_category(conn, path, name, parent)
        (lib / "topics" / path).mkdir(parents=True, exist_ok=True)
        db.log_change(conn, operator, "create", "category", path, name,
                      detail=f"新建分类（父级：{parent or '顶级'}）")
        kb.rebuild_indexes(lib, conn)
        conn.commit()
        return path
    finally:
        if own:
            conn.close()


def rename_category(lib, path: str, new_name: str, operator: str, conn=None) -> None:
    """Rename only changes the display name; the path (and files) stay put."""
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        cat = db.get_category(conn, path)
        if cat is None:
            raise KeyError(f"分类不存在: {path}")
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("分类名称不能为空")
        db.rename_category(conn, path, new_name)
        db.log_change(conn, operator, "update", "category", path, new_name,
                      detail=f"分类重命名 {cat['name']} → {new_name}",
                      before=cat["name"], after=new_name)
        kb.rebuild_indexes(lib, conn)
        conn.commit()
    finally:
        if own:
            conn.close()


def move_category(lib, path: str, new_parent: str, operator: str, conn=None) -> str:
    """Re-parent a whole subtree; notes and files move along. Returns new path."""
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        kb.ensure_categories(conn)
        path = path.strip().strip("/")
        new_parent = new_parent.strip().strip("/")
        if new_parent == path or new_parent.startswith(path + "/"):
            raise ValueError("不能移动到自身或其子分类下")
        cat = db.get_category(conn, path)
        if cat is None:
            raise KeyError(f"分类不存在: {path}")
        if new_parent:
            new_parent = kb.ensure_category_path(conn, new_parent)
        slug = path.rsplit("/", 1)[-1]
        new_path = f"{new_parent}/{slug}" if new_parent else slug
        if new_path == path:
            return path
        if db.get_category(conn, new_path) is not None:
            raise ValueError(f"目标位置已存在同名分类: {new_path}")

        # rewrite notes in the subtree (db rows + files)
        rows = conn.execute(
            "SELECT note_id, topic, rel_path FROM notes WHERE topic=? OR topic LIKE ?",
            (path, path + "/%")).fetchall()
        for r in rows:
            new_topic = new_path + r["topic"][len(path):]
            conn.execute("UPDATE notes SET topic=?, updated=?, updated_by=? WHERE note_id=?",
                         (new_topic, db.today(), operator, r["note_id"]))
            old_file = lib / r["rel_path"]
            if old_file.exists():
                old_file.unlink()
            note = _row_to_note(conn.execute(
                "SELECT * FROM notes WHERE note_id=?", (r["note_id"],)).fetchone())
            rel = kb.write_note_file(lib, note)
            conn.execute("UPDATE notes SET rel_path=? WHERE note_id=?", (rel, r["note_id"]))
            db.log_change(conn, operator, "move", "note", r["note_id"], note["title"],
                          detail=f"分类移动 {path} → {new_path}")

        db.move_category(conn, path, new_parent, new_path)
        old_dir = lib / "topics" / path
        if old_dir.exists():
            shutil.rmtree(old_dir, ignore_errors=True)
        db.log_change(conn, operator, "move", "category", new_path, cat["name"],
                      detail=f"分类 {path} 移动到 {new_parent or '顶级'}")
        kb.rebuild_indexes(lib, conn)
        conn.commit()
        return new_path
    finally:
        if own:
            conn.close()


def delete_category(lib, path: str, operator: str, conn=None) -> None:
    """Only empty leaf categories can be deleted."""
    lib = Path(lib)
    own = conn is None
    conn = conn or db.connect(lib)
    try:
        path = path.strip().strip("/")
        cat = db.get_category(conn, path)
        if cat is None:
            raise KeyError(f"分类不存在: {path}")
        n_notes = conn.execute(
            "SELECT COUNT(*) AS c FROM notes WHERE topic=? OR topic LIKE ?",
            (path, path + "/%")).fetchone()["c"]
        if n_notes:
            raise ValueError(f"分类下仍有 {n_notes} 篇笔记，请先移动或删除笔记")
        children = [r for r in db.list_categories(conn) if r["path"].startswith(path + "/")]
        if children:
            raise ValueError(f"请先删除其下的 {len(children)} 个子分类")
        db.delete_category(conn, path)
        d = lib / "topics" / path
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        db.log_change(conn, operator, "delete", "category", path, cat["name"],
                      detail="分类删除")
        kb.rebuild_indexes(lib, conn)
        conn.commit()
    finally:
        if own:
            conn.close()
