"""Real-loader bisect for QtGui.pyd: replicate frozen search context
(add_dll_directory = SetDllDirectory equivalent), load QtGui.pyd, then remove
one shadowable bundled DLL at a time to find which provider causes 127."""
import ctypes
import os
from pathlib import Path

d = Path(r"d:\知识库管理工具\workspace\dist\kbdiagd2\_internal")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.SetDllDirectoryW(str(d))          # mimic PyInstaller bootloader exactly
for sub in ("PySide6", "shiboken6"):
    p = d / sub
    if p.exists():
        os.add_dll_directory(str(p))
k32.LoadLibraryExW.restype = ctypes.c_void_p
k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
k32.FreeLibrary.argtypes = [ctypes.c_void_p]


def try_load():
    h = k32.LoadLibraryExW(str(d / "PySide6" / "QtGui.pyd"), None, 8)
    err = ctypes.get_last_error()
    if h:
        k32.FreeLibrary(h)
    return h, err


h, err = try_load()
print(f"baseline QtGui.pyd: {'OK' if h else f'FAIL WinError {err}'}")
if h:
    raise SystemExit(0)

# preload the known-good chain (like the frozen process has loaded already)
for n in ("shiboken6.abi3.dll", "python3.dll", "Qt6Core.dll", "pyside6.abi3.dll"):
    k32.LoadLibraryExW(str(d / n), None, 8)

h, err = try_load()
print(f"after preloading chain: {'OK' if h else f'FAIL WinError {err}'}")

suspects = ["MSVCP140.dll", "MSVCP140_1.dll", "MSVCP140_2.dll",
            "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
            "api-ms-win-crt-string-l1-1-0.dll", "api-ms-win-crt-heap-l1-1-0.dll",
            "api-ms-win-crt-runtime-l1-1-0.dll", "api-ms-win-crt-math-l1-1-0.dll"]
for name in suspects:
    f = d / name
    if not f.exists():
        continue
    bak = f.with_suffix(".dll.disabled")
    f.rename(bak)
    h, err = try_load()
    tag = "OK" if h else f"WinError {err}"
    print(f"without {name:<34} -> {tag}")
    bak.rename(f)

# all api-ms together
moved = []
for f in d.glob("api-ms-*.dll"):
    bak = f.with_suffix(".dll.disabled")
    f.rename(bak)
    moved.append((f, bak))
if moved:
    h, err = try_load()
    tag = "OK" if h else f"WinError {err}"
    print(f"without ALL api-ms ({len(moved)})          -> {tag}")
    for f, bak in moved:
        bak.rename(f)
