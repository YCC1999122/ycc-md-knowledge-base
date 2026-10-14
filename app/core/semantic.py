"""Local semantic embeddings via fastembed (ONNX CPU, fully offline).

Model: BAAI/bge-small-zh-v1.5 (~95 MB, 512-dim) cached under models/fastembed_cache.
- Install fastembed into runtime/packages; if missing or cache absent, the
  library silently degrades to keyword-only search (never crashes).
- App entry points (main.py / cli.py) set HF_HUB_OFFLINE=1 so runtime never
  touches the network; the model must be pre-downloaded into the cache.
"""
from __future__ import annotations

from pathlib import Path

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
# BGE zh retrieval instruction for queries (docs recommend this prefix)
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
BATCH = 32
# cosine below this is considered unrelated for bge-small-zh (related ~0.45+, noise ~0.2)
MIN_SCORE = 0.35

_model = None        # lazy singleton
_load_failed = False  # avoid retrying a broken install on every call


def model_dir() -> Path:
    from .paths import PROJECT_ROOT
    return PROJECT_ROOT / "models" / "fastembed_cache"


def available() -> bool:
    """Model cache present on disk (does not load the model)."""
    cache = model_dir()
    if not cache.exists():
        return False
    # fastembed may cache under BAAI/... or its Qdrant mirror: match either
    return any(cache.glob("models--*bge-small-zh-v1.5"))


def _get_model():
    global _model, _load_failed
    if _model is not None:
        return _model
    if _load_failed:
        return None
    try:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(model_dir()))
    except Exception:  # noqa: BLE001 - missing package/cache -> keyword-only mode
        _load_failed = True
        _model = None
    return _model


def _normalize(mat) -> "list[list[float]]":
    import numpy as np
    rows = list(mat)  # fastembed returns a generator of per-text vectors
    if not rows:
        return []
    arr = np.asarray([np.asarray(r, dtype=np.float32) for r in rows], dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    if model is None:
        return []
    return _normalize(model.embed(texts))


def embed_query(text: str) -> list[float]:
    vec = embed_texts([QUERY_PREFIX + text.strip()])
    return vec[0] if vec else []


# ---------- storage ----------

def _pack(vec: list[float]) -> bytes:
    import numpy as np
    return np.asarray(vec, dtype=np.float32).tobytes()


def embed_chunks(conn, note_id: str, title: str, chunks: list[dict]) -> int:
    """Embed a note's chunks (title + heading path + body) and replace its rows."""
    if not chunks:
        return 0
    texts = [f"{title}\n{c['heading_path']}\n{c['content']}" for c in chunks]
    vectors = embed_texts(texts)
    if not vectors or len(vectors) != len(chunks):
        return 0
    conn.execute("DELETE FROM embeddings WHERE note_id=?", (note_id,))
    for c, v in zip(chunks, vectors):
        conn.execute(
            "INSERT OR REPLACE INTO embeddings(chunk_id, note_id, model, dim, vector) VALUES(?,?,?,?,?)",
            (c["chunk_id"], note_id, MODEL_NAME, len(v), _pack(v)))
    return len(chunks)


def remove_note(conn, note_id: str) -> None:
    conn.execute("DELETE FROM embeddings WHERE note_id=?", (note_id,))


def rebuild_embeddings(lib_path, conn, progress=None) -> int:
    """Re-embed every note of the library (used by CLI `embed` and GUI button)."""
    lib_path = Path(lib_path)
    from . import chunker
    rows = conn.execute("SELECT note_id, title, content FROM notes").fetchall()
    conn.execute("DELETE FROM embeddings")
    done = 0
    for r in rows:
        chunks = chunker.chunk_note(r["note_id"], r["content"])
        done += embed_chunks(conn, r["note_id"], r["title"], chunks)
        if progress:
            progress(done)
    conn.commit()
    return done


# ---------- search ----------

def search_semantic(conn, query: str, limit: int = 20) -> list[dict]:
    """Best-matching notes by chunk cosine similarity, [{note_id, score}]."""
    import numpy as np
    q = embed_query(query)
    if not q:
        return []
    rows = conn.execute("SELECT note_id, vector FROM embeddings").fetchall()
    if not rows:
        return []
    dim = len(q)
    mat = np.frombuffer(b"".join(r["vector"] for r in rows),
                        dtype=np.float32).reshape(len(rows), dim)
    sims = mat @ np.asarray(q, dtype=np.float32)  # vectors are L2-normalized
    best: dict[str, float] = {}
    for i, r in enumerate(rows):
        s = float(sims[i])
        if s > best.get(r["note_id"], -2.0):
            best[r["note_id"]] = s
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"note_id": nid, "score": s} for nid, s in ranked if s >= MIN_SCORE]
