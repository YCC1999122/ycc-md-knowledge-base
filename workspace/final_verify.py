"""Final verification: title fix, incremental embedding on import, GUI boot."""
import os
import shutil
import sys

sys.path.insert(0, ".")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path

from app.core import db, paths, pipeline, retriever  # noqa: E402

lib = paths.LIBRARIES_DIR / paths.DEFAULT_LIBRARY
conn = db.connect(lib)

# 1. title fix: pure-semantic hit must show real title
r = retriever.search(conn, "门禁", limit=3)
print("1) 门禁 top titles:", [x["title"] for x in r])
assert r and all(x["title"] and not x["title"].startswith("20261012-") or "管理" in x["title"] for x in r)

# 2. incremental embedding on import
before = conn.execute("SELECT COUNT(*) AS c FROM embeddings").fetchone()["c"]
tmp = Path("workspace") / "tmp_test_note.md"
tmp.write_text("# 测试增量嵌入\n\n这是验证导入时自动生成语义向量的临时文档。\n\n"
               "关键词：湖畔亭台、环湖步道。\n", encoding="utf-8")
res = pipeline.import_file(lib, tmp, "测试员", "misc", conn)
conn2 = db.connect(lib)
after = conn2.execute("SELECT COUNT(*) AS c FROM embeddings").fetchone()["c"]
print(f"2) embeddings: {before} -> {after} (imported {len(res['notes'])} notes)")
assert after > before
# search the new content semantically (word not present verbatim in other notes)
hits = retriever.search(conn2, "环湖步道风景", limit=3)
print("   环湖步道风景 top:", [x["title"] for x in hits])
assert hits[0]["title"] == "测试增量嵌入", hits[0]

# 3. delete the test note (also wipes embeddings)
pipeline.delete_note(lib, res["notes"][0]["note_id"], "测试员", conn2)
after_del = conn2.execute("SELECT COUNT(*) AS c FROM embeddings").fetchone()["c"]
print(f"3) embeddings after delete: {after_del}")
assert after_del == before
conn2.close()
tmp.unlink()

conn.close()

# 4. GUI boot with new sidebar button
from PySide6.QtWidgets import QApplication
from app.gui import theme
from app.gui.main_window import MainWindow
app = QApplication([])
app.setStyleSheet(theme.QSS)
w = MainWindow()
w.show()
app.processEvents()
assert hasattr(w, "rebuild_semantic_index")
w._switch("search")
sp = w.pages["search"]
sp.input.setText("人员出入")
sp.run_search()
app.processEvents()
print("4) GUI search 人员出入 rows:", sp.table.rowCount())
w.close()
print("ALL FINAL CHECKS OK")
