"""GUI self-check: login + library picker + every page to PNG (offscreen)."""
import os
import sys

sys.path.insert(0, ".")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import auth, paths  # noqa: E402
from app.gui import theme  # noqa: E402
from app.gui.library_dialog import LibraryDialog  # noqa: E402
from app.gui.login import LoginDialog  # noqa: E402
from app.gui.main_window import MainWindow  # noqa: E402

OUT = ".screenshots"
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
app.setStyleSheet(theme.QSS)

auth.ensure_default_users()
assert auth.verify("admin", "admin"), "admin/admin 登录校验失败"
assert not auth.verify("admin", "wrong"), "错误密码应被拒绝"
print("[OK] auth admin/admin")

login = LoginDialog()
login.pwd_edit.setText("admin")
login.grab().save(f"{OUT}/dlg_login.png")
print("saved dlg_login")

picker = LibraryDialog()
picker.grab().save(f"{OUT}/dlg_library.png")
print("saved dlg_library")

lib = paths.LIBRARIES_DIR / "空调知识库"
w = MainWindow(lib, "admin")
w.resize(1280, 800)
w.show()
app.processEvents()

for key in ["overview", "import", "browse", "search", "logs", "operators"]:
    w._switch(key)
    app.processEvents()
    w.grab().save(f"{OUT}/page_{key}.png")
    print("saved", key)

# switch library back to default lib through the dialog path
other = paths.LIBRARIES_DIR / paths.DEFAULT_LIBRARY
w.set_library(other)
app.processEvents()
w._switch("browse")
app.processEvents()
w.grab().save(f"{OUT}/page_browse_default.png")
print("saved browse_default (after switch)")

w.close()
print("done")
