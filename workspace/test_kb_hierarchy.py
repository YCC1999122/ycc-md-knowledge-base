"""Verify kb-level hierarchy: demo child lib -> tree/overview screenshots -> cleanup."""
import os
import shutil
import sys

sys.path.insert(0, ".")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import kb, paths  # noqa: E402
from app.gui import theme  # noqa: E402
from app.gui.library_dialog import LibraryDialog  # noqa: E402
from app.gui.main_window import MainWindow  # noqa: E402

OUT = ".screenshots"
os.makedirs(OUT, exist_ok=True)

DEMO = paths.LIBRARIES_DIR / "演示_房间空调子库"
if DEMO.exists():
    shutil.rmtree(DEMO)

# build a demo child under 空调知识库 (user's 空调遥控器 child stays untouched)
kb.create_library(DEMO, "演示_房间空调子库", "某房间空调实例（演示父子层级）",
                  parent="空调知识库")
children = [p.name for p in kb.library_children("空调知识库")]
assert "演示_房间空调子库" in children and "空调遥控器" in children, children
# cycle guard: making 空调知识库 a child of its own child must fail
try:
    kb.set_library_parent(paths.LIBRARIES_DIR / "空调知识库", "演示_房间空调子库")
    raise SystemExit("应当拒绝循环父子")
except ValueError as e:
    print(f"[OK] 循环检测：{e}")

app = QApplication([])
app.setStyleSheet(theme.QSS)

picker = LibraryDialog()
picker.grab().save(f"{OUT}/dlg_library_tree.png")
print("saved dlg_library_tree")

w = MainWindow(paths.LIBRARIES_DIR / "空调知识库", "admin")
w.resize(1280, 800)
w.show()
app.processEvents()
w.grab().save(f"{OUT}/page_overview_hier.png")
print("saved page_overview_hier (空调知识库, 含两个子库)")
w.set_library(DEMO)
app.processEvents()
w._switch("overview")
app.processEvents()
w.grab().save(f"{OUT}/page_overview_child.png")
print("saved page_overview_child (子库, has parent)")
w.close()

# cleanup: remove only the demo child; user's libraries keep their parents
shutil.rmtree(DEMO)
print("done, 演示子库已清理（空调遥控器等用户数据保留）")
