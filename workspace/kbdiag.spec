"""PyInstaller spec for ???????.exe (onefile, windowed).

Key fix: the embedded runtime ships an OLD VC++ runtime (14.40); bundling it
makes Qt 6.12 DLLs fail with WinError 127 (missing newer procedures). Drop
the stale msvcp/vcruntime binaries and bundle the up-to-date ones from the
system (redistributable), which also keeps the exe working on older PCs.
"""
import os

ROOT = os.path.abspath(os.getcwd())
ICO = os.path.join(ROOT, "workspace", "app.ico")

from PyInstaller.utils.hooks import collect_all, collect_data_files  # noqa: E402

datas, binaries, hiddenimports = [], [], []
for pkg in ("fastembed", "onnxruntime"):          # semantic search runtime
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("pypinyin")            # pinyin phrase tables

a = Analysis(
    [os.path.join(ROOT, "app", "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)

# drop stale VC++ runtime picked up from the embedded python
_DROP = {"msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
         "vcruntime140.dll", "vcruntime140_1.dll"}


def _stale(name: str) -> bool:
    n = name.lower()
    return n in _DROP or n.startswith(("msvcp140-", "vcruntime140-"))


a.binaries = [b for b in a.binaries if not _stale(b[0])]

# bundle the current system VC++ runtime instead (newer, backward compatible)
_sys32 = os.path.join(os.environ["SystemRoot"], "System32")
for dll in sorted(_DROP):
    src = os.path.join(_sys32, dll)
    if os.path.exists(src):
        a.binaries.append((dll, src, "BINARY"))

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="kbdiag",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=ICO if os.path.exists(ICO) else None,
)
