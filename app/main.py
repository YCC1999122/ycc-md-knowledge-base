"""Application entry point: ensure library exists, launch the GUI.

Usage (from project root):
  runtime\\python\\python.exe app\\main.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# runtime must be fully offline: never let the embedding model hit the network
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# ensure project root is on sys.path for embeddable python
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtGui import QFont, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import auth, kb, paths  # noqa: E402
from app.gui import theme  # noqa: E402
from app.gui.library_dialog import LibraryDialog  # noqa: E402
from app.gui.login import LoginDialog  # noqa: E402
from app.gui.main_window import MainWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("知识库管理工具")
    app.setStyleSheet(theme.QSS)

    # window/taskbar icon
    icon_file = Path(__file__).parent / "gui" / "icon.png"
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    # set app-wide font
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    # first run: seed admin/admin and make sure at least one library exists
    auth.ensure_default_users()
    if not paths.list_libraries():
        kb.create_library(paths.LIBRARIES_DIR / paths.DEFAULT_LIBRARY,
                          paths.DEFAULT_LIBRARY, "默认知识库")

    login = LoginDialog()
    if not login.exec():
        sys.exit(0)

    picker = LibraryDialog(allow_cancel=False)
    if not picker.exec() or not picker.selected:
        sys.exit(0)

    win = MainWindow(picker.selected, login.username)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
