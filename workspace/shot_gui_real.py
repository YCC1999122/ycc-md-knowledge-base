"""Real-render GUI screenshot: normal (windows) platform, timed capture then quit."""
import os
import sys

sys.path.insert(0, ".")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.gui import theme  # noqa: E402
from app.gui.main_window import MainWindow  # noqa: E402

OUT = ".screenshots"
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
app.setStyleSheet(theme.QSS)
w = MainWindow()
w.resize(1280, 800)
w.show()

shots = []


def shoot_all():
    for key in ["overview", "import", "browse", "search", "logs", "operators"]:
        w._switch(key)
        app.processEvents()
        w.grab().save(f"{OUT}/real_{key}.png")
        print("saved", key)

    sp = w.pages["search"]
    sp.input.setText("巡护")
    sp.run_search()
    w._switch("search")
    app.processEvents()
    w.grab().save(f"{OUT}/real_search_results.png")
    print("saved search_results")

    bp = w.pages["browse"]
    w._switch("browse")
    bp.refresh()
    app.processEvents()
    if bp.note_list.count():
        bp.note_list.setCurrentRow(0)
        app.processEvents()
        bp.start_edit()
        app.processEvents()
        w.grab().save(f"{OUT}/real_browse_edit.png")
        print("saved browse_edit")

    app.quit()


QTimer.singleShot(1200, shoot_all)
app.exec()
print("done")
