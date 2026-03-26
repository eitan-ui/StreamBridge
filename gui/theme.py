"""
StreamBridge — Carbon Glass Design System
Centralized design tokens, font loading, and unified QSS stylesheet.
"""
import os
import sys
import glob

from PyQt6.QtGui import QFontDatabase

# ─── Color Tokens ──────────────────────────────────────────────────────
BG_PRIMARY = "#08080e"
BG_SECONDARY = "#121218"
BG_TERTIARY = "#0a0a12"
CARD_BG = "rgba(255, 255, 255, 0.02)"
CARD_BORDER = "rgba(255, 255, 255, 0.04)"
INPUT_BG = "rgba(255, 255, 255, 0.03)"
INPUT_BORDER = "rgba(255, 255, 255, 0.06)"
INPUT_FOCUS = "rgba(34, 211, 238, 0.5)"
ACCENT = "#22d3ee"
SUCCESS = "#34d399"
ERROR = "#f87171"
WARNING = "#fbbf24"
TEXT_PRIMARY = "#f0f2f8"
TEXT_SECONDARY = "rgba(255, 255, 255, 0.50)"
TEXT_MUTED = "rgba(255, 255, 255, 0.25)"
TEXT_ON_BUTTON = "#08080e"
SELECTION_BG = "rgba(34, 211, 238, 0.2)"
HOVER_BG = "rgba(255, 255, 255, 0.04)"
DIALOG_BORDER = "#252545"

# ─── Spacing Tokens ───────────────────────────────────────────────────
MARGIN = 14
SPACING_LG = 10
SPACING_MD = 8
SPACING_SM = 5

# ─── Border Radius ────────────────────────────────────────────────────
RADIUS_CARD = 10
RADIUS_INPUT = 8
RADIUS_SM = 4

# ─── Font Tokens ──────────────────────────────────────────────────────
FONT_FAMILY = "'Plus Jakarta Sans', 'Helvetica Neue', sans-serif"
FONT_MONO = "'JetBrains Mono', 'SF Mono', 'Consolas', 'Menlo', monospace"
FONT_XL = 14
FONT_LG = 12
FONT_MD = 11
FONT_SM = 9
FONT_XS = 8


def load_fonts():
    """Register bundled fonts with Qt. Call once after QApplication creation."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fonts_dir = os.path.join(base, "resources", "fonts")
    for ttf in glob.glob(os.path.join(fonts_dir, "*.ttf")):
        QFontDatabase.addApplicationFont(ttf)


# ─── Unified QSS Stylesheet ──────────────────────────────────────────
BASE_STYLESHEET = f"""
/* ── Base ─────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {BG_PRIMARY}, stop:0.5 {BG_SECONDARY}, stop:1 {BG_TERTIARY});
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_MD}px;
    font-weight: 500;
}}

QLabel {{
    background: transparent;
    font-size: {FONT_MD}px;
    font-weight: 500;
}}

/* ── Inputs ───────────────────────────────────────────── */
QLineEdit {{
    background-color: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_MD}px;
    font-weight: 500;
    min-height: 14px;
}}
QLineEdit:focus {{
    border-color: {INPUT_FOCUS};
}}
QLineEdit::placeholder {{
    color: {TEXT_MUTED};
}}

QComboBox {{
    background-color: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_MD}px;
    font-weight: 500;
    min-height: 14px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    width: 0;
    height: 0;
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_SECONDARY};
    border: 1px solid {CARD_BORDER};
    border-radius: 8px;
    color: {TEXT_PRIMARY};
    selection-background-color: {SELECTION_BG};
    selection-color: #ffffff;
    outline: 0;
    padding: 4px;
    font-size: {FONT_MD}px;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_MD}px;
    font-weight: 500;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {INPUT_FOCUS};
}}

QTimeEdit {{
    background-color: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_MD}px;
    font-weight: 500;
}}

/* ── Buttons ──────────────────────────────────────────── */
QPushButton {{
    border: 1px solid {CARD_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 7px 12px;
    font-weight: 600;
    font-size: {FONT_MD}px;
    background-color: {HOVER_BG};
    color: {TEXT_PRIMARY};
}}
QPushButton:hover {{
    background-color: rgba(255, 255, 255, 0.06);
}}

QPushButton#startBtn {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {SUCCESS}, stop:1 #22c589);
    color: {TEXT_ON_BUTTON};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    border: none;
}}
QPushButton#startBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4ae8ad, stop:1 {SUCCESS});
}}
QPushButton#startBtn:disabled {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0d1a14, stop:1 #0a1510);
    color: {TEXT_MUTED};
}}

QPushButton#stopBtn {{
    background: {HOVER_BG};
    color: {TEXT_MUTED};
    border: 1px solid {INPUT_BORDER};
}}
QPushButton#stopBtn:enabled {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {ERROR}, stop:1 #dc4e4e);
    color: #fff;
    border: none;
}}
QPushButton#stopBtn:enabled:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fca5a5, stop:1 {ERROR});
}}

QPushButton#smallBtn {{
    background-color: {CARD_BG};
    color: {TEXT_SECONDARY};
    padding: 6px 10px;
    font-size: {FONT_SM}px;
    font-weight: 500;
    border-radius: 8px;
    border: 1px solid {CARD_BORDER};
}}
QPushButton#smallBtn:hover {{
    background-color: {HOVER_BG};
    color: {TEXT_PRIMARY};
}}

QPushButton#saveBtn {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {SUCCESS}, stop:1 #22c589);
    color: {TEXT_ON_BUTTON};
    border: none;
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.5px;
}}
QPushButton#saveBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4ae8ad, stop:1 {SUCCESS});
}}

QPushButton#accentBtn {{
    background-color: rgba(34, 211, 238, 0.12);
    color: {ACCENT};
    border: 1px solid rgba(34, 211, 238, 0.1);
}}
QPushButton#accentBtn:hover {{
    background-color: rgba(34, 211, 238, 0.18);
}}

QPushButton#dangerBtn {{
    background-color: rgba(248, 113, 113, 0.1);
    color: {ERROR};
    border: 1px solid rgba(248, 113, 113, 0.08);
}}
QPushButton#dangerBtn:hover {{
    background-color: rgba(248, 113, 113, 0.16);
}}

/* ── Panels / Frames ─────────────────────────────────── */
QFrame#statusPanel {{
    background-color: {CARD_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#endpointPanel {{
    background-color: {CARD_BG};
    border: 1px solid rgba(34, 211, 238, 0.06);
    border-radius: {RADIUS_CARD}px;
}}

/* ── Tab Widget ───────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {CARD_BORDER};
    background-color: {BG_PRIMARY};
    border-radius: 10px;
    margin-top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    padding: 9px 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: {FONT_SM}px;
    font-weight: 600;
    min-width: 60px;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_PRIMARY};
}}

/* ── Group Box ────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {CARD_BORDER};
    border-radius: {RADIUS_CARD}px;
    margin-top: 16px;
    padding: 18px 16px 14px;
    font-size: {FONT_SM}px;
    font-weight: 500;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    padding: 0 10px;
    color: {ACCENT};
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* ── Check Box ────────────────────────────────────────── */
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: {FONT_MD}px;
    font-weight: 500;
    spacing: 10px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {INPUT_BORDER};
    border-radius: 5px;
    background-color: {INPUT_BG};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Table Widget ─────────────────────────────────────── */
QTableWidget {{
    background-color: {INPUT_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: {RADIUS_INPUT}px;
    gridline-color: {CARD_BORDER};
    color: {TEXT_PRIMARY};
    font-size: {FONT_MD}px;
    font-weight: 500;
}}
QTableWidget::item {{
    padding: 8px 12px;
}}
QTableWidget::item:selected {{
    background-color: rgba(34, 211, 238, 0.08);
    color: {TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: {CARD_BG};
    color: {TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {CARD_BORDER};
    padding: 10px 12px;
    font-size: {FONT_SM}px;
    font-weight: 600;
}}

/* ── Text Edit / Log ──────────────────────────────────── */
QTextEdit {{
    background-color: rgba(8, 8, 14, 0.9);
    border: 1px solid {CARD_BORDER};
    border-radius: {RADIUS_INPUT}px;
    color: {TEXT_SECONDARY};
    font-family: {FONT_MONO};
    font-size: {FONT_SM}px;
    padding: 12px 14px;
    line-height: 1.5;
}}

/* ── Scroll Area ──────────────────────────────────────── */
QScrollArea {{
    border: none;
    background: transparent;
}}

/* ── Scrollbar ────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.14);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── List Widget ──────────────────────────────────────── */
QListWidget {{
    background-color: {INPUT_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: {RADIUS_INPUT}px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_MD}px;
    outline: 0;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background-color: {SELECTION_BG};
}}
QListWidget::item:hover {{
    background-color: {HOVER_BG};
}}
"""

# ─── Dialog Stylesheet ──────────────────────────────────────────────
# Extends BASE_STYLESHEET with dialog-specific overrides
DIALOG_STYLESHEET = BASE_STYLESHEET + f"""
/* ── Dialog overrides ────────────────────────────────── */
QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {BG_PRIMARY}, stop:0.5 {BG_SECONDARY}, stop:1 {BG_TERTIARY});
    border: 1px solid {DIALOG_BORDER};
}}

QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
"""


def apply_dialog_theme(dialog, title: str = "", min_width: int = 600,
                       min_height: int = 400) -> None:
    """Apply Carbon Glass theme to a QDialog."""
    dialog.setStyleSheet(DIALOG_STYLESHEET)
    if title:
        dialog.setWindowTitle(title)
    dialog.setMinimumSize(min_width, min_height)
