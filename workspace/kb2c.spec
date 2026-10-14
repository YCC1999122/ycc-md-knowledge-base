"""PyInstaller spec: onefile windowed exe.

Strategy: do NOT let PyInstaller dissect PySide6 (its dependency walk pulled a
bad icuuc.dll from Anaconda on PATH and re-laid-out the DLLs, breaking the
loader chain). Instead ship the working runtime\\packages\\PySide6 + shiboken6
directories VERBATIM as data and put them on sys.path via a runtime hook ?
identical to the proven source-mode environment.
"""
import os

ROOT = os.path.abspath(os.getcwd())
PKGS = os.path.join(ROOT, "runtime", "packages")
ICO = os.path.join(ROOT, "workspace", "app.ico")

datas = [
    (os.path.join(PKGS, "PySide6"), "PySide6"),
    (os.path.join(PKGS, "shiboken6"), "shiboken6"),
]

a = Analysis(
    [os.path.join(ROOT, "app", "main.py")],
    pathex=[ROOT],
    datas=datas,
    excludes=["PySide6", "shiboken6", "fastembed", "onnxruntime"],
    runtime_hooks=[os.path.join(ROOT, "workspace", "rth_local.py")],
)


def _drop(name: str) -> bool:
    n = name.lower().replace("\\", "/")
    if n.startswith(("pyside6", "shiboken6")) or "/pyside6/" in n or "/shiboken6/" in n:
        return True                       # shipped verbatim via datas instead
    if n.startswith(("api-ms-win-", "ucrtbase", "icuuc", "icuin", "icudt")):
        return True                       # OS provides these; stale copies break Qt
    return False


a.binaries = [b for b in a.binaries if not _drop(b[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="kb2c",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=ICO if os.path.exists(ICO) else None,
)
