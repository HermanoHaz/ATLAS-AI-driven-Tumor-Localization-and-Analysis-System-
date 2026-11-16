"""
ATLAS - Dashboard Interface

Place at: interfaces/dashboard.py
Preview on its own:  python interfaces\\dashboard.py

Signals:
    module_selected(key)   key = "scanner" | "queue" | "patients" | "reports"
    see_all_upcoming()     "SEE ALL" in the Upcoming section was clicked
    user_clicked()         user chip (top right) was clicked
    settings_clicked()     gear button in the header was clicked

Handy methods (call these later when the database is ready):
    set_user(full_name, department)
    set_stats(total, processing, verified, pending)
    set_badge("queue", "02 awaiting review")
    set_today_tasks([(title, subtitle, right_text), ...])   [] = empty state
    set_upcoming([(title, subtitle, right_text), ...])      next 30 days, [] = empty
"""
import glob
import math
import os
import random
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from components.header import AppHeader
from components.footer import AppFooter

# ============================================================================
#  >>>  MODULE CARD BACKGROUNDS - EDIT HERE  <<<
# ============================================================================
# By default each card gets a generated sci-fi background (neon grid, circuit
# traces, light rays, flowing waves) - no files needed.
#
# To use your OWN picture on a card instead:
#   1. put the image in  assets/backgrounds/
#   2. type the START of its file name below (any .png / .jpg / .webp)
# Leave "" to keep the generated background for that card.
CARD_SCALE = 1.3   # size of the icon / text inside the module cards (1.0 = old size)

CARD_IMAGES = {
    "scanner":  "",      # e.g. "card_scanner"
    "queue":    "",      # e.g. "card_queue"
    "patients": "",      # e.g. "card_patients"
    "reports":  "",      # e.g. "card_reports"
}
# ============================================================================


def find_card_image(key: str):
    name = CARD_IMAGES.get(key, "")
    if not name:
        return None
    for folder in (os.path.join(ROOT_DIR, "assets", "backgrounds"),
                   os.path.join(os.getcwd(), "assets", "backgrounds")):
        for m in glob.glob(os.path.join(folder, name + "*")):
            if m.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                return m
    print(f"[dashboard] Card background '{name}' not found in assets/backgrounds/")
    return None

# ----------------------------------------------------------------------------
# Theme  (same base values as login.py / user_register.py)
# ----------------------------------------------------------------------------
BG = QColor("#04050a")
CYAN = QColor("#3fd0e2")
PURPLE = QColor("#7c5cff")
TEXT = "#e8eef2"
TEXT_DIM = "#5b6670"
TEXT_FAINT = "#46515a"
TEXT_SOFT = "#7d8a94"
PURPLE_LIGHT = "#a98bff"
GREEN = "#3de0a0"
CYAN_LIGHT = "#4fd8ea"
LINE = "#1a2227"
LIGHT_MODE = False

SANS = ["Inter", "Segoe UI", "Helvetica Neue", "Arial"]

PANEL_WIDTH = 380     # width of the right-hand panel (was 298) - change to resize
MONO = ["JetBrains Mono", "Consolas", "Menlo", "Courier New"]


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


def hline(color=LINE):
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {color};")
    return f


def vline(height, color="#1c2a31"):
    f = QFrame()
    f.setFixedSize(1, height)
    f.setStyleSheet(f"background: {color};")
    return f


# ----------------------------------------------------------------------------
# Small reusable widgets
# ----------------------------------------------------------------------------
class Dot(QWidget):
    def __init__(self, color, size=6, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.size = size
        self.setFixedSize(size + 8, size + 8)
        self.setAttribute(Qt.WA_TranslucentBackground)

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


# ----------------------------------------------------------------------------
# Module cards
# ----------------------------------------------------------------------------
def draw_module_icon(p: QPainter, kind: str, cx: float, cy: float, color: QColor):
    p.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    if kind == "patient":
        p.drawEllipse(QPointF(cx - 2, cy - 4.5), 4, 4)
        path = QPainterPath()
        path.moveTo(cx - 9, cy + 9)
        path.cubicTo(cx - 9, cy + 1, cx + 5, cy + 1, cx + 5, cy + 9)
        p.drawPath(path)
        p.drawLine(QPointF(cx + 6, cy - 5), QPointF(cx + 12, cy - 5))
        p.drawLine(QPointF(cx + 9, cy - 8), QPointF(cx + 9, cy - 2))

    elif kind == "queue":
        p.drawRoundedRect(QRectF(cx - 9, cy - 10, 18, 20), 2.5, 2.5)
        p.drawLine(QPointF(cx - 5, cy - 4), QPointF(cx + 5, cy - 4))
        p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 1, cy))
        p.drawEllipse(QPointF(cx + 4, cy + 5), 3.4, 3.4)
        p.drawLine(QPointF(cx + 6.5, cy + 7.5), QPointF(cx + 9.5, cy + 10.5))

    elif kind == "report":
        path = QPainterPath()
        path.moveTo(cx - 7, cy - 10)
        path.lineTo(cx + 3, cy - 10)
        path.lineTo(cx + 8, cy - 5)
        path.lineTo(cx + 8, cy + 10)
        path.lineTo(cx - 7, cy + 10)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(cx + 3, cy - 10), QPointF(cx + 3, cy - 5))
        p.drawLine(QPointF(cx + 3, cy - 5), QPointF(cx + 8, cy - 5))
        p.drawLine(QPointF(cx - 3, cy), QPointF(cx + 4, cy))
        p.drawLine(QPointF(cx - 3, cy + 5), QPointF(cx - 1, cy + 7))
        p.drawLine(QPointF(cx - 1, cy + 7), QPointF(cx + 3, cy + 3))

    elif kind == "scanner":
        a, s = 5, 11
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x, y = cx + sx * s, cy + sy * s
            p.drawLine(QPointF(x, y), QPointF(x - sx * a, y))
            p.drawLine(QPointF(x, y), QPointF(x, y - sy * a))
        p.drawEllipse(QPointF(cx, cy), 6.5, 6.5)
        p.drawLine(QPointF(cx - 5, cy), QPointF(cx - 2, cy))
        p.drawLine(QPointF(cx - 2, cy), QPointF(cx - 1, cy - 4))
        p.drawLine(QPointF(cx - 1, cy - 4), QPointF(cx + 1, cy + 4))
        p.drawLine(QPointF(cx + 1, cy + 4), QPointF(cx + 2, cy))
        p.drawLine(QPointF(cx + 2, cy), QPointF(cx + 5, cy))


# ----------------------------------------------------------------------------
# Generated card backgrounds
# ----------------------------------------------------------------------------
def _bg_grid(p: QPainter, w, h):
    """Neon perspective grid floor + horizon glow."""
    hz, vx = h * 0.52, w * 0.62
    rnd = random.Random(11)
    p.setPen(Qt.NoPen)
    for _ in range(26):                                   # faint stars above the horizon
        p.setBrush(QColor(170, 180, 255, rnd.randint(25, 90)))
        p.drawEllipse(QPointF(rnd.uniform(0, w), rnd.uniform(0, hz)), 0.9, 0.9)

    g = QLinearGradient(0, hz - 34, 0, hz + 12)           # horizon glow
    g.setColorAt(0.0, QColor(110, 130, 255, 0))
    g.setColorAt(0.75, QColor(120, 140, 255, 80))
    g.setColorAt(1.0, QColor(120, 140, 255, 0))
    p.fillRect(QRectF(0, hz - 34, w, 46), g)

    for i in range(-24, 25):                              # lines running to the viewer
        alpha = int(max(12, 95 - abs(i) * 3.2))
        p.setPen(QPen(QColor(120, 140, 255, alpha), 1))
        p.drawLine(QPointF(vx + i * 4, hz), QPointF(vx + i * (w / 8.5), h))

    rows = 11                                             # cross lines (perspective spacing)
    for r in range(1, rows + 1):
        t = (r / rows) ** 2.1
        p.setPen(QPen(QColor(125, 150, 255, int(30 + 95 * t)), 1))
        y = hz + (h - hz) * t
        p.drawLine(QPointF(0, y), QPointF(w, y))


def _bg_circuit(p: QPainter, w, h):
    """Glowing circuit traces coming in from the right edge."""
    rnd = random.Random(7)
    for _ in range(12):
        x, y = w + 4, rnd.uniform(h * 0.10, h * 0.92)
        pts = [QPointF(x, y)]
        x -= rnd.uniform(w * 0.08, w * 0.30)
        pts.append(QPointF(x, y))
        d = rnd.choice((-1, 1)) * rnd.uniform(14, 44)
        x -= abs(d)
        y += d
        pts.append(QPointF(x, y))
        x -= rnd.uniform(w * 0.06, w * 0.26)
        pts.append(QPointF(max(x, 0), y))

        alpha = rnd.randint(55, 120)
        p.setPen(QPen(QColor(124, 92, 255, alpha), 1.2))
        p.setBrush(Qt.NoBrush)
        for a, b in zip(pts, pts[1:]):
            p.drawLine(a, b)

        end = pts[-1]                                     # node at the end of the trace
        p.setPen(QPen(QColor(63, 208, 226, 150), 1))
        p.setBrush(QColor(10, 14, 24))
        p.drawEllipse(end, 3, 3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(63, 208, 226, 200))
        p.drawEllipse(end, 1.2, 1.2)


def _bg_rays(p: QPainter, w, h):
    """Vertical light streaks with a glowing edge, like a sci-fi corridor."""
    rnd = random.Random(23)
    for edge, direction in ((w, -1), (0, 1)):
        g = QLinearGradient(edge, 0, edge + direction * 70, 0)
        g.setColorAt(0.0, QColor(150, 100, 255, 90))
        g.setColorAt(1.0, QColor(150, 100, 255, 0))
        p.fillRect(QRectF(min(edge, edge + direction * 70), 0, 70, h), g)

    for _ in range(30):
        x = w * 0.42 + rnd.random() * w * 0.58
        top, bottom = rnd.uniform(0, h * 0.45), rnd.uniform(h * 0.55, h)
        g = QLinearGradient(0, top, 0, bottom)
        g.setColorAt(0.0, QColor(160, 110, 255, 0))
        g.setColorAt(0.5, QColor(160, 110, 255, rnd.randint(40, 120)))
        g.setColorAt(1.0, QColor(160, 110, 255, 0))
        p.setPen(QPen(g, rnd.choice((1, 1, 1.4))))
        p.drawLine(QPointF(x, top), QPointF(x, bottom))

    p.setPen(Qt.NoPen)
    for _ in range(40):
        p.setBrush(QColor(200, 170, 255, rnd.randint(30, 140)))
        p.drawEllipse(QPointF(w * 0.45 + rnd.random() * w * 0.55, rnd.uniform(0, h)), 1, 1)


def _bg_waves(p: QPainter, w, h):
    """Flowing dotted waves, like a data stream."""
    g = QLinearGradient(0, h * 0.45, 0, h)
    g.setColorAt(0.0, QColor(150, 70, 220, 0))
    g.setColorAt(1.0, QColor(150, 70, 220, 60))
    p.fillRect(QRectF(0, h * 0.45, w, h * 0.55), g)

    p.setPen(Qt.NoPen)
    for k in range(8):
        amp = 9 + k * 3
        base = h * 0.62 + k * 7
        color = QColor(150 + k * 10, 90, 255 - k * 12, 120 - k * 6)
        x = 0.0
        while x <= w:
            y = base + math.sin(x * 0.017 + k * 0.7) * amp
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), 1.0, 1.0)
            x += 5


BG_STYLES = {
    "scanner": _bg_grid,
    "queue": _bg_circuit,
    "patients": _bg_rays,
    "reports": _bg_waves,
}


def build_card_background(key: str, w: int, h: int, dpr: float) -> QPixmap:
    """Render the card background once into a pixmap (cached by the card)."""
    pm = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 2, 2)
    p.setClipPath(clip)

    base = QLinearGradient(0, 0, w, h)
    base.setColorAt(0, QColor(14, 16, 28))
    base.setColorAt(1, QColor(9, 10, 18))
    p.fillRect(QRectF(0, 0, w, h), base)

    path = find_card_image(key)
    img = QPixmap(path) if path else QPixmap()
    if not img.isNull():                                   # your own picture (cover-fit)
        tw, th = int(w * dpr), int(h * dpr)
        scaled = img.scaled(tw, th, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        sx, sy = (scaled.width() - tw) // 2, (scaled.height() - th) // 2
        p.drawPixmap(QRectF(0, 0, w, h), scaled, QRectF(sx, sy, tw, th))
    else:
        BG_STYLES.get(key, _bg_grid)(p, w, h)

    # keep the text readable: darken the left side and the bottom
    left = QLinearGradient(0, 0, w, 0)
    left.setColorAt(0.0, QColor(7, 9, 16, 215))
    left.setColorAt(0.55, QColor(7, 9, 16, 120))
    left.setColorAt(1.0, QColor(7, 9, 16, 0))
    p.fillRect(QRectF(0, 0, w, h), left)
    bottom = QLinearGradient(0, h * 0.35, 0, h)
    bottom.setColorAt(0.0, QColor(7, 9, 16, 0))
    bottom.setColorAt(1.0, QColor(7, 9, 16, 170))
    p.fillRect(QRectF(0, 0, w, h), bottom)
    p.end()
    return pm


class ModuleCard(QWidget):
    clicked = Signal(str)

    def __init__(self, key, index, title, desc, icon, accent="purple",
                 arrow=False, badge="", parent=None):
        super().__init__(parent)
        self.key, self.index, self.title, self.desc = key, index, title, desc
        self.icon, self.accent, self.arrow, self.badge = icon, accent, arrow, badge
        self._hover = False
        self._bg = None
        self._bg_key = None
        self.setMinimumHeight(int(193 * CARD_SCALE))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

    def set_badge(self, text: str):
        self.badge = text
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.key)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(0.5, 0.5, w - 1, h - 1)
        cyan = self.accent == "cyan"

        # ---- card body ----
        if LIGHT_MODE:
            g = QLinearGradient(0, 0, w, h)
            g.setColorAt(0, QColor("#ffffff"))
            g.setColorAt(1, QColor("#f1edf7"))
            p.setBrush(g)
            border = QColor("#cfc5dd") if self._hover else QColor("#ded7e8")
        elif cyan:
            g = QLinearGradient(0, 0, w, h)
            g.setColorAt(0, QColor(12, 48, 60, 235))
            g.setColorAt(1, QColor(9, 30, 40, 235))
            p.setBrush(g)
            border = QColor("#2b8190") if self._hover else QColor("#1f6b78")
        else:
            key = (w, h, self.devicePixelRatioF())
            if self._bg_key != key:                      # rebuild only when the size changes
                self._bg = build_card_background(self.key, w, h, key[2])
                self._bg_key = key
            p.setOpacity(1.0 if self._hover else 0.82)   # slightly brighter on hover
            p.drawPixmap(0, 0, self._bg)
            p.setOpacity(1.0)
            p.setBrush(Qt.NoBrush)
            border = QColor("#3a4378") if self._hover else QColor("#232a3d")
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(rect, 2, 2)

        # everything below (icon, text, badge) is drawn bigger by CARD_SCALE
        p.scale(CARD_SCALE, CARD_SCALE)
        w, h = w / CARD_SCALE, h / CARD_SCALE

        # ---- "MODULE / 01" ----
        p.setFont(make_font(MONO, 8, spacing=1.4))
        p.setPen(QColor(TEXT_FAINT))
        p.drawText(QRectF(22, 14, w - 80, 16), Qt.AlignLeft | Qt.AlignVCenter, self.index)

        # ---- glowing dot on the scanner card ----
        if cyan:
            c = QPointF(w - 24, 23)
            g = QRadialGradient(c, 9)
            if LIGHT_MODE:
                g.setColorAt(0, QColor(20, 126, 139, 100))
                g.setColorAt(1, QColor(20, 126, 139, 0))
            else:
                g.setColorAt(0, QColor(63, 208, 226, 120))
                g.setColorAt(1, QColor(63, 208, 226, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, 9, 9)
            p.setBrush(CYAN)
            p.drawEllipse(c, 2.6, 2.6)

        # ---- icon box ----
        box = QRectF(22, 56 + (h - 193) * 0.5, 52, 52)   # icon drifts down as the card grows
        if LIGHT_MODE:
            p.setBrush(QColor("#e6f4f5" if cyan else "#f0eafb"))
            p.setPen(QPen(QColor("#c6e4e7" if cyan else "#d7cbe9"), 1))
            icon_color = QColor(CYAN_LIGHT if cyan else PURPLE_LIGHT)
        elif cyan:
            p.setBrush(QColor("#0f3140"))
            p.setPen(QPen(QColor("#2b8190"), 1))
            icon_color = QColor(CYAN_LIGHT)
        else:
            p.setBrush(QColor("#17162b"))
            p.setPen(QPen(QColor("#2b2a50"), 1))
            icon_color = QColor(PURPLE_LIGHT)
        p.drawRoundedRect(box, 3, 3)
        draw_module_icon(p, self.icon, box.center().x(), box.center().y(), icon_color)

        # ---- title / description ----
        p.setPen(QColor(TEXT))
        p.setFont(make_font(MONO, 14, QFont.Medium, 1.6))
        p.drawText(QRectF(22, h - 76, w - 44, 26), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setPen(QColor(TEXT_SOFT))
        p.setFont(make_font(SANS, 11))
        p.drawText(QRectF(22, h - 52, w - 44, 20), Qt.AlignLeft | Qt.AlignVCenter, self.desc)

        # ---- badge (bottom-right) ----
        if self.badge:
            f = make_font(MONO, 8, spacing=0.8)
            p.setFont(f)
            tw = QFontMetrics(f).horizontalAdvance(self.badge)
            right = w - 22
            p.setPen(QColor(TEXT_DIM))
            p.drawText(QRectF(right - tw - 4, h - 30, tw + 8, 16),
                       Qt.AlignRight | Qt.AlignVCenter, self.badge)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(TEXT_DIM))
            p.drawEllipse(QPointF(right - tw - 11, h - 22), 2, 2)
        p.end()


# ----------------------------------------------------------------------------
# Right panel pieces
# ----------------------------------------------------------------------------
def rule_row(left_text: str, right_text: str = "", line=True) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    lay.addWidget(make_label(left_text, MONO, 9, TEXT_DIM, spacing=1.6))
    if line:
        l = hline()
        lay.addWidget(l, 1)
    else:
        lay.addStretch(1)
    if right_text:
        lay.addWidget(make_label(right_text, MONO, 9, TEXT_DIM, spacing=1.4,
                                 align=Qt.AlignRight))
    return box


class StatsGrid(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self.values = {}
        cells = [
            ("total", "00", "TOTAL SCANNED", TEXT, 0, 0),
            ("processing", "00", "IN PROGRESS", CYAN_LIGHT, 0, 1),
            ("verified", "00", "VERIFIED", GREEN, 1, 0),
            ("pending", "00", "REPORTS PENDING", PURPLE_LIGHT, 1, 1),
        ]
        for key, num, label, color, r, c in cells:
            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(18, 18, 12, 16)
            cl.setSpacing(6)
            value = make_label(num, MONO, 28, color)
            cl.addWidget(value)
            cl.addWidget(make_label(label, MONO, 9, TEXT_DIM, spacing=1.2))
            self.values[key] = value
            grid.addWidget(cell, r, c)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

    def set_values(self, total, processing, verified, pending):
        for key, v in zip(("total", "processing", "verified", "pending"),
                          (total, processing, verified, pending)):
            self.values[key].setText(f"{int(v):02d}")

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.setBrush(QColor("#ffffff" if LIGHT_MODE else QColor(8, 11, 16, 200)))
        p.setPen(QPen(QColor(LINE), 1))
        p.drawRect(QRectF(0.5, 0.5, w - 1, h - 1))
        p.drawLine(w // 2, 0, w // 2, h)
        p.drawLine(0, h // 2, w, h // 2)
        p.end()


class CardFrame(QFrame):
    """Rounded dark card used for the task empty / list states."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#ffffff" if LIGHT_MODE else QColor(13, 16, 23, 225)))
        p.setPen(QPen(QColor(LINE), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 4, 4)
        p.end()


class IconCircle(QWidget):
    """Soft purple circle with a sun or calendar icon."""

    def __init__(self, kind: str, size=46, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(112, 72, 184, 32 if LIGHT_MODE else 50))
        p.drawEllipse(self.rect())

        cx, cy = self.width() / 2, self.height() / 2
        p.setPen(QPen(QColor(PURPLE_LIGHT), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        if self.kind == "sun":
            p.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
            for i in range(8):
                a = math.radians(i * 45)
                p.drawLine(QPointF(cx + math.cos(a) * 6.0, cy + math.sin(a) * 6.0),
                           QPointF(cx + math.cos(a) * 8.2, cy + math.sin(a) * 8.2))
        else:  # calendar
            p.drawRoundedRect(QRectF(cx - 7, cy - 6, 14, 13), 2, 2)
            p.drawLine(QPointF(cx - 7, cy - 2), QPointF(cx + 7, cy - 2))
            p.drawLine(QPointF(cx - 3, cy - 8), QPointF(cx - 3, cy - 5))
            p.drawLine(QPointF(cx + 3, cy - 8), QPointF(cx + 3, cy - 5))
        p.end()


class StateCard(CardFrame):
    """Empty state: icon, title, subtitle."""

    def __init__(self, icon, title, subtitle, subtitle_color=TEXT_DIM, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 20, 18, 20)
        lay.setSpacing(0)
        lay.addWidget(IconCircle(icon), 0, Qt.AlignHCenter)
        lay.addSpacing(12)
        lay.addWidget(make_label(title, SANS, 14, TEXT, QFont.DemiBold,
                                 align=Qt.AlignHCenter))
        lay.addSpacing(4)
        sub = make_label(subtitle, SANS, 12, subtitle_color, align=Qt.AlignHCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)


class TaskRow(QWidget):
    def __init__(self, title, sub="", right="", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(Dot(PURPLE_LIGHT, 5), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(make_label(title, SANS, 12, TEXT))
        if sub:
            col.addWidget(make_label(sub, SANS, 10, TEXT_DIM))
        lay.addLayout(col, 1)
        if right:
            lay.addWidget(make_label(right, MONO, 10, TEXT_DIM, align=Qt.AlignRight),
                          0, Qt.AlignTop)


class TaskListCard(CardFrame):
    def __init__(self, rows, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        for i, (title, sub, right) in enumerate(rows):
            if i:
                lay.addWidget(hline("#1a2027"))
            lay.addWidget(TaskRow(title, sub, right))


class OverviewPanel(QWidget):
    see_all_clicked = Signal()
    MAX_ROWS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(PANEL_WIDTH)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 34, 30, 26)
        lay.setSpacing(0)

        # ---- 1. today's task ----
        lay.addWidget(rule_row("DAILY OVERVIEW"))
        lay.addSpacing(18)
        lay.addWidget(make_label("TODAY'S TASK", MONO, 16, TEXT, QFont.Medium, 1.4))
        lay.addSpacing(3)
        self.today_sub = make_label("No urgent items right now.", SANS, 11, TEXT_DIM)
        lay.addWidget(self.today_sub)
        lay.addSpacing(10)
        self.today_holder = QVBoxLayout()
        self.today_holder.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.today_holder)
        lay.addSpacing(10)
        lay.addStretch(1)

        # ---- 2. upcoming (next 30 days) ----
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(make_label("UPCOMING", MONO, 16, PURPLE_LIGHT, QFont.Medium, 1.4))
        self.count_pill = QLabel("0 ITEMS")
        self.count_pill.setFont(make_font(MONO, 9, QFont.Bold, 1.0))
        self.count_pill.setStyleSheet(
            f"color: {PURPLE_LIGHT}; background: #1d1a3a; border: 1px solid #33305e;"
            " border-radius: 9px; padding: 2px 8px;")
        head.addWidget(self.count_pill, 0, Qt.AlignVCenter)
        head.addStretch(1)
        see = QPushButton("SEE ALL  \u2192")
        see.setCursor(Qt.PointingHandCursor)
        see.setFont(make_font(MONO, 9, QFont.Bold, 1.0))
        see.setStyleSheet(
            f"QPushButton {{ color: {PURPLE_LIGHT}; background: transparent;"
            " border: 1px solid #2b2a50; border-radius: 11px; padding: 3px 10px; }"
            "QPushButton:hover { border: 1px solid #7c5cff; color: #c4b5ff; }")
        see.clicked.connect(self.see_all_clicked.emit)
        head.addWidget(see, 0, Qt.AlignVCenter)
        lay.addLayout(head)
        lay.addSpacing(3)
        lay.addWidget(make_label("Your deadlines in the next 30 days.", SANS, 11, TEXT_DIM))
        lay.addSpacing(10)
        self.upcoming_holder = QVBoxLayout()
        self.upcoming_holder.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.upcoming_holder)
        lay.addSpacing(10)
        lay.addStretch(1)

        # ---- 3. workflow snapshot ----
        lay.addWidget(rule_row("WORKFLOW SNAPSHOT", "LIVE", line=False))
        lay.addSpacing(10)
        self.stats = StatsGrid()
        self.stats.setFixedHeight(150)
        lay.addWidget(self.stats)

        self.set_today_tasks([])
        self.set_upcoming([])

    # ---- helpers ----
    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def set_today_tasks(self, rows):
        """rows = [(title, subtitle, right_text), ...]  ([] shows the empty state)"""
        self._clear(self.today_holder)
        if rows:
            self.today_sub.setText(f"{len(rows)} task(s) due today.")
            self.today_holder.addWidget(TaskListCard(rows[:self.MAX_ROWS]))
        else:
            self.today_sub.setText("No urgent items right now.")
            self.today_holder.addWidget(
                StateCard("sun", "No tasks for today", "You're all set", PURPLE_LIGHT))

    def set_upcoming(self, rows):
        """rows = [(title, subtitle, right_text), ...]  ([] shows the empty state)"""
        self._clear(self.upcoming_holder)
        self.count_pill.setText(f"{len(rows)} ITEM{'S' if len(rows) != 1 else ''}")
        if rows:
            self.upcoming_holder.addWidget(TaskListCard(rows[:self.MAX_ROWS]))
        else:
            self.upcoming_holder.addWidget(StateCard(
                "calendar", "Nothing in the next 30 days.",
                "New tasks and revision sessions will appear here automatically."))

    def paintEvent(self, _):
        p = QPainter(self)
        if LIGHT_MODE:
            p.fillRect(self.rect(), QColor("#f5f2f9"))
        p.setPen(QPen(QColor(LINE if LIGHT_MODE else "#151c21"), 1))
        p.drawLine(0, 0, 0, self.height())
        p.end()


# ----------------------------------------------------------------------------
# Dashboard page
# ----------------------------------------------------------------------------
class DashboardPage(QWidget):
    module_selected = Signal(str)
    user_clicked = Signal()
    settings_clicked = Signal()
    see_all_upcoming = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1100, 700)
        self.full_name = "Dr. Amzar Najmi"
        self._build_ui()

    # ---- background -------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), BG)

        def glow(cx, cy, radius, color, alpha):
            g = QRadialGradient(QPointF(cx, cy), radius)
            c0 = QColor(color); c0.setAlpha(alpha)
            c1 = QColor(color); c1.setAlpha(0)
            g.setColorAt(0.0, c0)
            g.setColorAt(1.0, c1)
            p.fillRect(self.rect(), g)

        if LIGHT_MODE:
            glow(w * 0.42, h * 0.50, 380, QColor(170, 140, 210), 26)
            glow(w, h, w * 0.30, QColor(170, 140, 210), 22)
        else:
            glow(w * 0.42, h * 0.50, 380, QColor(70, 40, 150), 34)
            glow(w, h, w * 0.30, QColor(0, 140, 130), 45)
        p.end()

    # ---- UI ---------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = AppHeader()
        self.header.logout_clicked.connect(self.user_clicked.emit)
        self.header.settings_clicked.connect(self.settings_clicked.emit)
        root.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_left(), 1)
        self.panel = OverviewPanel()
        self.panel.see_all_clicked.connect(self.see_all_upcoming.emit)
        body.addWidget(self.panel)
        root.addLayout(body, 1)

        self.footer = AppFooter()
        root.addWidget(self.footer)

    def _build_left(self) -> QWidget:
        left = QWidget()
        lay = QVBoxLayout(left)
        lay.setContentsMargins(60, 52, 44, 40)
        lay.setSpacing(0)

        # "PERSONAL WORKSPACE ——"
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(make_label("PERSONAL WORKSPACE", MONO, 8, "#8b6cff", spacing=2.2))
        line = QFrame()
        line.setFixedSize(40, 1)
        line.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                           " stop:0 #7c5cff, stop:1 rgba(124,92,255,0));")
        row.addWidget(line)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(18)

        self.hello_label = make_label("", MONO, 30, TEXT, spacing=1.5)
        lay.addWidget(self.hello_label)
        self._update_hello()
        lay.addSpacing(12)
        lay.addWidget(make_label(
            "Welcome to ATLAS. Select a module to begin, or view active studies.",
            SANS, 12, TEXT_SOFT))
        lay.addSpacing(34)

        # module cards (2 x 2)
        self.cards = {}
        defs = [
            ("scanner", "MODULE / 01", "AI SCANNER",
             "Upload & segment an MRI scan immediately.", "scanner", "purple", False, ""),
            ("queue", "MODULE / 02", "SCANNER QUEUE",
             "Access scans ready for AI segmentation.", "queue", "purple", True,),
            ("patients", "MODULE / 03", "PATIENT INFORMATION",
             "View and manage all patient cases.", "patient", "purple", False, ""),
            ("reports", "MODULE / 04", "REPORTS",
             "Review and finalize AI-generated summaries.", "report", "purple", True,),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        for i, d in enumerate(defs):
            card = ModuleCard(*d)
            card.clicked.connect(self.module_selected.emit)
            self.cards[d[0]] = card
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid, 1)
        return left

    def _update_hello(self):
        self.hello_label.setText(f"HELLO, {self.full_name.upper()}")

    # ---- public API -------------------------------------------------------
    def set_user(self, full_name: str, department: str):
        self.full_name = full_name
        self.header.set_user(full_name, department)
        self._update_hello()

    def set_photo(self, pixmap):
        """Profile photo shown in the header avatar (QPixmap or None)."""
        self.header.set_photo(pixmap)

    def set_theme(self, dark: bool):
        global BG, CYAN, PURPLE, TEXT, TEXT_DIM, TEXT_FAINT, TEXT_SOFT
        global PURPLE_LIGHT, GREEN, CYAN_LIGHT, LINE, LIGHT_MODE
        light = not dark
        if LIGHT_MODE == light:
            return
        old = {TEXT: "#20182e" if light else "#e8eef2",
               TEXT_DIM: "#655d75" if light else "#5b6670",
               TEXT_FAINT: "#857d95" if light else "#46515a",
               TEXT_SOFT: "#5e576b" if light else "#7d8a94",
               CYAN.name(): "#147e8b" if light else "#3fd0e2",
               PURPLE: "#7048b8" if light else "#7c5cff",
               PURPLE_LIGHT: "#7048b8" if light else "#a98bff",
               GREEN: "#16805b" if light else "#3de0a0",
               CYAN_LIGHT: "#147e8b" if light else "#4fd8ea"}
        LIGHT_MODE = light
        BG = QColor("#f4f1f8" if light else "#04050a")
        CYAN = QColor("#147e8b" if light else "#3fd0e2")
        PURPLE = "#7048b8" if light else "#7c5cff"
        TEXT = "#20182e" if light else "#e8eef2"
        TEXT_DIM = "#655d75" if light else "#5b6670"
        TEXT_FAINT = "#857d95" if light else "#46515a"
        TEXT_SOFT = "#5e576b" if light else "#7d8a94"
        PURPLE_LIGHT = "#7048b8" if light else "#a98bff"
        GREEN = "#16805b" if light else "#3de0a0"
        CYAN_LIGHT = "#147e8b" if light else "#4fd8ea"
        LINE = "#d8d0e3" if light else "#1a2227"
        for label in self.findChildren(QLabel):
            style = label.styleSheet()
            for before, after in old.items():
                style = style.replace(before, after)
            label.setStyleSheet(style)
        for widget in self.findChildren(QWidget):
            style = widget.styleSheet()
            for before, after in old.items():
                style = style.replace(before, after)
            if style:
                widget.setStyleSheet(style)
            widget.update()
        self.update()

    def set_stats(self, total, processing, verified, pending):
        self.panel.stats.set_values(total, processing, verified, pending)

    def set_badge(self, key: str, text: str):
        if key in self.cards:
            self.cards[key].set_badge(text)

    def set_today_tasks(self, rows):
        self.panel.set_today_tasks(rows)

    def set_upcoming(self, rows):
        self.panel.set_upcoming(rows)


# ----------------------------------------------------------------------------
# Preview
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    page = DashboardPage()
    page.module_selected.connect(lambda k: print("MODULE:", k))
    page.user_clicked.connect(lambda: print("USER CHIP clicked"))
    page.see_all_upcoming.connect(lambda: print("SEE ALL upcoming clicked"))
    page.resize(1210, 760)
    page.setWindowTitle("ATLAS - Dashboard")
    page.show()
    sys.exit(app.exec())
