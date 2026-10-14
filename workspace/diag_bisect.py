"""Loader bisect: for each suspicious bundled DLL, rename it away and try
loading Qt6Core.dll; observe how the error changes (127 vs 126 vs OK)."""
import ctypes
import os
import sys
from pathlib import Path

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.LoadLibraryExW.restype = ctypes.c_void_p
k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
k32.FreeLibrary.argtypes = [ctypes.c_void_p]
LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008


def try_load_qt6core(bundle: Path):
    h = k32.LoadLibraryExW(str(bundle / "Qt6Core.dll"), None,
                           LOAD_WITH_ALTERED_SEARCH_PATH)
    err = ctypes.get_last_error()
    if h:
        k32.FreeLibrary(h)
    return h, err


def main(bundle: str):
    d = Path(bundle).resolve()
    os.add_dll_directory(str(d))
    suspects = ["icuuc.dll", "MSVCP140.dll", "MSVCP140_1.dll", "MSVCP140_2.dll",
                "VCRUNTIME140.dll", "VCRUNTIME140_1.dll", "python3.dll",
                "python311.dll", "shiboken6.abi3.dll", "pyside6.abi3.dll"]
    h, err = try_load_qt6core(d)
    print(f"baseline Qt6Core: {'OK' if h else f'FAIL WinError {err}'}")
    if h:
        return

    for name in suspects:
        f = d / name
        if not f.exists():
            continue
        bak = f.with_suffix(".dll.disabled")
        f.rename(bak)
        h, err = try_load_qt6core(d)
        tag = "OK" if h else f"WinError {err}"
        print(f"without {name:<22} -> {tag}")
        bak.rename(f)

    # also: disable ALL api-ms forwarder files at once
    apims = list(d.glob("api-ms-*.dll"))
    moved = []
    for f in apims:
        bak = f.with_suffix(".dll.disabled")
        f.rename(bak)
        moved.append((f, bak))
    if moved:
        h, err = try_load_qt6core(d)
        tag = "OK" if h else f"WinError {err}"
        print(f"without ALL api-ms-*.dll ({len(moved)} files) -> {tag}")
        for f, bak in moved:
            bak.rename(f)


if __name__ == "__main__":
    main(sys.argv[1])
