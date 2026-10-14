"""Generate the application icon: blue rounded square + white folded document.

Run from project root with the bundled runtime:
  runtime\\python\\python.exe scripts\\make_icon.py

Output: app\\gui\\icon.png (256x256)
"""
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QGuiApplication, QImage, QPainter,  # noqa: E402
                           QPainterPath, QPen)

BLUE = QColor("#2563eb")
BLUE_LIGHT = QColor("#bfdbfe")
WHITE = QColor("#ffffff")

S = 256  # canvas size


def draw(p: QPainter) -> None:
    p.setRenderHint(QPainter.Antialiasing)

    # background: rounded square
    p.setPen(Qt.NoPen)
    p.setBrush(BLUE)
    p.drawRoundedRect(QRectF(0, 0, S, S), 56, 56)

    # document body (white) with folded top-right corner
    x, y, w, h = 64.0, 44.0, 128.0, 168.0
    fold = 36.0
    doc = QPainterPath(QPointF(x, y))
    doc.lineTo(x + w - fold, y)            # top edge up to the fold
    doc.lineTo(x + w, y + fold)            # diagonal fold
    doc.lineTo(x + w, y + h)               # right edge
    doc.lineTo(x, y + h)                   # bottom edge
    doc.closeSubpath()
    p.setBrush(WHITE)
    p.drawPath(doc)

    # fold triangle (light blue)
    corner = QPainterPath(QPointF(x + w - fold, y))
    corner.lineTo(x + w - fold, y + fold)
    corner.lineTo(x + w, y + fold)
    corner.closeSubpath()
    p.setBrush(BLUE_LIGHT)
    p.drawPath(corner)

    # text lines (blue, rounded caps)
    p.setPen(QPen(BLUE, 14, Qt.SolidLine, Qt.RoundCap))
    for i, length in enumerate((72.0, 72.0, 48.0)):
        ly = y + 64.0 + i * 30.0
        p.drawLine(QPointF(x + 24.0, ly), QPointF(x + 24.0 + length, ly))


def main() -> None:
    app = QGuiApplication([])  # noqa: F841 (needed for QPainter)
    img = QImage(S, S, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    draw(p)
    p.end()
    out = ROOT / "app" / "gui" / "icon.png"
    img.save(str(out))
    print(f"icon written: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
