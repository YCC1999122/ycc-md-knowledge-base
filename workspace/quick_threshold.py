"""Quick threshold sanity check."""
import os
import sys

sys.path.insert(0, ".")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from app.core import db, paths, retriever  # noqa: E402

conn = db.connect(paths.LIBRARIES_DIR / paths.DEFAULT_LIBRARY)
for q in ["人员出入", "门禁", "设备供电", "天气"]:
    rs = retriever.search(conn, q, limit=10)
    print(f"{q}: {len(rs)} hits -> {[r['title'] for r in rs[:3]]}")
conn.close()
