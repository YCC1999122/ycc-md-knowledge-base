print("0 python ok", flush=True)
print("1 import shiboken6 ...", flush=True)
import shiboken6  # noqa: E402
print("   ok", flush=True)
print("2 import PySide6 ...", flush=True)
import PySide6  # noqa: E402
print("   ok", PySide6.__file__, flush=True)
print("3 import QtCore ...", flush=True)
from PySide6 import QtCore  # noqa: E402
print("   ok", QtCore.qVersion(), flush=True)
print("4 import QtGui ...", flush=True)
from PySide6 import QtGui  # noqa: E402
print("   ok", flush=True)
print("5 import QtWidgets ...", flush=True)
from PySide6 import QtWidgets  # noqa: E402
print("   ok", flush=True)
print("ALL-OK", flush=True)
