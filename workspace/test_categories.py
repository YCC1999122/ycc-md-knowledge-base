"""Category tree end-to-end test: create/rename/move/delete + import + old-lib seeding."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import db, kb, paths, pipeline  # noqa: E402

LIB = paths.LIBRARIES_DIR / "测试_分类树"
SAMPLE = paths.WORKSPACE_DIR / "samples" / "智能巡护系统产品手册.docx"
ok = 0


def check(label, cond):
    global ok
    assert cond, f"FAILED: {label}"
    ok += 1
    print(f"[OK] {label}")


# 0. fresh start
if LIB.exists():
    shutil.rmtree(LIB)
kb.create_library(LIB, "测试_分类树")
conn = db.connect(LIB)
check("新库种子为默认 9 个顶级分类", len(db.list_categories(conn)) == 9)

# 1. build a 3-level tree: gong-si / bu-men / cai-wu
p1 = pipeline.create_category(LIB, "", "公司", "测试员", conn)
p2 = pipeline.create_category(LIB, p1, "部门", "测试员", conn)
p3 = pipeline.create_category(LIB, p2, "财务", "测试员", conn)
check(f"三级路径 {p3}", p3 == "gong-si/bu-men/cai-wu")
check("物理目录已嵌套创建", (LIB / "topics" / p3).is_dir())

# 2. import straight into the deep path
r = pipeline.import_file(LIB, SAMPLE, "测试员", p3, conn)
check(f"导入生成 {len(r['notes'])} 篇笔记", len(r["notes"]) >= 1)
note = r["notes"][0]
check("笔记 topic 为深层路径", note["topic"] == p3)
check("笔记文件位于嵌套目录", (LIB / note["rel_path"]).exists() and p3 in note["rel_path"])

# 3. typed new path auto-creates levels on import
r2 = pipeline.import_file(LIB, paths.WORKSPACE_DIR / "samples" / "园区出入管理制度.pdf",
                          "测试员", "公司/后勤", conn)
check("中文新路径自动建层级并 slug 化", r2["notes"][0]["topic"] == "gong-si/hou-qin")
check("中间级 hou-qin 已在分类表", db.get_category(conn, "gong-si/hou-qin") is not None)

# 4. rename only changes display name
pipeline.rename_category(LIB, p3, "财务室", "测试员", conn)
check("重命名后显示名更新", db.get_category(conn, p3)["name"] == "财务室")
check("重命名不改路径", db.get_category(conn, p3) is not None)

# 5. move a whole subtree (gong-si/bu-men -> top level), notes follow
new_path = pipeline.move_category(LIB, p2, "", "测试员", conn)
check("子树移动到顶级", new_path == "bu-men")
conn2 = db.connect(LIB)
moved = conn2.execute("SELECT topic, rel_path FROM notes WHERE note_id=?",
                      (note["note_id"],)).fetchone()
check("笔记 topic 跟随子树移动", moved["topic"] == "bu-men/cai-wu")
check("笔记文件随之迁移", (LIB / moved["rel_path"]).exists())
check("旧目录已移除", not (LIB / "topics" / "gong-si" / "bu-men").exists())
conn2.close()

# 6. delete guards
try:
    pipeline.delete_category(LIB, "bu-men/cai-wu", "测试员", conn)
    raise SystemExit("应当拒绝删除有笔记的分类")
except ValueError as e:
    check(f"拒绝删除有笔记分类（{e}）", True)
try:
    pipeline.delete_category(LIB, "gong-si", "测试员", conn)
    raise SystemExit("应当拒绝删除有子分类的分类")
except ValueError as e:
    check(f"拒绝删除有子分类的分类（{e}）", True)
empty = pipeline.create_category(LIB, "", "临时空类", "测试员", conn)
pipeline.delete_category(LIB, empty, "测试员", conn)
check("空叶子分类可删除", db.get_category(conn, empty) is None
      and not (LIB / "topics" / empty).exists())

# 7. logs + index files
logs = db.list_changes(conn, limit=200)
cat_logs = [l for l in logs if l["target_type"] == "category"]
check(f"分类操作已记变更（{len(cat_logs)} 条）", len(cat_logs) >= 6)
index = (LIB / "INDEX.md").read_text(encoding="utf-8")
llms = (LIB / "llms.txt").read_text(encoding="utf-8")
check("INDEX.md 含嵌套登记簿", "  - **财务室**" in index or "- **财务室**" in index)
check("llms.txt 含树形分类链接", "topics/bu-men/cai-wu/_topic.md" in llms)
check("MOC 标题用显示名", "# 财务室（bu-men/cai-wu）"
      in (LIB / "topics" / "bu-men" / "cai-wu" / "_topic.md").read_text(encoding="utf-8"))
conn.close()

# 8. old library (notes but no categories yet) -> seed from distinct topics
OLD = paths.LIBRARIES_DIR / "默认知识库"
oconn = db.connect(OLD)
n_before = len(db.list_categories(oconn))
kb.ensure_categories(oconn)
oconn.commit()
cats_old = {r["path"] for r in db.list_categories(oconn)}
topics_old = {r["topic"] for r in oconn.execute("SELECT DISTINCT topic FROM notes")}
check(f"旧库种子（原 {n_before} → 现 {len(cats_old)}）", topics_old <= cats_old)
kb.rebuild_indexes(OLD, oconn)
oconn.commit()
check("旧库 INDEX.md 重建成功", "登记簿" in (OLD / "INDEX.md").read_text(encoding="utf-8"))
oconn.close()

# 9. cleanup
shutil.rmtree(LIB)
print(f"\n全部通过：{ok} 项检查")
