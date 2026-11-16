"""
ATLAS - shared theme helpers  (theme/theme.py)

Colours, fonts and small helpers used by the shared header / footer
(components/header.py, components/footer.py).

CINEMATIC TITLE FONT
    1. Download "Orbitron" from fonts.google.com/specimen/Orbitron
    2. Copy the .ttf file(s) into  assets/fonts/   (create the folder)
    3. Restart the app - it loads every .ttf / .otf in that folder automatically.
    (Without the file, it falls back to Bahnschrift / Segoe UI.)
"""
import glob
import os

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QRadialGradient
from PySide6.QtWidgets import QFrame, QLabel, QWidget

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# ----------------------------------------------------------------------------
# Main theme (same values as the screens)
# ----------------------------------------------------------------------------
CYAN = QColor("#3fd0e2")
PURPLE_LIGHT = "#a98bff"
GREEN = "#3de0a0"

# ----------------------------------------------------------------------------
# SHELL colours - header & footer use a navy / steel-blue band so users can
# tell them apart from the near-black page content.  Change them here.
# ----------------------------------------------------------------------------
SHELL_BG_TOP = "#14223a"
SHELL_BG_BOTTOM = "#0d1829"
SHELL_BORDER = "#25416b"
SHELL_ACCENT = "#4cc3ff"
SHELL_TEXT = "#e6f0fb"
SHELL_TEXT_DIM = "#8196b0"
SHELL_TEXT_FAINT = "#5d7391"

# ----------------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------------
SANS = ["Inter", "Segoe UI", "Helvetica Neue", "Arial"]
MONO = ["JetBrains Mono", "Consolas", "Menlo", "Courier New"]
TITLE_FONT = ["Orbitron", "Michroma", "Audiowide", "Bahnschrift", "Segoe UI", "Arial"]

_fonts_loaded = False


def load_custom_fonts():
    """Register every .ttf / .otf found in assets/fonts (runs once)."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    _fonts_loaded = True
    for pattern in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
        for path in glob.glob(os.path.join(FONTS_DIR, pattern)):
            QFontDatabase.addApplicationFont(path)


def make_font(families, px, weight=QFont.Normal, spacing=0.0):
    f = QFont()
    f.setFamilies(families)
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def make_label(text, families, px, color, weight=QFont.Normal, spacing=0.0,
               align=Qt.AlignLeft):
    lbl = QLabel(text)
    lbl.setFont(make_font(families, px, weight, spacing))
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    lbl.setAlignment(align | Qt.AlignVCenter)
    return lbl


def vline(height, color=SHELL_BORDER):
    f = QFrame()
    f.setFixedSize(1, height)
    f.setStyleSheet(f"background: {color};")
    return f


# ----------------------------------------------------------------------------
# Logo lookup (assets/ folder, matches the START of the file name)
# ----------------------------------------------------------------------------
def find_logo(name: str):
    folders = [ASSETS_DIR, os.path.join(os.getcwd(), "assets")]
    for folder in folders:
        matches = glob.glob(os.path.join(folder, name + "*"))
        matches = [m for m in matches if m.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
        if matches:
            return matches[0]
    print(f"[theme] Logo '{name}' not found. Looked in:")
    for f in folders:
        print("   ", os.path.abspath(f))
    return None


# ----------------------------------------------------------------------------
# Glowing status dot
# ----------------------------------------------------------------------------
class Dot(QWidget):
    def __init__(self, color, size=6, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.size = size
        self.setFixedSize(size + 8, size + 8)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_color(self, color):
        self.color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        g = QRadialGradient(c, self.width() / 2)
        c0 = QColor(self.color); c0.setAlpha(90)
        c1 = QColor(self.color); c1.setAlpha(0)
        g.setColorAt(0, c0)
        g.setColorAt(1, c1)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, self.width() / 2, self.width() / 2)
        p.setBrush(self.color)
        p.drawEllipse(c, self.size / 2, self.size / 2)
        p.end()