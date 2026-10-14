"""Full-text indexer on SQLite FTS5 (trigram tokenizer: Chinese substring search).

Semantic/vector indexing is pluggable: embedder interface reserved, default
model BGE-M3 under models/embedding (wired in when the model package exists).
"""
from __future__ import annotations

import re
import sqlite3


def index_note(conn, note_id: str, title: str, content: str) -> None:
    conn.execute("DELETE FROM notes_fts WHERE note_id=?", (note_id,))
    conn.execute("INSERT INTO notes_fts(note_id, title, content) VALUES(?,?,?)",
                 (note_id, title, content))


def remove_note(conn, note_id: str) -> None:
    conn.execute("DELETE FROM notes_fts WHERE note_id=?", (note_id,))


def search_fts(conn, query: str, limit: int = 20):
    """FTS5 trigram match needs >=3 chars per term; shorter terms fall back to LIKE."""
    terms = [t for t in re.split(r"\s+", query.strip()) if t]
    if not terms:
        return []
    if all(len(t) >= 3 for t in terms):
        match = " AND ".join('"' + t.replace('"', "") + '"' for t in terms)
        sql = ("SELECT note_id, title, snippet(notes_fts, 2, '【', '】', '…', 12) AS snip "
               "FROM notes_fts WHERE notes_fts MATCH ? ORDER BY rank LIMIT ?")
        try:
            return conn.execute(sql, (match, limit)).fetchall()
        except sqlite3.OperationalError:
            pass
    return _like_search(conn, terms, limit)


def _like_search(conn, terms: list[str], limit: int):
    cond = " AND ".join("(title LIKE ? OR content LIKE ?)" for _ in terms)
    args: list[str] = []
    for t in terms:
        args += [f"%{t}%", f"%{t}%"]
    rows = conn.execute(
        f"SELECT note_id, title, content FROM notes WHERE {cond} LIMIT ?",
        (*args, limit)).fetchall()
    results = []
    for r in rows:
        pos = r["content"].find(terms[0])
        start = max(0, pos - 40) if pos >= 0 else 0
        snip = r["content"][start:start + 140].replace("\n", " ")
        for t in terms:
            snip = snip.replace(t, f"【{t}】")
        results.append({"note_id": r["note_id"], "title": r["title"], "snip": snip})
    return results
