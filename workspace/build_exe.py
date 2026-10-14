"""Build 知识库管理工具.exe (onefile, windowed) with PyInstaller.

Output lands at the project root so the frozen exe treats the root as its
data dir (paths.py): libraries/ config/ models/ stay shared and portable.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "runtime" / "python" / "python.exe"

# exe icon needs .ico — convert from the app icon
from PIL import Image
ico = ROOT / "workspace" / "app.ico"
img = Image.open(ROOT / "app" / "gui" / "icon.png")
img.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
print(f"[OK] icon -> {ico}")

cmd = [
    str(PY), "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--distpath", str(ROOT),                  # exe -> project root
    "--workpath", str(ROOT / "workspace" / "build"),
    str(ROOT / "workspace" / "kb.spec"),      # spec carries onefile/windowed/icon/collects
]
print(" ".join(cmd))
sys.exit(subprocess.call(cmd, cwd=ROOT))
