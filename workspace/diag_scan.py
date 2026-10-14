import ctypes
import os
from pathlib import Path

d = Path(r"d:\知识库管理工具\workspace\dist\kbdiagd2\_internal")
os.add_dll_directory(str(d))
for sub in ("PySide6", "shiboken6"):
    p = d / sub
    if p.exists():
        os.add_dll_directory(str(p))
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.LoadLibraryExW.restype = ctypes.c_void_p
k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
k32.FreeLibrary.argtypes = [ctypes.c_void_p]

files = sorted(d.glob("*.dll")) + sorted((d / "PySide6").glob("*.dll")) + \
    sorted((d / "shiboken6").glob("*.pyd") if (d / "shiboken6").exists() else [])
fail = []
for f in files:
    h = k32.LoadLibraryExW(str(f), None, 8)
    err = ctypes.get_last_error()
    if not h:
        fail.append((f.relative_to(d), err))
print(f"scanned {len(files)}, failures: {len(fail)}")
for rel, err in fail:
    print(f"  WinError {err:<4} {rel}")
