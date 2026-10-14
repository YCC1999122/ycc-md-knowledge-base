"""Management database: documents / notes / chunks / change logs / operators.

One SQLite database per library, stored at <library>/index/kb.db.
Full-text search uses SQLite FTS5 with the trigram tokenizer (works for Chinese).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA_TABLES = """
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS operators(
  op_id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  role TEXT DEFAULT '编辑',
  created TEXT,
  active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS documents(
  doc_id TEXT PRIMARY KEY,
  filename TEXT,
  stored_path TEXT,
  ext TEXT,
  size INTEGER,
  sha256 TEXT,
  imported_by TEXT,
  imported_at TEXT,
  status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS notes(
  note_id TEXT PRIMARY KEY,
  title TEXT,
  topic TEXT,
  tags TEXT,
  level TEXT DEFAULT 'internal',
  status TEXT DEFAULT 'verified',
  summary TEXT,
  source_doc TEXT,
  source_path TEXT,
  rel_path TEXT,
  content TEXT,
  created TEXT,
  updated TEXT,
  updated_by TEXT
);
CREATE TABLE IF NOT EXISTS chunks(
  chunk_id TEXT PRIMARY KEY,
  note_id TEXT,
  heading_path TEXT,
  content TEXT,
  tokens INTEGER,
  ord INTEGER
);
CREATE TABLE IF NOT EXISTS change_logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  operator TEXT,
  action TEXT,
  target_type TEXT,
  target_id TEXT,
  title TEXT,
  detail TEXT,
  before_text TEXT,
  after_text TEXT
);
CREATE TABLE IF NOT EXISTS categories(
  path TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  parent TEXT DEFAULT '',
  created TEXT
);
CREATE TABLE IF NOT EXISTS embeddings(
  chunk_id TEXT PRIMARY KEY,
  note_id TEXT,
  model TEXT,
  dim INTEGER,
  vector BLOB
);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON change_logs(ts);
CREATE INDEX IF NOT EXISTS idx_logs_target ON change_logs(target_id);
CREATE INDEX IF NOT EXISTS idx_emb_note ON embeddings(note_id);
"""

FTS_TRIGRAM = "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(note_id UNINDEXED, title, content, tokenize='trigram')"
FTS_FALLBACK = "CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(note_id UNINDEXED, title, content)"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def today_compact() -> str:
    return datetime.now().strftime("%Y%m%d")


def connect(lib_path) -> sqlite3.Connection:
    db_file = Path(lib_path) / "index" / "kb.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_TABLES)
    try:
        conn.execute(FTS_TRIGRAM)
    except sqlite3.OperationalError:
        conn.execute(FTS_FALLBACK)
    conn.commit()
    return conn


# ---------- operators ----------

def ensure_operator(conn, name: str, role: str = "编辑") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO operators(op_id, name, role, created, active) VALUES(?,?,?,?,1)",
        (f"op-{name}", name, role, now()),
    )


def list_operators(conn, include_inactive: bool = True):
    sql = "SELECT * FROM operators"
    if not include_inactive:
        sql += " WHERE active=1"
    return conn.execute(sql + " ORDER BY created").fetchall()


def set_operator_active(conn, name: str, active: bool) -> None:
    conn.execute("UPDATE operators SET active=? WHERE name=?", (1 if active else 0, name))


def current_operator(conn):
    row = conn.execute("SELECT value FROM meta WHERE key='current_operator'").fetchone()
    return row["value"] if row else None


def set_current_operator(conn, name: str) -> None:
    ensure_operator(conn, name)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('current_operator', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (name,),
    )


# ---------- categories (customizable multi-level classification tree) ----------

def ensure_category(conn, path: str, name: str, parent: str = "") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO categories(path, name, parent, created) VALUES(?,?,?,?)",
        (path, name, parent, now()),
    )


def list_categories(conn):
    return conn.execute("SELECT * FROM categories ORDER BY path").fetchall()


def get_category(conn, path: str):
    return conn.execute("SELECT * FROM categories WHERE path=?", (path,)).fetchone()


def rename_category(conn, path: str, new_name: str) -> None:
    conn.execute("UPDATE categories SET name=? WHERE path=?", (new_name, path))


def delete_category(conn, path: str) -> None:
    conn.execute("DELETE FROM categories WHERE path=?", (path,))


def move_category(conn, path: str, new_parent: str, new_path: str) -> None:
    """Re-parent a subtree: rewrite path prefix for the node and all descendants."""
    rows = conn.execute(
        "SELECT path, parent FROM categories WHERE path=? OR path LIKE ?",
        (path, path + "/%")).fetchall()
    for r in rows:
        updated = new_path + r["path"][len(path):]
        parent = new_parent if r["path"] == path else updated.rsplit("/", 1)[0]
        conn.execute("UPDATE categories SET path=?, parent=? WHERE path=?",
                     (updated, parent, r["path"]))


def category_display(conn, path: str) -> str:
    """'manual' -> '产品手册'; nested -> '父显示名 / 子显示名'."""
    names = {}
    for r in list_categories(conn):
        names[r["path"]] = r["name"]
    parts = path.split("/")
    out = []
    for i in range(len(parts)):
        seg = "/".join(parts[: i + 1])
        out.append(names.get(seg, parts[i]))
    return " / ".join(out)


# ---------- change logs ----------

def log_change(conn, operator: str, action: str, target_type: str, target_id: str,
               title: str, detail: str = "", before: str = "", after: str = "") -> None:
    """action: import / create / update / delete / move / reclassify / reimport"""
    conn.execute(
        "INSERT INTO change_logs(ts, operator, action, target_type, target_id, title, detail, before_text, after_text)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (now(), operator, action, target_type, target_id, title, detail, before, after),
    )


def list_changes(conn, operator: str = "", action: str = "", keyword: str = "", limit: int = 500):
    sql, args = "SELECT * FROM change_logs WHERE 1=1", []
    if operator:
        sql += " AND operator=?"; args.append(operator)
    if action:
        sql += " AND action=?"; args.append(action)
    if keyword:
        sql += " AND (title LIKE ? OR target_id LIKE ? OR detail LIKE ?)"
        args += [f"%{keyword}%"] * 3
    sql += " ORDER BY id DESC LIMIT ?"; args.append(limit)
    return conn.execute(sql, args).fetchall()


# ---------- stats ----------

def stats(conn) -> dict:
    def count(table):
        return conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
    return {
        "documents": count("documents"),
        "notes": count("notes"),
        "chunks": count("chunks"),
        "change_logs": count("change_logs"),
        "operators": count("operators"),
    }
