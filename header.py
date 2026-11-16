"""
ATLAS - Shared header  (components/header.py)

Use it on any page:

    from components.header import AppHeader

    self.header = AppHeader()
    self.header.set_user("Dr. Amzar Najmi", "Neuroradiology")
    self.header.set_photo(pixmap)            # photo from the database (QPixmap, or None)
    self.header.logout_clicked.connect(...)
    self.header.settings_clicked.connect(...)
    layout.addWidget(self.header)

Preview on its own:  python components\\header.py
"""
import math
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from theme.theme import (
    MONO, SANS, TITLE_FONT, CYAN,
    SHELL_BG_TOP, SHELL_BG_BOTTOM, SHELL_BORDER, SHELL_ACCENT,
    SHELL_TEXT, SHELL_TEXT_DIM,
    find_logo, load_custom_fonts, make_font, make_label, vline,
)

# PURPLE HEADER THEME
CYAN = "#A78BFA"

SHELL_BG_TOP = "#100B20"
SHELL_BG_BOTTOM = "#19112E"
SHELL_BORDER = "#49336F"
SHELL_ACCENT = "#A78BFA"
SHELL_TEXT_DIM = "#A99ACB"

# ============================================================================
#  >>>  HEADER SETTINGS - EDIT HERE  <<<
# ============================================================================
# Logos live in the project's assets/ folder. Type the START of the file name.
LOGO_NAME = "Atlas_Bulat"     # logo 1 (ATLAS emblem, with corner brackets)
LOGO_HEIGHT = 44
LOGO2_NAME = "Unikl_Bulat"    # logo 2 (set "" to hide). Other option: "Unikl_Logo"
LOGO2_HEIGHT = 52

# Title font - "cinematic". See theme/theme.py for how to install Orbitron.
TITLE_TEXT = "Ai-driven Tumor Localization and Analysis System"
TITLE_SIZE = 15
TITLE_SPACING = 2.0           # letter spacing (wider = more cinematic)
TITLE_UPPERCASE = False       # True = ALL CAPS
SUBTITLE_TEXT = "Medical Imaging Intelligence"

# No bundled/default profile photo is used. Users can upload one in Settings.
PROFILE_PHOTO_SIZE = 46
# ============================================================================


def tight(label: QLabel) -> QLabel:
    """Keep a label at its natural height (no stretching)."""
    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    return label


class PlainLogo(QLabel):
    """A logo image with no frame. Hidden if the file isn't found."""

    def __init__(self, name: str, height: int, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        path = find_logo(name) if name else None
        pm = QPixmap(path) if path else QPixmap()
        if pm.isNull():
            self.hide()
        else:
            self.setPixmap(pm.scaledToHeight(height, Qt.SmoothTransformation))


class LogoBox(QWidget):
    """Logo with corner brackets and a small dot (top-right)."""
    PAD = 10

    def __init__(self, name: str, height: int, parent=None):
        super().__init__(parent)
        path = find_logo(name)
        self.pm = QPixmap(path) if path else QPixmap()
        if not self.pm.isNull():
            self.pm = self.pm.scaledToHeight(height, Qt.SmoothTransformation)
            self.setFixedSize(self.pm.width() + 2 * self.PAD,
                              self.pm.height() + 2 * self.PAD)
        else:
            self.setFixedSize(64, 64)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self.pm.isNull():
            p.setPen(QColor(SHELL_TEXT))
            p.setFont(make_font(SANS, 11, QFont.Light, 2))
            p.drawText(self.rect(), Qt.AlignCenter, "ATLAS")
        else:
            p.drawPixmap(self.PAD, self.PAD, self.pm)
        a = 9
        p.setPen(QPen(QColor("#a9bdd6"), 1.2))
        p.drawLine(1, 1, 1 + a, 1)
        p.drawLine(1, 1, 1, 1 + a)
        p.drawLine(w - 1, h - 1, w - 1 - a, h - 1)
        p.drawLine(w - 1, h - 1, w - 1, h - 1 - a)
        p.setPen(Qt.NoPen)
        p.setBrush(CYAN)
        p.drawEllipse(QPointF(w - 3, 4), 2, 2)
        p.end()


class SettingsButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Settings")
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
        color = QColor(SHELL_ACCENT) if self._hover else QColor("#a9bdd6")

        # gear only — no box
        cx, cy = 17.0, 17.0
        pts = []
        for i in range(8):
            base = i * 45
            for ang, r in ((-17, 5.2), (-10, 8.0), (10, 8.0), (17, 5.2)):
                a = math.radians(base + ang)
                pts.append(QPointF(cx + math.cos(a) * r, cy + math.sin(a) * r))
        p.setPen(QPen(color, 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF(pts))
        p.drawEllipse(QPointF(cx, cy), 2.6, 2.6)
        p.end()


class Avatar(QWidget):
    """Profile photo, left blank until the user uploads one in Settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(PROFILE_PHOTO_SIZE, PROFILE_PHOTO_SIZE)
        self.db_photo = None

    def set_photo(self, pixmap):
        """Photo from the database (QPixmap), or None to show the empty avatar."""
        self.db_photo = pixmap if (pixmap is not None and not pixmap.isNull()) else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = PROFILE_PHOTO_SIZE
        rect = QRectF(0.5, 0.5, s - 1, s - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 4, 4)
        p.setClipPath(path)

        photo = self.db_photo
        if photo is not None and not photo.isNull():
            scaled = photo.scaled(s, s, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (s - scaled.width()) // 2
            y = (s - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        else:
            p.setBrush(QColor("#162540"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 4, 4)

        p.setClipping(False)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#33568a"), 1))
        p.drawRoundedRect(rect, 4, 4)
        p.end()


class LogoutButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(96, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Log out")
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
        color = QColor(SHELL_ACCENT) if self._hover else QColor("#d5e4f4")

        # door + arrow (log out) — no box
        cx, cy = 12.0, 17.0
        p.setPen(QPen(color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(cx - 7, cy - 7, 9, 14), 1.4, 1.4)
        p.drawLine(QPointF(cx + 1, cy), QPointF(cx + 10, cy))
        p.drawLine(QPointF(cx + 6.5, cy - 3.2), QPointF(cx + 10, cy))
        p.drawLine(QPointF(cx + 6.5, cy + 3.2), QPointF(cx + 10, cy))

        p.setPen(color)
        p.setFont(make_font(MONO, 10, QFont.Bold, 1.0))
        p.drawText(QRectF(26, 0, 70, 34), Qt.AlignVCenter | Qt.AlignLeft, "LOGOUT")
        p.end()


class AppHeader(QWidget):
    user_clicked = Signal()          # kept only so older code that connects it does not crash
    settings_clicked = Signal()
    logout_clicked = Signal()
    HEIGHT = 80

    def __init__(self, user_name="User", department="", parent=None):
        super().__init__(parent)
        load_custom_fonts()
        self.setFixedHeight(self.HEIGHT)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(36, 0, 12, 0)
        lay.setSpacing(12)

        # ---- logos (UniKL first, ATLAS second) ----
        lay.addWidget(PlainLogo(LOGO2_NAME, LOGO2_HEIGHT), 0, Qt.AlignVCenter)
        lay.addWidget(LogoBox(LOGO_NAME, LOGO_HEIGHT), 0, Qt.AlignVCenter)
        lay.addWidget(vline(34), 0, Qt.AlignVCenter)

        # ---- titles ----
        texts = QVBoxLayout()
        texts.setSpacing(4)
        texts.addStretch(1)
        texts.addWidget(tight(make_label(SUBTITLE_TEXT, MONO, 11, SHELL_TEXT_DIM,
                                         spacing=1.4)))
        title = TITLE_TEXT.upper() if TITLE_UPPERCASE else TITLE_TEXT
        texts.addWidget(tight(make_label(title, TITLE_FONT, TITLE_SIZE, SHELL_TEXT,
                                         QFont.Medium, TITLE_SPACING)))
        texts.addStretch(1)
        lay.addLayout(texts)
        lay.addStretch(1)

        # ---- settings ----
        self.settings_btn = SettingsButton()
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        lay.addWidget(self.settings_btn, 0, Qt.AlignVCenter)
        lay.addSpacing(2)
        lay.addWidget(vline(34), 0, Qt.AlignVCenter)

        # ---- user chip (photo + name; not a logout control) ----
        chip = QWidget()
        chip_lay = QHBoxLayout(chip)
        chip_lay.setContentsMargins(6, 0, 4, 0)
        chip_lay.setSpacing(10)
        self.avatar = Avatar()
        chip_lay.addWidget(self.avatar, 0, Qt.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(3)
        self.name_label = tight(make_label("", MONO, 11, SHELL_TEXT, QFont.Bold, 1.0))
        self.dept_label = tight(make_label("", MONO, 8, SHELL_TEXT_DIM, spacing=1.4))
        info.addStretch(1)
        info.addWidget(self.name_label)
        info.addWidget(self.dept_label)
        info.addStretch(1)
        chip_lay.addLayout(info)
        lay.addWidget(chip, 0, Qt.AlignVCenter)

        self.logout_btn = LogoutButton()
        self.logout_btn.clicked.connect(self.logout_clicked.emit)
        lay.addWidget(self.logout_btn, 0, Qt.AlignVCenter)

        self.set_user(user_name, department)

    # ---- public API ----
    def set_user(self, full_name: str, department: str = ""):
        self.name_label.setText(full_name.upper())
        self.dept_label.setText(department.upper())

    def set_photo(self, pixmap):
        """Profile photo from the database (QPixmap, or None for the fallback picture)."""
        self.avatar.set_photo(pixmap)

    # ---- painting: navy band + glowing accent line on the bottom edge ----
    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(SHELL_BG_TOP))
        g.setColorAt(1, QColor(SHELL_BG_BOTTOM))
        p.fillRect(self.rect(), g)

        p.setPen(QPen(QColor(SHELL_BORDER), 1))
        p.drawLine(0, h - 1, w, h - 1)

        ag = QLinearGradient(0, 0, w, 0)
        a0 = QColor(SHELL_ACCENT); a0.setAlpha(0)
        a1 = QColor(SHELL_ACCENT); a1.setAlpha(190)
        a2 = QColor(SHELL_ACCENT); a2.setAlpha(0)
        ag.setColorAt(0.0, a0)
        ag.setColorAt(0.18, a1)
        ag.setColorAt(0.60, a2)
        ag.setColorAt(1.0, a2)
        p.fillRect(QRectF(0, h - 2, w, 2), ag)
        p.end()


# ----------------------------------------------------------------------------
# Preview
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    box = QWidget()
    box.setStyleSheet("background: #04050a;")
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    header = AppHeader("Dr. Amzar Najmi", "Neuroradiology")
    header.logout_clicked.connect(lambda: print("LOGOUT clicked"))
    header.settings_clicked.connect(lambda: print("SETTINGS clicked"))
    v.addWidget(header)
    v.addStretch(1)
    box.resize(1300, 300)
    box.setWindowTitle("AppHeader preview")
    box.show()
    sys.exit(app.exec())
