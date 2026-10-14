"""Manual PE import-directory parser (no pefile): list QtGui.pyd/Qt6Gui.dll
deps and check where each can be found."""
import ctypes
import os
import struct
import sys
from pathlib import Path

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


def read_imports(path: Path):
    data = path.read_bytes()
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe_off:pe_off + 4] == b"PE\0\0"
    coff = pe_off + 4
    num_sections = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    ddir = opt + (0x70 if magic == 0x20B else 0x60)  # data directories offset
    import_rva = struct.unpack_from("<I", data, ddir + 8)[0]
    if not import_rva:
        return []
    sec_off = opt + opt_size
    sections = []
    for i in range(num_sections):
        s = sec_off + i * 40
        va, vsz = struct.unpack_from("<I", data, s + 12)[0], struct.unpack_from("<I", data, s + 8)[0]
        raw, rsz = struct.unpack_from("<I", data, s + 20)[0], struct.unpack_from("<I", data, s + 16)[0]
        sections.append((va, vsz, raw, rsz))

    def rva2off(rva):
        for va, vsz, raw, rsz in sections:
            if va <= rva < va + max(vsz, rsz):
                return raw + (rva - va)
        return None

    out = []
    off = rva2off(import_rva)
    while True:
        tag, tds, fwd, name_rva, fthunk = struct.unpack_from("<IIIII", data, off)
        if name_rva == 0:
            break
        no = rva2off(name_rva)
        end = data.index(b"\0", no)
        dll = data[no:end].decode("ascii", "replace")
        out.append(dll)
        off += 20
    return out


def main(bundle: str, rel: str):
    d = Path(bundle).resolve()
    sys32 = Path(os.environ["SystemRoot"]) / "System32"
    pathdirs = [Path(x) for x in os.environ.get("PATH", "").split(";") if x]
    for target_rel in (rel, "PySide6/" + rel):
        f = d / target_rel
        if not f.exists():
            continue
        print(f"=== {f.name} deps ===")
        for dep in read_imports(f):
            places = []
            for cand in (f.parent, d, d / "PySide6", d / "shiboken6", sys32,
                         *pathdirs):
                c = cand / dep
                if c.exists():
                    places.append(str(c))
                    break
            if places:
                mark = "OK " if (places[0].startswith(str(d)) or places[0] == str(sys32 / dep)) else "alt"
                print(f"  {mark} {dep:<34} <- {places[0]}")
            else:
                print(f"  ??? {dep:<34} NOT FOUND ANYWHERE")
        return


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
