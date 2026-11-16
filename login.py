"""
ATLAS - Login Interface (standalone, outside the main shell)

Place at: interfaces/login.py
Run directly to preview:  python login.py

Hook into your app via the signals:
    login_requested(username, password)
    register_requested()
"""
import glob
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient, QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from theme.theme import TITLE_FONT, load_custom_fonts

# ============================================================================
#  >>>  LOGO SETTINGS - EDIT HERE  <<<
# ============================================================================
# The emblem image must be inside your project's  assets/  folder.
# Type the START of the file name below (no need for the extension).
LOGO_NAME = "Atlas_Bulat"     # emblem only (the round ATLAS symbol)
LOGO_HEIGHT = 64              # emblem height in pixels

# The "ATLAS" wordmark is live text in the cinematic title font
# (Orbitron - see theme/theme.py to install it). Set WORDMARK_TEXT = "" to hide it.
WORDMARK_TEXT = "ATLAS"
WORDMARK_SIZE = 40            # font size in pixels
WORDMARK_SPACING = 10         # letter spacing (wider = more cinematic)
# ============================================================================


def find_logo():
    """Search the assets folder for a file that starts with LOGO_NAME."""
    here = os.path.dirname(os.path.abspath(__file__))
    folders = [
        os.path.join(here, "..", "assets"),   # project_root/assets (login.py in interfaces/)
        os.path.join(here, "assets"),         # assets next to login.py
        os.path.join(os.getcwd(), "assets"),  # assets in the folder you ran python from
    ]
    for folder in folders:
        matches = glob.glob(os.path.join(folder, LOGO_NAME + "*"))
        matches = [m for m in matches if m.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
        if matches:
            return matches[0]
    print("[login] Logo not found. Looked in:")
    for f in folders:
        print("   ", os.path.abspath(f))
    return None


# ----------------------------------------------------------------------------
# Theme (move these into theme/ later if you want)
# ----------------------------------------------------------------------------
BG = QColor("#04050a")
CYAN = QColor("#3fd0e2")
CYAN_DIM = QColor("#12303a")
PURPLE = QColor("#7c5cff")
TEXT = "#e8eef2"
TEXT_DIM = "#5b6670"
TEXT_FAINT = "#46515a"
LIGHT_MODE = False

SANS = ["Inter", "Segoe UI", "Helvetica Neue", "Arial"]
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


# ----------------------------------------------------------------------------
# Small icon widget (drawn with QPainter so no image assets are needed)
# ----------------------------------------------------------------------------
class IconWidget(QWidget):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(44, 44)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(CYAN, 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2

        if self.kind == "user":
            p.drawEllipse(QPointF(cx, cy - 3.5), 3.6, 3.6)
            path = QPainterPath()
            path.moveTo(cx - 6.5, cy + 8)
            path.cubicTo(cx - 6.5, cy + 2, cx + 6.5, cy + 2, cx + 6.5, cy + 8)
            p.drawPath(path)
        else:  # key
            p.drawEllipse(QPointF(cx - 4, cy), 3.2, 3.2)
            p.drawLine(QPointF(cx - 0.8, cy), QPointF(cx + 7, cy))
            p.drawLine(QPointF(cx + 5, cy), QPointF(cx + 5, cy + 2.8))
            p.drawLine(QPointF(cx + 7, cy), QPointF(cx + 7, cy + 2.2))
        p.end()


# ----------------------------------------------------------------------------
# Input field: icon | divider | line edit, with corner tick
# ----------------------------------------------------------------------------
class AtlasField(QFrame):
    def __init__(self, icon_kind: str, placeholder: str, password=False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self._focused = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 12, 0)
        lay.setSpacing(0)

        lay.addWidget(IconWidget(icon_kind))

        divider = QFrame()
        divider.setFixedSize(1, 24)
        divider.setStyleSheet(f"background: {CYAN_DIM.name()};")
        lay.addWidget(divider)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFont(make_font(MONO, 12, spacing=1.0))
        if password:
            self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; color: {TEXT};"
            f" padding-left: 12px; selection-background-color: #1f8a99; }}"
        )
        self.edit.installEventFilter(self)
        lay.addWidget(self.edit, 1)

    def eventFilter(self, obj, event):
        if obj is self.edit:
            if event.type() == event.Type.FocusIn:
                self._focused = True
                self.update()
            elif event.type() == event.Type.FocusOut:
                self._focused = False
                self.update()
        return super().eventFilter(obj, event)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        p.setBrush(QColor("#ffffff" if LIGHT_MODE else "#060a0f"))
        border = (QColor(CYAN) if self._focused else QColor("#c9bedb")) if LIGHT_MODE else (
            QColor("#2a8d9b") if self._focused else QColor("#10303a"))
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(rect, 5, 5)

        # tiny corner tick (top-right)
        p.setPen(QPen(QColor("#8b69cb" if LIGHT_MODE else "#2a6f7a"), 1))
        x, y = rect.right() - 7, rect.top() + 6
        p.drawLine(QPointF(x - 4, y), QPointF(x, y))
        p.drawLine(QPointF(x, y), QPointF(x, y + 4))
        p.end()


# ----------------------------------------------------------------------------
# Card with accent corners
# ----------------------------------------------------------------------------
class AtlasCard(QFrame):
    RADIUS = 12

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.RADIUS
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        p.setBrush(QColor("#ffffff" if LIGHT_MODE else QColor(11, 13, 18, 235)))
        p.setPen(QPen(QColor("#d8d0e3" if LIGHT_MODE else "#1a2227"), 1))
        p.drawRoundedRect(rect, r, r)

        p.setBrush(Qt.NoBrush)

        # top-left cyan accent
        p.setPen(QPen(CYAN, 1.4))
        tl = QPainterPath()
        tl.moveTo(rect.left() + 34, rect.top())
        tl.lineTo(rect.left() + r, rect.top())
        tl.arcTo(QRectF(rect.left(), rect.top(), 2 * r, 2 * r), 90, 90)
        tl.lineTo(rect.left(), rect.top() + 28)
        p.drawPath(tl)

        # bottom-right purple accent
        p.setPen(QPen(PURPLE, 1.4))
        br = QPainterPath()
        br.moveTo(rect.right() - 34, rect.bottom())
        br.lineTo(rect.right() - r, rect.bottom())
        br.arcTo(QRectF(rect.right() - 2 * r, rect.bottom() - 2 * r, 2 * r, 2 * r), 270, 90)
        br.lineTo(rect.right(), rect.bottom() - 28)
        p.drawPath(br)
        p.end()


# ----------------------------------------------------------------------------
# Small status ring (bottom-right)
# ----------------------------------------------------------------------------
class StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(CYAN, 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(6, 6), 3, 3)
        p.end()


# ----------------------------------------------------------------------------
# "ATLAS" wordmark - cinematic font with a soft white -> ice-blue gradient
# ----------------------------------------------------------------------------
class Wordmark(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.font_ = make_font(TITLE_FONT, WORDMARK_SIZE, QFont.DemiBold, WORDMARK_SPACING)
        fm = QFontMetrics(self.font_)
        self.setFixedSize(fm.horizontalAdvance(text) + 16, fm.height() + 6)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setFont(self.font_)

        glow = QColor(63, 208, 226, 45)               # faint cyan glow behind the letters
        p.setPen(glow)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.drawText(QRectF(dx, dy, w, h), Qt.AlignCenter, self.text)

        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor("#ffffff"))
        g.setColorAt(1.0, QColor("#9fe8f5"))
        p.setPen(QPen(QBrush(g), 1))
        p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self.text)
        p.end()


# ----------------------------------------------------------------------------
# Login page
# ----------------------------------------------------------------------------
class LoginPage(QWidget):
    login_requested = Signal(str, str)   # username, password
    register_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        load_custom_fonts()
        self.setMinimumSize(900, 760)
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
            glow(0, h * 0.45, w * 0.42, QColor(182, 158, 220), 52)
            glow(w * 0.5, h * 0.42, 330, QColor(210, 198, 230), 38)
            glow(w, h * 0.68, w * 0.34, QColor(183, 160, 220), 35)
        else:
            glow(0, h * 0.45, w * 0.42, QColor(70, 35, 170), 80)
            glow(w * 0.5, h * 0.42, 330, QColor(60, 50, 150), 55)
            glow(w, h * 0.68, w * 0.34, QColor(0, 140, 130), 70)

        # thin top line
        p.setPen(QPen(QColor(20, 60, 70, 160), 1))
        p.drawLine(34, 24, w - 34, 24)
        p.end()

    # ---- UI ---------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 22)
        root.setSpacing(0)

        # header
        root.addWidget(make_label("ATLAS SECURE ENVIRONMENT", MONO, 9, TEXT_FAINT, spacing=2))
        root.addStretch(1)

        # centre column
        centre = QVBoxLayout()
        centre.setSpacing(0)
        centre.setAlignment(Qt.AlignHCenter)

        centre.addWidget(self._build_logo(), 0, Qt.AlignHCenter)
        centre.addSpacing(14)
        centre.addWidget(self._build_secure_divider(), 0, Qt.AlignHCenter)
        centre.addSpacing(14)

        title = make_label(
            "Ai-driven Tumor Localization\nand Analysis System",
            SANS, 23, TEXT, QFont.DemiBold, 1.2, Qt.AlignHCenter,
        )
        centre.addWidget(title, 0, Qt.AlignHCenter)
        centre.addSpacing(10)
        centre.addWidget(
            make_label("Medical Imaging Intelligence", MONO, 11, TEXT_DIM,
                       spacing=1.6, align=Qt.AlignHCenter),
            0, Qt.AlignHCenter,
        )
        centre.addSpacing(30)
        centre.addWidget(self._build_card(), 0, Qt.AlignHCenter)

        root.addLayout(centre)
        root.addStretch(1)

        # footer
        footer = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(make_label("© 2026 - HAK CIPTA TERPELIHARA", MONO, 8, TEXT_FAINT, spacing=1.4))
        left.addWidget(make_label("ATLAS : Ai-driven Tumor Localization and Analysis System",
                                  MONO, 8, TEXT_FAINT, spacing=1.0))
        footer.addLayout(left)
        footer.addStretch(1)
        footer.addWidget(StatusDot(), 0, Qt.AlignBottom)
        root.addLayout(footer)

    def _build_logo(self) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        path = find_logo()
        pm = QPixmap(path) if path else QPixmap()
        if not pm.isNull():
            emblem = QLabel()
            emblem.setPixmap(pm.scaledToHeight(LOGO_HEIGHT, Qt.SmoothTransformation))
            emblem.setStyleSheet("background: transparent;")
            lay.addWidget(emblem, 0, Qt.AlignVCenter)

        if WORDMARK_TEXT:
            if not pm.isNull():
                sep = QFrame()
                sep.setFixedSize(1, int(LOGO_HEIGHT * 0.8))
                sep.setStyleSheet("background: #1f3a46;")
                lay.addWidget(sep, 0, Qt.AlignVCenter)
            lay.addWidget(Wordmark(WORDMARK_TEXT), 0, Qt.AlignVCenter)
        return box

    def _build_secure_divider(self) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        def line():
            l = QFrame()
            l.setFixedSize(38, 1)
            l.setStyleSheet("background: #1f8a99;")
            return l

        lay.addWidget(line())
        lay.addWidget(make_label("SECURE CLINICAL ACCESS", MONO, 8, "#3fd0e2",
                                 QFont.Bold, 2.2))
        lay.addWidget(line())
        return box

    def _build_card(self) -> QWidget:
        card = AtlasCard()
        card.setFixedSize(530, 310)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 22, 32, 26)
        lay.setSpacing(0)

        lay.addWidget(make_label("AUTHORIZED ACCESS", SANS, 13, TEXT, QFont.Medium, 2.2))
        lay.addSpacing(18)

        self.username = AtlasField("user", "Username")
        self.password = AtlasField("key", "Password", password=True)
        lay.addWidget(self.username)
        lay.addSpacing(11)
        lay.addWidget(self.password)
        lay.addSpacing(14)

        lay.addWidget(make_label("256-BIT ENCRYPTED SESSION", MONO, 7, TEXT_FAINT,
                                 spacing=1.2, align=Qt.AlignHCenter))
        lay.addSpacing(10)

        # login button (short, pill-shaped, centred)
        self.login_btn = QPushButton("LOGIN")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setFixedSize(170, 44)
        self.login_btn.setFont(make_font(MONO, 11, QFont.Bold, 3.0))
        self.login_btn.setStyleSheet("""
            QPushButton {
                color: #04141a; border: none; border-radius: 22px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #38cde0, stop:1 #7aeef3);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #4ddbec, stop:1 #98f4f7);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #2bb4c6, stop:1 #62d9de);
            }
        """)
        self.login_btn.clicked.connect(self._on_login)
        lay.addWidget(self.login_btn, 0, Qt.AlignHCenter)
        lay.addSpacing(18)

        # "Don't have an account yet? Register Here"
        reg = QHBoxLayout()
        reg.setSpacing(4)
        reg.addStretch(1)
        reg.addWidget(make_label("Don't have an account yet?", SANS, 11, TEXT_DIM))
        self.register_btn = QPushButton("Register Here")
        self.register_btn.setFlat(True)
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.setFont(make_font(SANS, 11, QFont.DemiBold))
        self.register_btn.setStyleSheet(
            "QPushButton { color: #3fd0e2; background: transparent; border: none;"
            " padding: 0; }"
            "QPushButton:hover { color: #98f4f7; }")
        self.register_btn.clicked.connect(self.register_requested.emit)
        reg.addWidget(self.register_btn)
        reg.addStretch(1)
        lay.addLayout(reg)

        # Enter key submits
        self.username.edit.returnPressed.connect(self.password.edit.setFocus)
        self.password.edit.returnPressed.connect(self._on_login)
        return card

    # ---- actions ----------------------------------------------------------
    def _on_login(self):
        self.login_requested.emit(self.username.edit.text().strip(),
                                  self.password.edit.text())

    def clear(self):
        self.username.edit.clear()
        self.password.edit.clear()
        self.username.edit.setFocus()

    def set_theme(self, dark: bool):
        global BG, CYAN, CYAN_DIM, TEXT, TEXT_DIM, TEXT_FAINT, LIGHT_MODE
        light = not dark
        if LIGHT_MODE == light:
            return
        old = {TEXT: "#20182e" if light else "#e8eef2",
               TEXT_DIM: "#655d75" if light else "#5b6670",
               TEXT_FAINT: "#857d95" if light else "#46515a",
               CYAN.name(): "#7048b8" if light else "#3fd0e2"}
        LIGHT_MODE = light
        BG = QColor("#f4f1f8" if light else "#04050a")
        CYAN = QColor("#7048b8" if light else "#3fd0e2")
        CYAN_DIM = QColor("#d8cde8" if light else "#12303a")
        TEXT = "#20182e" if light else "#e8eef2"
        TEXT_DIM = "#655d75" if light else "#5b6670"
        TEXT_FAINT = "#857d95" if light else "#46515a"
        for label in self.findChildren(QLabel):
            style = label.styleSheet()
            for before, after in old.items():
                style = style.replace(before, after)
            label.setStyleSheet(style)
        for field in (self.username, self.password):
            field.edit.setStyleSheet(
                f"QLineEdit {{ background: transparent; border: none; color: {TEXT};"
                " padding-left: 12px; selection-background-color: #8b69cb; }}")
            field.update()
        if light:
            self.login_btn.setStyleSheet("""
                QPushButton { color: #ffffff; border: none; border-radius: 22px;
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7650d8,stop:1 #a78bfa); }
                QPushButton:hover { background: #9a78f2; }
                QPushButton:pressed { background: #6540bd; }
            """)
            self.register_btn.setStyleSheet("QPushButton { color: #7048b8; background: transparent; border: none; padding: 0; } QPushButton:hover { color: #815abd; }")
        else:
            self.login_btn.setStyleSheet("""
                QPushButton {
                    color: #04141a; border: none; border-radius: 22px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #38cde0, stop:1 #7aeef3);
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #4ddbec, stop:1 #98f4f7);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #2bb4c6, stop:1 #62d9de);
                }
            """)
            self.register_btn.setStyleSheet(
                "QPushButton { color: #3fd0e2; background: transparent; border: none; padding: 0; }"
                "QPushButton:hover { color: #98f4f7; }")
        self.update()


# ----------------------------------------------------------------------------
# Preview
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    page = LoginPage()
    page.login_requested.connect(lambda u, pw: print("LOGIN:", u, "*" * len(pw)))
    page.register_requested.connect(lambda: print("REGISTER clicked"))
    page.resize(1210, 855)
    page.setWindowTitle("ATLAS - Login")
    page.show()
    sys.exit(app.exec())
