"""End-to-end hybrid search test: FTS-only terms vs semantic-only terms."""
import sys

sys.path.insert(0, ".")
# HF_HUB_OFFLINE is set by cli/main entry; simulate it here too
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from app.core import db, paths, retriever  # noqa: E402

lib = paths.LIBRARIES_DIR / paths.DEFAULT_LIBRARY
conn = db.connect(lib)

n_emb = conn.execute("SELECT COUNT(*) AS c FROM embeddings").fetchone()["c"]
print(f"embeddings in db: {n_emb}")

CASES = [
    ("巡逻", "2字词：FTS trigram 匹配不了，期望语义检索命中巡护类笔记"),
    ("森林防火", "常规词：FTS+语义都应命中"),
    ("门禁", "2字词：期望语义命中出入管理"),
    ("报销流程", "未登录词：期望语义命中相关制度/财务笔记"),
]

for q, expect in CASES:
    rs = retriever.search(conn, q, limit=5)
    print(f"\n== {q}  ({expect})")
    if not rs:
        print("   (no results)")
    for r in rs[:3]:
        print(f"   {r['note_id']:<32} [{r['topic']:<7}] {r['title']}")
        snip = (r['snippet'] or '').replace('\n', ' ')[:60]
        print(f"      {snip}")

conn.close()
print("\nE2E HYBRID SEARCH OK")
