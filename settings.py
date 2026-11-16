"""
ATLAS - User Profile & Settings page  (interfaces/settings.py)

Sections (as in the design):
    01 PROFILE IDENTITY   avatar (click the camera to upload / remove a photo), name, role, staff ID, email
    02 PERSONAL INFORMATION   editable profile with Cancel / Save Changes
    03 PERSONAL TASKS     title, description, date, time, note -> ADD PERSONAL TASK
    Dark / Light switch (top right)

Signals (main.py connects them to the database):
    back_requested()                "Dashboard" button
    logout_clicked()                LOGOUT button in the header
    theme_toggled(dark: bool)       dark / light switch
    profile_save_requested(dict)    keys: full_name, email, phone, department
    photo_selected(object)          PNG bytes (256 x 256), or None when the photo is removed
    task_add_requested(dict)        keys: title, description, due_date, due_time, note

Methods main.py calls back:
    set_user(name, dept)   set_profile(dict)   set_photo_bytes(bytes | None)
    notify_profile(text, ok)   notify_task(text, ok)   clear_task_form()   set_dark_mode(bool)
"""
import math
import os
import re
import sys
from datetime import date, time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import (
    QBuffer, QByteArray, QDate, QEasingCurve, QIODevice, QPoint, QPointF, QRectF, QSize, Qt,
    QTime, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListView, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QTimeEdit, QVBoxLayout, QWidget,
)

from components.footer import AppFooter
from components.header import AppHeader
from theme.theme import MONO, SANS, find_logo, make_font, make_label

# ----------------------------------------------------------------------------
# Palette (dark violet slate to match the shared header and footer)
# ----------------------------------------------------------------------------
BG = QColor("#080811")
CYAN = "#A78BFA"              # violet accent shared with the header and footer
CYAN_Q = QColor(CYAN)
TEXT = "#e8eef2"
MUTED = "#A99ACB"
FAINT = "#786A99"
LINE = "#302747"
FIELD_BG = "#090812"
FIELD_LINE = "#33294A"
ERROR = "#ff7b8a"
LIGHT_MODE = False

PHOTO_PX = 256                      # stored photo size
MAX_PHOTO_FILE = 15 * 1024 * 1024   # refuse files bigger than 15 MB


# ----------------------------------------------------------------------------
# Icons (drawn with QPainter, no image files needed)
# ----------------------------------------------------------------------------
def draw_icon(p: QPainter, kind: str, cx: float, cy: float, size: float, color: QColor):
    p.save()
    p.translate(cx - size / 2, cy - size / 2)
    p.scale(size / 20.0, size / 20.0)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    if kind == "camera":
        p.drawRoundedRect(QRectF(2, 6, 16, 11), 2, 2)
        bump = QPainterPath()
        bump.moveTo(7, 6)
        bump.lineTo(8.3, 3.6)
        bump.lineTo(11.7, 3.6)
        bump.lineTo(13, 6)
        p.drawPath(bump)
        p.drawEllipse(QPointF(10, 11.5), 3.2, 3.2)
    elif kind == "calendar":
        p.drawRoundedRect(QRectF(3, 4.5, 14, 12.5), 2, 2)
        p.drawLine(QPointF(3, 8.5), QPointF(17, 8.5))
        p.drawLine(QPointF(7, 2.5), QPointF(7, 6))
        p.drawLine(QPointF(13, 2.5), QPointF(13, 6))
    elif kind == "clock":
        p.drawEllipse(QPointF(10, 10), 7.5, 7.5)
        p.drawLine(QPointF(10, 5.5), QPointF(10, 10))
        p.drawLine(QPointF(10, 10), QPointF(13, 12))
    elif kind == "save":
        p.drawRoundedRect(QRectF(3, 3, 14, 14), 2, 2)
        p.drawRect(QRectF(6, 3, 7, 4.5))
        p.drawRect(QRectF(6, 11, 8, 6))
    elif kind == "back":
        p.drawLine(QPointF(16, 10), QPointF(4, 10))
        p.drawLine(QPointF(4, 10), QPointF(9, 5))
        p.drawLine(QPointF(4, 10), QPointF(9, 15))
    elif kind == "moon":
        moon = QPainterPath()
        moon.addEllipse(QPointF(10, 10), 6.5, 6.5)
        cut = QPainterPath()
        cut.addEllipse(QPointF(13.2, 8), 5.6, 5.6)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPath(moon.subtracted(cut))
    elif kind == "sun":
        p.drawEllipse(QPointF(10, 10), 3.4, 3.4)
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(10 + math.cos(a) * 5.8, 10 + math.sin(a) * 5.8),
                       QPointF(10 + math.cos(a) * 8.2, 10 + math.sin(a) * 8.2))
    p.restore()


def make_icon(kind: str, color: str = CYAN) -> QIcon:
    pm = QPixmap(48, 48)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_icon(p, kind, 24, 24, 44, QColor(color))
    p.end()
    return QIcon(pm)


class IconLabel(QWidget):
    def __init__(self, kind: str, size=18, color=CYAN, parent=None):
        super().__init__(parent)
        self.kind, self.color = kind, QColor(color)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QPainter(self)
        draw_icon(p, self.kind, self.width() / 2, self.height() / 2, self.width(), self.color)
        p.end()


# ----------------------------------------------------------------------------
# Cards, labels, inputs
# ----------------------------------------------------------------------------
class Card(QFrame):
    def __init__(self, radius=0, parent=None):
        super().__init__(parent)
        self.radius = radius

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, 0, h)
        if LIGHT_MODE:
            g.setColorAt(0, QColor("#ffffff"))
            g.setColorAt(1, QColor("#f5f1fb"))
        else:
            g.setColorAt(0, QColor(19, 14, 32, 242))
            g.setColorAt(1, QColor(11, 10, 20, 242))
        p.setBrush(g)
        p.setPen(QPen(QColor(LINE), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), self.radius, self.radius)
        p.end()


def hline():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {LINE};")
    return f


def section_header(number: str, title: str) -> QWidget:
    """'01  PROFILE IDENTITY' - cyan number + muted title."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addWidget(make_label(number, MONO, 11, CYAN, QFont.Bold, 2))
    lay.addWidget(make_label(title, MONO, 11, MUTED, spacing=2.4))
    lay.addStretch(1)
    return box


def field_label(text: str, color=MUTED, star=False) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    lay.addWidget(make_label(text, MONO, 10, color, QFont.Bold if color == CYAN else QFont.Normal, 1.8))
    if star:
        lay.addWidget(make_label("\u2605", MONO, 10, CYAN))
    lay.addStretch(1)
    return box


INPUT_QSS = f"""
    QLineEdit, QPlainTextEdit {{
        background: {FIELD_BG}; border: 1px solid {FIELD_LINE}; border-radius: 2px;
        padding: 0 12px; color: {TEXT}; selection-background-color: #5d438a;
    }}
    QPlainTextEdit {{ padding: 8px 12px; }}
    QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {CYAN}; }}
"""


def make_line_edit(placeholder="", value="", height=44, px=14) -> QLineEdit:
    e = QLineEdit(value)
    e.setPlaceholderText(placeholder)
    e.setFixedHeight(height)
    e.setFont(make_font(MONO, px))
    return e


class DepartmentCombo(QComboBox):
    """Department selector styled to match the registration dropdown."""
    DEPARTMENTS = [
        "Radiology", "Oncology", "Neurology", "Neurosurgery",
        "Pathology", "Internal Medicine", "Biomedical / IT",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setView(QListView())
        self.addItem("Select department")
        self.model().item(0).setEnabled(False)
        self.addItems(self.DEPARTMENTS)
        self.setCurrentIndex(0)
        self.setProperty("placeholder", True)
        self.setFixedHeight(44)
        self.setFont(make_font(MONO, 14))
        self.refresh_theme()
        self.currentIndexChanged.connect(self._refresh_placeholder)

    def refresh_theme(self):
        popup_bg = "#ffffff" if LIGHT_MODE else "#100d1b"
        selected = "#e8def7" if LIGHT_MODE else "#342350"
        self.setStyleSheet(f"""
            QComboBox {{
                background: {FIELD_BG}; border: 1px solid {FIELD_LINE}; border-radius: 2px;
                padding: 0 12px; color: {TEXT};
            }}
            QComboBox[placeholder="true"] {{ color: {FAINT}; }}
            QComboBox:focus, QComboBox:on {{ border: 1px solid {CYAN}; }}
            QComboBox::drop-down {{ border: none; width: 34px; }}
            QComboBox::down-arrow {{ image: none; }}
            QComboBox QAbstractItemView {{
                background: {popup_bg}; border: 1px solid {FIELD_LINE}; outline: 0;
                color: {TEXT}; selection-background-color: {selected};
                selection-color: {TEXT};
            }}
            QComboBox QAbstractItemView::item {{ padding: 6px 10px; min-height: 22px; }}
            QComboBox QAbstractItemView::item:disabled {{ color: {FAINT}; }}
        """)
        self.update()

    def _refresh_placeholder(self):
        self.setProperty("placeholder", self.currentIndex() == 0)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_value(self, department: str):
        department = (department or "").strip()
        if not department:
            self.setCurrentIndex(0)
            return
        index = self.findText(department, Qt.MatchFixedString)
        if index < 0:
            self.addItem(department)
            index = self.count() - 1
        self.setCurrentIndex(index)

    def value(self) -> str:
        return "" if self.currentIndex() <= 0 else self.currentText().strip()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = CYAN_Q if self.hasFocus() else QColor(MUTED)
        cx, cy = self.width() - 16, self.height() / 2
        p.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))
        p.end()


class IconField(QFrame):
    """A bordered field with an icon on the left (used for the date / time pickers)."""
    EDITOR_QSS = f"""
        QDateEdit, QTimeEdit {{ background: transparent; border: none; color: {TEXT};
                               selection-background-color: #5d438a; }}
        QDateEdit::drop-down {{ width: 18px; border: none; }}
        QDateEdit::down-arrow {{ image: none; }}
        QTimeEdit::up-button, QTimeEdit::down-button {{ width: 0px; height: 0px; border: none; }}
    """

    def __init__(self, icon: str, editor, chevron=False, parent=None):
        super().__init__(parent)
        self.chevron = chevron
        self.editor = editor
        self._focus = False
        self.setFixedHeight(38)
        self.refresh_theme()
        editor.setFont(make_font(MONO, 11))
        editor.installEventFilter(self)
        try:                                       # the text part of the spin box also reports focus
            inner = editor.lineEdit()
            if inner is not None:
                inner.installEventFilter(self)
        except Exception:
            pass
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 4, 0)
        lay.setSpacing(8)
        lay.addWidget(IconLabel(icon, 16))
        lay.addWidget(editor, 1)

    def refresh_theme(self):
        editor_bg = "#ffffff" if LIGHT_MODE else "transparent"
        self.editor.setStyleSheet(f"""
            QDateEdit, QTimeEdit {{ background: {editor_bg}; border: none; color: {TEXT};
                                   selection-background-color: #8b69cb; }}
            QDateEdit::drop-down {{ width: 18px; border: none; }}
            QDateEdit::down-arrow {{ image: none; }}
            QTimeEdit::up-button, QTimeEdit::down-button {{ width: 0px; height: 0px; border: none; }}
        """)
        self.update()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn:
            self._focus = True
            self.update()
        elif event.type() == event.Type.FocusOut:
            self._focus = False
            self.update()
        return super().eventFilter(obj, event)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(FIELD_BG))
        p.setPen(QPen(QColor(CYAN) if self._focus else QColor(FIELD_LINE), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 2, 2)
        if self.chevron:
            cx, cy = self.width() - 13, self.height() / 2
            p.setPen(QPen(QColor(MUTED), 1.3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(QPointF(cx - 3.5, cy - 1.5), QPointF(cx, cy + 2))
            p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 3.5, cy - 1.5))
        p.end()


# ----------------------------------------------------------------------------
# Avatar with camera button
# ----------------------------------------------------------------------------
class CameraButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Change profile photo")
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#eee8f7") if LIGHT_MODE and not self._hover else
                   QColor("#e1d8f1") if LIGHT_MODE else
                   QColor("#201733") if not self._hover else QColor("#342350"))
        p.setPen(QPen(CYAN_Q, 1.5))
        p.drawEllipse(QRectF(1, 1, 32, 32))
        draw_icon(p, "camera", 17, 17, 17, CYAN_Q)
        p.end()


class AvatarCircle(QWidget):
    SIZE = 140

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.initials = "U"
        self.photo = None
        self.cam = CameraButton(self)
        self.cam.move(100, 98)

    def set_initials(self, text):
        self.initials = text
        self.update()

    def set_photo(self, pixmap):
        if pixmap is None or pixmap.isNull():
            self.photo = None
        else:
            self.photo = pixmap.scaled(PHOTO_PX, PHOTO_PX, Qt.KeepAspectRatioByExpanding,
                                       Qt.SmoothTransformation)
        self.update()

    def has_photo(self) -> bool:
        return self.photo is not None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.SIZE / 2 - 4, self.SIZE / 2 - 4)
        r = 54

        glow = QRadialGradient(c, r + 16)                    # soft violet glow
        glow.setColorAt(0.6, QColor(112, 72, 184, 35 if LIGHT_MODE else 60))
        glow.setColorAt(1.0, QColor(112, 72, 184, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, r + 16, r + 16)

        circle = QPainterPath()
        circle.addEllipse(c, r, r)
        if self.photo is not None:
            p.save()
            p.setClipPath(circle)
            side = min(self.photo.width(), self.photo.height())
            p.drawPixmap(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), self.photo,
                         QRectF((self.photo.width() - side) / 2, (self.photo.height() - side) / 2,
                                side, side))
            p.restore()
        else:
            g = QLinearGradient(0, c.y() - r, 0, c.y() + r)
            g.setColorAt(0, QColor("#eee8f7" if LIGHT_MODE else "#251b39"))
            g.setColorAt(1, QColor("#dcd2eb" if LIGHT_MODE else "#100d1b"))
            p.setBrush(g)
            p.drawPath(circle)
            p.setPen(QColor(TEXT))
            p.setFont(make_font(MONO, 36, QFont.Bold, 3))
            p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, self.initials)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(112, 72, 184, 190 if LIGHT_MODE else 170), 1.5))
        p.drawEllipse(c, r, r)
        p.end()


# ----------------------------------------------------------------------------
# Dark / light switch
# ----------------------------------------------------------------------------
class ThemeSwitch(QWidget):
    toggled = Signal(bool)          # True = dark mode

    def __init__(self, dark=True, parent=None):
        super().__init__(parent)
        self.setFixedSize(210, 46)
        self.setCursor(Qt.PointingHandCursor)
        self._dark = dark
        self._pos = 1.0 if dark else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim.valueChanged.connect(self._on_anim)

    def set_dark(self, dark: bool, emit=False):
        if dark == self._dark:
            return
        self._dark = dark
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if dark else 0.0)
        self._anim.start()
        if emit:
            self.toggled.emit(dark)

    def _on_anim(self, v):
        self._pos = float(v)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.set_dark(not self._dark, emit=True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setBrush(QColor("#ffffff" if LIGHT_MODE else QColor(17, 13, 27, 230)))
        p.setPen(QPen(QColor("#d8cde8" if LIGHT_MODE else "#392c52"), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 2, 2)

        draw_icon(p, "moon" if self._dark else "sun", 26, h / 2, 17, CYAN_Q)
        p.setPen(QColor(MUTED))
        p.setFont(make_font(MONO, 10, QFont.Medium, 2))
        p.drawText(QRectF(46, 0, 100, h), Qt.AlignLeft | Qt.AlignVCenter,
                   "DARK MODE" if self._dark else "LIGHT MODE")

        tx, ty, tw, th = w - 62, h / 2 - 12, 46, 24          # switch track
        track = QColor(CYAN)
        track.setAlpha(int(40 + 90 * self._pos))
        p.setBrush(track)
        p.setPen(QPen(CYAN_Q if self._dark else QColor("#51436d"), 1))
        p.drawRoundedRect(QRectF(tx, ty, tw, th), th / 2, th / 2)
        kx = tx + 12 + self._pos * (tw - 24)
        p.setPen(Qt.NoPen)
        p.setBrush(CYAN_Q if self._dark else QColor("#a99acb"))
        p.drawEllipse(QPointF(kx, h / 2), 8, 8)
        p.end()


# ----------------------------------------------------------------------------
# Buttons
# ----------------------------------------------------------------------------
def outline_button(text: str, icon: str = "", cyan=False, height=44) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedHeight(height)
    b.setFont(make_font(MONO, 11, QFont.Bold, 1.8))
    if icon:
        b.setIcon(make_icon(icon, CYAN if cyan else MUTED))
        b.setIconSize(QSize(18, 18))
    if cyan:
        b.setStyleSheet(
            f"QPushButton {{ color: {CYAN}; background: rgba(167,139,250,18); border: 1px solid {CYAN};"
            " border-radius: 2px; padding: 0 22px; }"
            "QPushButton:hover { background: rgba(167,139,250,45); }"
            "QPushButton:pressed { background: rgba(167,139,250,70); }")
    else:
        b.setStyleSheet(
            f"QPushButton {{ color: {MUTED}; background: transparent; border: 1px solid #392c52;"
            " border-radius: 2px; padding: 0 22px; }"
            f"QPushButton:hover {{ color: {TEXT}; border: 1px solid #705a9c; }}")
    return b


class PillButton(QPushButton):
    """Glowing violet pill (ADD PERSONAL TASK)."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(220, 52)
        self.setFont(make_font(MONO, 10, QFont.Bold, 2))

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bw, bh = w - 16, 36
        r = QRectF((w - bw) / 2, (h - bh) / 2, bw, bh)
        for i in range(5):                                   # violet glow
            grow = 2 + i * 2.2
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(167, 139, 250, 18))
            p.drawRoundedRect(r.adjusted(-grow, -grow, grow, grow), bh / 2 + grow, bh / 2 + grow)
        if self.isDown():
            c0, c1 = "#7650d8", "#a78bfa"
        elif self._hover:
            c0, c1 = "#9a78f2", "#d1c4ff"
        else:
            c0, c1 = "#8b5cf6", "#c4b5fd"
        g = QLinearGradient(r.left(), 0, r.right(), 0)
        g.setColorAt(0, QColor(c0))
        g.setColorAt(1, QColor(c1))
        p.setBrush(g)
        p.drawRoundedRect(r, bh / 2, bh / 2)
        p.setFont(self.font())
        p.setPen(QColor("#160f24"))
        p.drawText(r, Qt.AlignCenter, self.text())
        p.end()


# ----------------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PAGE_QSS = f"""
    QCalendarWidget QWidget {{ background: #0a1018; color: {TEXT}; }}
    QCalendarWidget QAbstractItemView:enabled {{
        background: #0a1018; color: {TEXT};
        selection-background-color: #5d438a; selection-color: #ffffff; }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {FAINT}; }}
    QCalendarWidget QToolButton {{ background: transparent; color: {TEXT}; }}
    QCalendarWidget QToolButton:hover {{ background: #342350; }}
    QMenu {{ background: #0a1018; color: {TEXT}; border: 1px solid {LINE}; padding: 4px; }}
    QMenu::item {{ padding: 7px 22px; }}
    QMenu::item:selected {{ background: #342350; }}
    QMenu::item:disabled {{ color: {FAINT}; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #49366d; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


class SettingsPage(QWidget):
    back_requested = Signal()
    logout_clicked = Signal()        # LOGOUT button in the header
    user_clicked = Signal()          # same event, kept so older main.py code still works
    theme_toggled = Signal(bool)
    profile_save_requested = Signal(dict)
    photo_selected = Signal(object)
    task_add_requested = Signal(dict)

    # Set to False to hide the dark / light switch.
    SHOW_THEME_SWITCH = True

    def __init__(self, parent=None):
        super().__init__(parent)
        icon_path = find_logo("Atlas_Bulat")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(1100, 700)
        self._snapshot = {"full_name": "", "email": "", "phone": "", "department": ""}
        self._build()

    # ---- background: dark slate + soft glows + faint grid ------------------
    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), BG)
        for cx, cy, rad, col in ((0, h * 0.35, w * 0.35, QColor(93, 57, 150, 58)),
                                 (w, h * 0.8, w * 0.32, QColor(81, 45, 120, 48))):
            g = QRadialGradient(QPointF(cx, cy), rad)
            g.setColorAt(0, col)
            c2 = QColor(col)
            c2.setAlpha(0)
            g.setColorAt(1, c2)
            p.fillRect(self.rect(), g)
        p.setPen(QPen(QColor(167, 139, 250, 11), 1))
        for x in range(0, w, 44):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 44):
            p.drawLine(0, y, w, y)
        p.end()

    # ---- UI ----------------------------------------------------------------
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = AppHeader()
        self.header.logout_clicked.connect(self.logout_clicked.emit)
        self.header.logout_clicked.connect(self.user_clicked.emit)
        outer.addWidget(self.header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollArea > QWidget > QWidget { background: transparent; }")
        self._content = QWidget()
        self._content.setStyleSheet(PAGE_QSS)
        scroll.setWidget(self._content)
        outer.addWidget(scroll, 1)

        v = QVBoxLayout(self._content)
        v.setContentsMargins(34, 26, 34, 28)
        v.setSpacing(18)
        v.addLayout(self._build_title_row())

        body = QHBoxLayout()
        body.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(18)
        left.addWidget(self._build_identity_card())
        left.addWidget(self._build_info_card(), 1)
        body.addLayout(left, 1)
        body.addWidget(self._build_tasks_card())
        v.addLayout(body, 1)

        self.footer = AppFooter()
        outer.addWidget(self.footer)

    def _build_title_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(6)
        crumb = QHBoxLayout()
        crumb.setSpacing(8)
        crumb.addWidget(make_label("SYS", MONO, 10, CYAN, QFont.Bold, 2))
        crumb.addWidget(make_label("/  ACCOUNT", MONO, 10, FAINT, spacing=2))
        crumb.addStretch(1)
        col.addLayout(crumb)
        col.addWidget(make_label("USER PROFILE & SETTINGS", MONO, 34, TEXT, QFont.Bold, 1.5))
        col.addWidget(make_label("Manage your personal information and workspace preferences.",
                                 SANS, 13, MUTED))
        row.addLayout(col, 1)

        back = outline_button("DASHBOARD", "back", height=46)
        back.clicked.connect(self.back_requested.emit)
        row.addWidget(back, 0, Qt.AlignTop)
        self.theme_switch = ThemeSwitch(dark=True)
        self.theme_switch.toggled.connect(self.set_theme)
        self.theme_switch.toggled.connect(self.theme_toggled.emit)
        self.theme_switch.setVisible(self.SHOW_THEME_SWITCH)
        row.addSpacing(10)
        row.addWidget(self.theme_switch, 0, Qt.AlignTop)
        return row

    # -- 01 profile identity --
    def _build_identity_card(self) -> QWidget:
        card = Card()
        lay = QHBoxLayout(card)
        lay.setContentsMargins(30, 26, 30, 26)
        lay.setSpacing(28)

        self.avatar = AvatarCircle()
        self.avatar.cam.clicked.connect(self._avatar_menu)
        lay.addWidget(self.avatar, 0, Qt.AlignVCenter)

        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(section_header("01", "PROFILE IDENTITY"))
        self.name_label = make_label("", MONO, 28, TEXT, QFont.Bold, 0.5)
        col.addWidget(self.name_label)
        meta = QHBoxLayout()
        meta.setSpacing(10)
        self.role_label = make_label("", MONO, 11, CYAN, QFont.Bold, 1.8)
        meta.addWidget(self.role_label)
        sep = QFrame()
        sep.setFixedSize(1, 14)
        sep.setStyleSheet(f"background: {LINE};")
        meta.addWidget(sep)
        self.id_label = make_label("", MONO, 11, MUTED, spacing=1.6)
        meta.addWidget(self.id_label)
        meta.addStretch(1)
        col.addLayout(meta)
        self.email_label = make_label("", SANS, 14, MUTED)
        col.addWidget(self.email_label)
        lay.addLayout(col, 1)
        return card

    # -- 02 personal information --
    def _build_info_card(self) -> QWidget:
        card = Card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(26, 24, 26, 24)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.addWidget(section_header("02", "PERSONAL INFORMATION"), 1)
        head.addWidget(make_label("\u2605 REQUIRED FIELDS", MONO, 9, FAINT, spacing=1.5,
                                  align=Qt.AlignRight))
        lay.addLayout(head)
        lay.addSpacing(6)
        lay.addWidget(make_label("Edit Profile", MONO, 22, TEXT, QFont.Bold, 0.5))
        lay.addSpacing(16)
        lay.addWidget(hline())
        lay.addSpacing(22)

        self.in_name = make_line_edit("Full name")
        self.in_email = make_line_edit("name@hospital.org")
        self.in_phone = make_line_edit("+60 xx xxx xxxx")
        self.in_dept = DepartmentCombo()
        for e in (self.in_name, self.in_email, self.in_phone):
            e.setStyleSheet(INPUT_QSS)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        for (label, star), widget, r, c in (
                (("FULL NAME", True), self.in_name, 0, 0),
                (("EMAIL ADDRESS", True), self.in_email, 0, 1),
                (("PHONE NUMBER", False), self.in_phone, 2, 0),
                (("DEPARTMENT", False), self.in_dept, 2, 1)):
            grid.addWidget(field_label(label, MUTED, star), r, c)
            grid.addWidget(widget, r + 1, c)
        lay.addLayout(grid)
        lay.addStretch(1)
        lay.addSpacing(18)
        lay.addWidget(hline())
        lay.addSpacing(18)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.profile_status = make_label("", SANS, 12, CYAN)
        buttons.addWidget(self.profile_status, 1)
        cancel = outline_button("CANCEL")
        cancel.clicked.connect(self._cancel_profile)
        save = outline_button("SAVE CHANGES", "save", cyan=True)
        save.clicked.connect(self._save_profile)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        lay.addLayout(buttons)
        return card

    # -- 03 personal tasks --
    def _build_tasks_card(self) -> QWidget:
        card = Card(radius=14)
        card.setFixedWidth(360)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 24, 24, 22)
        lay.setSpacing(0)

        lay.addWidget(section_header("03", "PERSONAL TASKS"))
        lay.addSpacing(4)
        lay.addWidget(make_label("Task Management", MONO, 18, TEXT, QFont.Bold, 0.5))
        lay.addSpacing(12)
        lay.addWidget(hline())
        lay.addSpacing(18)

        self.task_title = make_line_edit("Enter task title", height=40, px=12)
        self.task_desc = QPlainTextEdit()
        self.task_desc.setPlaceholderText("Add task details...")
        self.task_desc.setFixedHeight(76)
        self.task_desc.setFont(make_font(MONO, 12))
        self.task_note = make_line_edit("Optional note", height=40, px=12)
        for w in (self.task_title, self.task_desc, self.task_note):
            w.setStyleSheet(INPUT_QSS)

        self.task_date = QDateEdit()
        self.task_date.setCalendarPopup(True)
        self.task_date.setDisplayFormat("dd/MM/yyyy")
        self.task_date.setMinimumDate(QDate.currentDate().addDays(-1))
        self.task_date.setSpecialValueText("dd/mm/yyyy")
        self.task_date.setDate(self.task_date.minimumDate())
        self.task_time = QTimeEdit()
        self.task_time.setDisplayFormat("hh:mm AP")
        self.task_time.setMinimumTime(QTime(0, 0))
        self.task_time.setSpecialValueText("--:-- --")
        self.task_time.setTime(QTime(0, 0))
        self.task_time.setToolTip("Type the time or use the Up / Down keys")

        lay.addWidget(field_label("TASK TITLE", CYAN))
        lay.addSpacing(6)
        lay.addWidget(self.task_title)
        lay.addSpacing(14)
        lay.addWidget(field_label("DESCRIPTION", CYAN))
        lay.addSpacing(6)
        lay.addWidget(self.task_desc)
        lay.addSpacing(14)

        row = QHBoxLayout()
        row.setSpacing(12)
        for label, icon, editor, chev in (("DATE", "calendar", self.task_date, True),
                                          ("TIME", "clock", self.task_time, False)):
            col = QVBoxLayout()
            col.setSpacing(6)
            col.addWidget(field_label(label, CYAN))
            col.addWidget(IconField(icon, editor, chevron=chev))
            row.addLayout(col, 1)
        lay.addLayout(row)
        lay.addSpacing(14)
        lay.addWidget(field_label("NOTE", CYAN))
        lay.addSpacing(6)
        lay.addWidget(self.task_note)
        lay.addStretch(1)
        lay.addSpacing(10)

        self.task_status = make_label("", SANS, 12, CYAN, align=Qt.AlignHCenter)
        lay.addWidget(self.task_status)
        lay.addSpacing(6)
        add = PillButton("ADD PERSONAL TASK")
        add.clicked.connect(self._add_task)
        lay.addWidget(add, 0, Qt.AlignHCenter)
        return card

    # ---- public API (called by main.py) -------------------------------------
    def set_user(self, full_name: str, department: str = ""):
        self.header.set_user(full_name, department)

    def set_profile(self, profile: dict):
        """profile keys: full_name, email, phone, department, role, staff_id"""
        self._snapshot = {k: profile.get(k, "") for k in ("full_name", "email", "phone", "department")}
        self.in_name.setText(self._snapshot["full_name"])
        self.in_email.setText(self._snapshot["email"])
        self.in_phone.setText(self._snapshot["phone"])
        self.in_dept.set_value(self._snapshot["department"])
        self._refresh_identity(profile)
        self.profile_status.setText("")

    def _refresh_identity(self, profile: dict):
        name = profile.get("full_name", "")
        self.name_label.setText(name)
        self.role_label.setText((profile.get("role") or "STAFF").upper())
        sid = profile.get("staff_id") or ""
        self.id_label.setText(f"STAFF ID \u00b7 {sid}" if sid else "")
        self.email_label.setText(profile.get("email", ""))
        parts = [w for w in name.replace(".", " ").split()
                 if w.lower() not in ("dr", "prof", "mr", "ms", "mrs")]
        self.avatar.set_initials("".join(w[0] for w in parts[:2]).upper() or "U")

    def set_photo_bytes(self, data):
        """data = PNG/JPEG bytes from the database, or None."""
        pm = QPixmap()
        if data and pm.loadFromData(bytes(data)):
            self.avatar.set_photo(pm)
            self.header.set_photo(pm)
        else:
            self.avatar.set_photo(None)
            self.header.set_photo(None)

    def notify_profile(self, text: str, ok: bool = True):
        self.profile_status.setStyleSheet(f"color: {CYAN if ok else ERROR}; background: transparent;")
        self.profile_status.setText(text)

    def notify_task(self, text: str, ok: bool = True):
        self.task_status.setStyleSheet(f"color: {CYAN if ok else ERROR}; background: transparent;")
        self.task_status.setText(text)

    def clear_task_form(self):
        self.task_title.clear()
        self.task_desc.clear()
        self.task_note.clear()
        self.task_date.setDate(self.task_date.minimumDate())
        self.task_time.setTime(QTime(0, 0))

    def set_dark_mode(self, dark: bool):
        self.set_theme(dark)

    def set_theme(self, dark: bool):
        """Apply dark or light colors to the Settings page and its controls."""
        global BG, CYAN, CYAN_Q, TEXT, MUTED, FAINT, LINE, FIELD_BG, FIELD_LINE, LIGHT_MODE
        global INPUT_QSS, PAGE_QSS

        light = not dark
        if LIGHT_MODE == light:
            self.theme_switch.set_dark(dark)
            return

        old_colors = {
            TEXT: "#20182E" if light else "#e8eef2",
            MUTED: "#655D75" if light else "#A99ACB",
            FAINT: "#857D95" if light else "#786A99",
            CYAN: "#7048B8" if light else "#A78BFA",
        }
        LIGHT_MODE = light
        BG = QColor("#f3f0f8" if light else "#080811")
        CYAN = "#7048B8" if light else "#A78BFA"
        CYAN_Q = QColor(CYAN)
        TEXT = "#20182E" if light else "#e8eef2"
        MUTED = "#655D75" if light else "#A99ACB"
        FAINT = "#857D95" if light else "#786A99"
        LINE = "#d8d0e3" if light else "#302747"
        FIELD_BG = "#ffffff" if light else "#090812"
        FIELD_LINE = "#c9bedb" if light else "#33294A"

        INPUT_QSS = f"""
            QLineEdit, QPlainTextEdit {{
                background: {FIELD_BG}; border: 1px solid {FIELD_LINE}; border-radius: 2px;
                padding: 0 12px; color: {TEXT}; selection-background-color: #8b69cb;
            }}
            QPlainTextEdit {{ padding: 8px 12px; }}
            QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {CYAN}; }}
        """
        surface = "#ffffff" if light else "#0a1018"
        hover = "#e8e1f1" if light else "#342350"
        PAGE_QSS = f"""
            QCalendarWidget QWidget {{ background: {surface}; color: {TEXT}; }}
            QCalendarWidget QAbstractItemView:enabled {{
                background: {surface}; color: {TEXT};
                selection-background-color: {hover}; selection-color: {TEXT}; }}
            QCalendarWidget QAbstractItemView:disabled {{ color: {FAINT}; }}
            QCalendarWidget QToolButton {{ background: transparent; color: {TEXT}; }}
            QCalendarWidget QToolButton:hover {{ background: {hover}; }}
            QMenu {{ background: {surface}; color: {TEXT}; border: 1px solid {LINE}; padding: 4px; }}
            QMenu::item {{ padding: 7px 22px; }}
            QMenu::item:selected {{ background: {hover}; }}
            QMenu::item:disabled {{ color: {FAINT}; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 4px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """

        for label in self.findChildren(QLabel):
            style = label.styleSheet()
            for old, new in old_colors.items():
                style = style.replace(old, new)
            label.setStyleSheet(style)

        for editor in (self.in_name, self.in_email, self.in_phone,
                       self.task_title, self.task_desc, self.task_note):
            editor.setStyleSheet(INPUT_QSS)
        self.in_dept.refresh_theme()
        for field in self.findChildren(IconField):
            field.refresh_theme()
        self._content.setStyleSheet(PAGE_QSS)

        for button in self.findChildren(QPushButton):
            if button.text() == "SAVE CHANGES":
                self._style_outline_button(button, accent=True)
            elif button.text() in ("CANCEL", "DASHBOARD"):
                self._style_outline_button(button, accent=False)

        self.theme_switch.set_dark(dark)
        for widget in self.findChildren(QWidget):
            widget.update()
        self.update()

    @staticmethod
    def _style_outline_button(button: QPushButton, accent=False):
        if accent:
            button.setStyleSheet(
                f"QPushButton {{ color: {CYAN}; background: rgba(112,72,184,18); border: 1px solid {CYAN};"
                " border-radius: 2px; padding: 0 22px; }"
                "QPushButton:hover { background: rgba(112,72,184,45); }"
                "QPushButton:pressed { background: rgba(112,72,184,70); }")
        else:
            button.setStyleSheet(
                f"QPushButton {{ color: {MUTED}; background: transparent; border: 1px solid {LINE};"
                " border-radius: 2px; padding: 0 22px; }"
                f"QPushButton:hover {{ color: {TEXT}; border: 1px solid {CYAN}; }}")

    # ---- actions -------------------------------------------------------------
    def _save_profile(self):
        name = self.in_name.text().strip()
        email = self.in_email.text().strip()
        if not name:
            self.notify_profile("Full name is required.", False)
            return
        if not EMAIL_RE.match(email):
            self.notify_profile("Please enter a valid email address.", False)
            return
        self.notify_profile("Saving...", True)
        self.profile_save_requested.emit({
            "full_name": name, "email": email,
            "phone": self.in_phone.text().strip(), "department": self.in_dept.value(),
        })

    def _cancel_profile(self):
        self.in_name.setText(self._snapshot["full_name"])
        self.in_email.setText(self._snapshot["email"])
        self.in_phone.setText(self._snapshot["phone"])
        self.in_dept.set_value(self._snapshot["department"])
        self.profile_status.setText("")

    def _add_task(self):
        title = self.task_title.text().strip()
        if not title:
            self.notify_task("Please enter a task title.", False)
            self.task_title.setFocus()
            return
        d = self.task_date.date()
        due = date.today() if d <= self.task_date.minimumDate() else date(d.year(), d.month(), d.day())
        t = self.task_time.time()
        due_time = None if t == QTime(0, 0) else time(t.hour(), t.minute())
        self.notify_task("Saving...", True)
        self.task_add_requested.emit({
            "title": title,
            "description": self.task_desc.toPlainText().strip(),
            "due_date": due, "due_time": due_time,
            "note": self.task_note.text().strip(),
        })

    # ---- profile photo ---------------------------------------------------------
    def _avatar_menu(self):
        menu = QMenu(self)
        upload = menu.addAction("Upload new photo...")
        remove = menu.addAction("Remove photo")
        remove.setEnabled(self.avatar.has_photo())
        chosen = menu.exec(self.avatar.cam.mapToGlobal(QPoint(0, self.avatar.cam.height())))
        if chosen is upload:
            self._choose_photo()
        elif chosen is remove:
            self.set_photo_bytes(None)
            self.photo_selected.emit(None)

    def _choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a profile photo", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        if os.path.getsize(path) > MAX_PHOTO_FILE:
            self.notify_profile("That image is too large (maximum 15 MB).", False)
            return
        img = QImage(path)
        if img.isNull():
            self.notify_profile("That file could not be opened as an image.", False)
            return
        side = min(img.width(), img.height())                      # centre-crop to a square
        img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
        img = img.scaled(PHOTO_PX, PHOTO_PX, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        data = bytes(ba.data())
        self.set_photo_bytes(data)
        self.photo_selected.emit(data)


# ----------------------------------------------------------------------------
# Preview
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = find_logo("Atlas_Bulat")
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    page = SettingsPage()
    page.set_user("Dr. Amzar Najmi", "Neuroradiology")
    page.set_profile({"full_name": "Amzar Najmi", "email": "amzar@example.com", "phone": "012 345 6789",
                      "department": "Neuroradiology", "role": "Doctor", "staff_id": "ATL-0001"})
    page.profile_save_requested.connect(lambda d: (print("SAVE PROFILE:", d), page.notify_profile("Saved (preview).")))
    page.task_add_requested.connect(lambda d: (print("ADD TASK:", d), page.notify_task("Added (preview).")))
    page.photo_selected.connect(lambda b: print("PHOTO:", None if b is None else f"{len(b)} bytes"))
    page.theme_toggled.connect(lambda dark: print("THEME:", "dark" if dark else "light"))
    page.resize(1210, 860)
    page.setWindowTitle("ATLAS - Settings")
    page.show()
    sys.exit(app.exec())
