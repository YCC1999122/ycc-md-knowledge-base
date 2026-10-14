# Runtime hook: put the verbatim PySide6 copy (next to the bundled files) on
# sys.path first, so PySide6 loads exactly like in source mode.
import os
import sys

base = getattr(sys, "_MEIPASS", None)
if base and os.path.isdir(os.path.join(base, "PySide6")):
    sys.path.insert(0, base)
