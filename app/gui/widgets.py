"""Shared small widgets/helpers for the management GUI."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QTableWidget, QVBoxLayout,
    QWidget,
)


def page_header(title: str, hint: str = "") -> QWidget:
    """Page title row: bold title + optional muted hint."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    lay.addWidget(t)
    if hint:
        h = QLabel(hint)
        h.setObjectName("muted")
        lay.addWidget(h)
    return w


def make_panel(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    """White rounded panel; returns (frame, its content layout)."""
    frame = QFrame()
    frame.setObjectName("panel")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setObjectName("panelTitle")
        lay.addWidget(t)
    return frame, lay


def style_table(table: QTableWidget, columns: list[str], stretch_last: bool = True) -> None:
    """Common read-only row-selection table setup."""
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setShowGrid(False)
    table.horizontalHeader().setStretchLastSection(stretch_last)
    table.verticalHeader().setDefaultSectionSize(30)


def hbox(spacing: int = 8) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(0, 0, 0, 0)
    return lay


def fmt_size(n: int) -> str:
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f} MB"
    return f"{n / 1024:.1f} KB"


def align(item, center: bool = True):
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if center
                          else Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    return item
