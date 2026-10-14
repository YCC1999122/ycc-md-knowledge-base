"""Diagnose WinError 127: walk a DLL's import table, try loading each import,
and pinpoint the missing export / the provider that got picked."""
import ctypes
import os
import sys
from pathlib import Path

import pefile

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]


def module_file(handle):
    buf = ctypes.create_unicode_buffer(512)
    k32.GetModuleFileNameW(ctypes.c_void_p(handle), buf, 512)
    return buf.value


def imports_of(path: Path) -> dict[str, list[str]]:
    """dll name -> list of imported symbols."""
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    out = {}
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        name = entry.dll.decode().lower()
        out[name] = [i.name.decode() for i in entry.imports if i.name]
    return out


def try_load(name: str):
    """ctypes-load by name in current search context; returns (ok, path, err)."""
    try:
        h = ctypes.WinDLL(name)
        return True, module_file(h._handle), ""
    except OSError as e:
        return False, "", str(e)


def missing_symbols(importer: Path, provider_name: str, candidates: list[str]):
    """Which imported symbols of `importer` (from provider_name) are absent
    from every candidate provider file?"""
    want = imports_of(importer).get(provider_name, [])
    if not want:
        return want, set(), None
    have = set()
    used = None
    for c in candidates:
        if c and Path(c).exists():
            pe = pefile.PE(c, fast_load=True)
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
            exp = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
            if exp:
                have = {s.name.decode() for s in exp.symbols if s.name}
                used = c
                break
    return want, {s for s in want if s not in have}, used


def main(internal: str, target: str):
    d = Path(internal).resolve()             # frozen _internal dir (absolute)
    os.add_dll_directory(str(d))
    for sub in ("PySide6", "shiboken6"):
        p = d / sub
        if p.exists():
            os.add_dll_directory(str(p))
    os.chdir(d)

    target_path = None
    for cand in (d / target, d / "PySide6" / target, d / "shiboken6" / target):
        if cand.exists():
            target_path = cand
            break
    if target_path is None:
        print(f"target not found in bundle: {target}")
        return
    print(f"=== imports of {target_path.name} ===")
    ok_all = True
    for name in imports_of(target_path):
        ok, path, err = try_load(name)
        if ok:
            print(f"  OK   {name:<42} <- {path}")
        else:
            ok_all = False
            print(f"  FAIL {name:<42} {err}")
            # candidates in search order: exe dir, bundle dirs, system32
            sys32 = Path(os.environ["SystemRoot"]) / "System32" / name
            cands = [Path(name), d / name, d / "PySide6" / name,
                     d / "shiboken6" / name, sys32]
            want, missing, used = missing_symbols(target_path, name, cands)
            if missing is not None:
                print(f"       provider used: {used}")
                print(f"       imported {len(want)}, missing {len(missing)}:")
                for s in sorted(missing)[:12]:
                    print(f"         - {s}")
    print("ALL-OK" if ok_all else "BROKEN")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
