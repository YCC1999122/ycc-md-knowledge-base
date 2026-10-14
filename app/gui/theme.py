"""Global Qt stylesheet. Strict layout, light blue theme, no external resources.

Colors follow docs/界面原型.html: primary #2563eb, background #f3f5f9,
white panels with 10px radius and #e4e8f0 borders. Font: Microsoft YaHei.
"""

PRIMARY = "#2563eb"
PRIMARY_HOVER = "#2f6bff"
PRIMARY_PRESSED = "#1e40af"
BG = "#f3f5f9"
PANEL = "#ffffff"
BORDER = "#e4e8f0"
TEXT = "#1f2937"
MUTED = "#6b7280"
NAV_CHECK_BG = "#e8efff"
DANGER = "#dc2626"

QSS = f"""
* {{
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}

/* ---------- sidebar ---------- */
QFrame#sidebar {{
    background: {PANEL};
    border-right: 1px solid {BORDER};
}}
QLabel#appTitle {{
    font-size: 16px;
    font-weight: 700;
    padding: 18px 16px 2px 16px;
}}
QLabel#appSub {{
    color: {MUTED};
    font-size: 12px;
    padding: 0 16px 12px 16px;
}}
QPushButton#nav {{
    text-align: left;
    padding: 9px 16px;
    border: none;
    border-radius: 6px;
    margin: 1px 10px;
    background: transparent;
    color: #374151;
}}
QPushButton#nav:hover {{
    background: #eef2f7;
}}
QPushButton#nav:checked {{
    background: {NAV_CHECK_BG};
    color: {PRIMARY};
    font-weight: 600;
}}
QPushButton#opButton {{
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-top: 1px solid {BORDER};
    color: {MUTED};
    background: transparent;
}}
QPushButton#opButton:hover {{
    color: {PRIMARY};
    background: #f8fafc;
}}

/* ---------- panels & cards ---------- */
QFrame#panel {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#panelTitle {{
    font-size: 14px;
    font-weight: 600;
    padding-bottom: 4px;
}}
QLabel#pageTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#muted {{
    color: {MUTED};
}}
QLabel#statNum {{
    font-size: 26px;
    font-weight: 700;
    color: {PRIMARY};
}}
QLabel#statLabel {{
    color: {MUTED};
}}
QFrame#dropzone {{
    background: #f8fafc;
    border: 2px dashed #93c5fd;
    border-radius: 10px;
}}
QLabel#dropHint {{
    color: {MUTED};
    font-size: 14px;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background: {PANEL};
    border: 1px solid #d0d7e2;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY};
}}
QPushButton:disabled {{
    color: #9ca3af;
    background: #f3f4f6;
    border-color: {BORDER};
}}
QPushButton#primary {{
    background: {PRIMARY};
    border: 1px solid {PRIMARY};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: {PRIMARY_HOVER};
    border-color: {PRIMARY_HOVER};
    color: #ffffff;
}}
QPushButton#primary:pressed {{
    background: {PRIMARY_PRESSED};
}}
QPushButton#danger {{
    color: {DANGER};
    border: 1px solid #fca5a5;
}}
QPushButton#danger:hover {{
    background: #fef2f2;
    color: {DANGER};
    border-color: {DANGER};
}}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QTextBrowser {{
    background: {PANEL};
    border: 1px solid #d0d7e2;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {NAV_CHECK_BG};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextBrowser:focus {{
    border-color: {PRIMARY};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {NAV_CHECK_BG};
    selection-color: {TEXT};
}}

/* ---------- tables ---------- */
QTableWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: #eef1f6;
}}
QTableWidget::item {{
    padding: 4px 6px;
    border: none;
}}
QTableWidget::item:selected {{
    background: {NAV_CHECK_BG};
    color: {TEXT};
}}
QHeaderView::section {{
    background: #f8fafc;
    color: #475569;
    font-weight: 600;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px;
}}

/* ---------- lists ---------- */
QListWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 5px;
}}
QListWidget::item:selected {{
    background: {NAV_CHECK_BG};
    color: {PRIMARY};
}}
QListWidget::item:hover:!selected {{
    background: #f1f5f9;
}}

QSplitter::handle {{
    background: {BORDER};
    width: 1px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #94a3b8;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolTip {{
    background: {PANEL};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 4px 6px;
}}
"""
