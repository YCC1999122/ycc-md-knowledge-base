"""Hybrid retriever: FTS5 keyword + local semantic vectors, fused by RRF.

Degrades gracefully: no fastembed/model cache -> keyword-only search.
"""
from __future__ import annotations

from . import indexer

_RRF_K = 60


def _safe_semantic(conn, query: str, limit: int) -> list[dict]:
    try:
        from . import semantic
        if not semantic.available():
            return []
        return semantic.search_semantic(conn, query, limit)
    except Exception:  # noqa: BLE001 - never let semantic issues break search
        return []


def search(conn, query: str, limit: int = 20) -> list[dict]:
    hits = indexer.search_fts(conn, query, limit * 2)
    sem = _safe_semantic(conn, query, limit * 2)

    # Reciprocal Rank Fusion over both ranked lists
    rrf: dict[str, float] = {}
    for rank, h in enumerate(hits):
        rrf[h["note_id"]] = rrf.get(h["note_id"], 0.0) + 1.0 / (_RRF_K + rank)
    for rank, s in enumerate(sem):
        rrf[s["note_id"]] = rrf.get(s["note_id"], 0.0) + 1.0 / (_RRF_K + rank)

    order = sorted(rrf, key=lambda nid: rrf[nid], reverse=True)[:limit]
    results = []
    for note_id in order:
        note = conn.execute(
            "SELECT title, topic, summary, status, updated, updated_by FROM notes WHERE note_id=?",
            (note_id,)).fetchone()
        if note is None:
            continue
        fts_hit = next((h for h in hits if h["note_id"] == note_id), None)
        results.append({
            "note_id": note_id,
            "title": fts_hit["title"] if fts_hit else note["title"],
            "snippet": fts_hit["snip"] if fts_hit else (note["summary"] or ""),
            "topic": note["topic"],
            "summary": note["summary"],
            "status": note["status"],
            "updated": note["updated"],
            "updated_by": note["updated_by"],
        })
    return results
