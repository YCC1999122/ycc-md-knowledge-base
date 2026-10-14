"""Console ONEDIR diag build sharing kb.spec's binary filters (for probing)."""
import os

ROOT = os.path.abspath(os.getcwd())
from PyInstaller.utils.hooks import collect_all, collect_data_files  # noqa: E402

datas, binaries, hiddenimports = [], [], []
for pkg in ("fastembed", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("pypinyin")

a = Analysis(
    [os.path.join(ROOT, "app", "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)

_DROP = {"msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
         "vcruntime140.dll", "vcruntime140_1.dll"}


def _stale(name: str) -> bool:
    n = name.lower()
    return n in _DROP or n.startswith(("msvcp140-", "vcruntime140-"))


a.binaries = [b for b in a.binaries if not _stale(b[0])]
_sys32 = os.path.join(os.environ["SystemRoot"], "System32")
for dll in sorted(_DROP):
    src = os.path.join(_sys32, dll)
    if os.path.exists(src):
        a.binaries.append((dll, src, "BINARY"))

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="kbdiagd2",
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="kbdiagd2",
)
