"""DFS load simulation: walk a bundle's DLL graph by FULL PATH, mimicking the
Windows loader, and pinpoint the exact (provider dll, missing symbol) pair."""
import ctypes
import os
import sys
from pathlib import Path

import pefile

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.LoadLibraryExW.restype = ctypes.c_void_p
k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
k32.GetProcAddress.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008

VISITED = set()
BUNDLE = None
PYTHON_DIR = Path(sys.executable).resolve().parent
SYS32 = Path(os.environ["SystemRoot"]) / "System32"


def load_full(path: Path):
    h = k32.LoadLibraryExW(str(path), None, LOAD_WITH_ALTERED_SEARCH_PATH)
    if not h:
        e = ctypes.get_last_error()
        return None, e
    return h, 0


def imports_of(path: Path):
    """Merge ALL import descriptors (duplicate DLL names possible)."""
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    merged = {}
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        name = entry.dll.decode().lower()
        syms = [i.name.decode() for i in entry.imports if i.name]
        merged.setdefault(name, []).extend(syms)
    return merged


def find_provider(name: str, importer_dir: Path):
    """Simulate search: importer dir, bundle root, PySide6, shiboken6, python dir, System32."""
    for d in (importer_dir, BUNDLE, BUNDLE / "PySide6", BUNDLE / "shiboken6",
              PYTHON_DIR, SYS32):
        c = d / name
        if c.exists():
            return c
    return None


def dfs(path: Path, depth=0):
    key = path.name.lower()
    if key in VISITED or path.parent == SYS32:
        return          # do not recurse into system DLLs (apiset noise)
    VISITED.add(key)
    pad = "  " * depth
    try:
        imps = imports_of(path)
    except Exception as e:  # noqa: BLE001
        print(f"{pad}[!] cannot parse {path.name}: {e}")
        return
    for dep_name, syms in imps.items():
        prov = find_provider(dep_name, path.parent)
        if prov is None:
            # apisets resolve virtually (kernelbase/combase/ucrtbase) — skip
            if dep_name.startswith("api-ms-"):
                continue
            print(f"{pad}MISSING-FILE {path.name} -> {dep_name}")
            continue
        if prov.parent == SYS32 and dep_name.startswith("api-ms-"):
            continue
        h, err = load_full(prov)
        if not h:
            print(f"{pad}LOAD-FAIL {path.name} -> {prov}  WinError {err}")
            dfs(prov, depth + 1)
            continue
        missing = [s for s in syms if not k32.GetProcAddress(h, s.encode())]
        if missing:
            print(f"{pad}SYMBOL-GAP {path.name} -> {prov}")
            print(f"{pad}  imported {len(syms)}, missing {len(missing)} (first 6):")
            for s in missing[:6]:
                print(f"{pad}    - {s}")
        dfs(prov, depth + 1)


def main(bundle: str, target: str):
    global BUNDLE
    BUNDLE = Path(bundle).resolve()
    t = None
    for cand in (BUNDLE / target, BUNDLE / "PySide6" / target,
                 BUNDLE / "shiboken6" / target):
        if cand.exists():
            t = cand
            break
    if t is None:
        print(f"target not found: {target}")
        return
    h, err = load_full(t)
    print(f"LOAD {t.name}: {'OK' if h else f'FAIL WinError {err}'}")
    dfs(t)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
