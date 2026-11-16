
"""
ATLAS - User Registration Interface (standalone, outside the main shell)

Place at: interfaces/user_register.py
Run directly to preview:  python interfaces\\user_register.py

Hook into your app via the signals:
    register_submitted(data: dict)   -> keys: first_name, last_name, email, phone,
                                        username, password, department, role, license_no
    back_to_login_requested()
"""
import glob
import os
import re
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QRegularExpression
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPalette,
    QPen, QPixmap, QRadialGradient, QLinearGradient, QAction,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListView, QPushButton, QVBoxLayout, QWidget,
)

from theme.theme import TITLE_FONT, load_custom_fonts

# ============================================================================
# SETTINGS
# ============================================================================
LOGO_NAME = "Atlas_Bulat"
LOGO_HEIGHT = 48
SCALE = 1.1
# ============================================================================


def sc(n):
    """Scale a pixel size by SCALE."""
    return int(round(n * SCALE))


def find_logo():
    """Search the assets folder for a file that starts with LOGO_NAME."""
    here = os.path.dirname(os.path.abspath(__file__))
    folders = [
        os.path.join(here, "..", "assets"),
        os.path.join(here, "assets"),
        os.path.join(os.getcwd(), "assets"),
    ]
    for folder in folders:
        matches = glob.glob(os.path.join(folder, LOGO_NAME + "*"))
        matches = [m for m in matches if m.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
        if matches:
            return matches[0]
    print("[register] Logo not found. Looked in:")
    for f in folders:
        print("   ", os.path.abspath(f))
    return None


# ----------------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------------
BG = QColor("#04050a")
CYAN = QColor("#3fd0e2")
CYAN_BRIGHT = QColor("#7aeef3")
CYAN_DIM = QColor("#12303a")
PURPLE = QColor("#7c5cff")
TEXT = "#e8eef2"
TEXT_DIM = "#5b6670"
TEXT_FAINT = "#46515a"
LABEL_COLOR = "#8b959d"
PLACEHOLDER = "#4d5861"
ERROR = "#ff7b8a"
LIGHT_MODE = False

SANS = ["Inter", "Segoe UI", "Helvetica Neue", "Arial"]
MONO = ["JetBrains Mono", "Consolas", "Menlo", "Courier New"]


def make_font(families, px, weight=QFont.Normal, spacing=0.0):
    f = QFont()
    f.setFamilies(families)
    f.setPixelSize(max(1, round(px * SCALE)))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing * SCALE)
    return f


def make_label(text, families, px, color, weight=QFont.Normal, spacing=0.0,
               align=Qt.AlignLeft):
    lbl = QLabel(text)
    lbl.setFont(make_font(families, px, weight, spacing))
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    lbl.setAlignment(align | Qt.AlignVCenter)
    return lbl


def make_eye_icon(visible: bool) -> QIcon:
    """Eye icon (slashed when the password is hidden)."""
    pm = QPixmap(36, 36)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#766b87" if LIGHT_MODE else "#8b959d"), 2.0,
                  Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(5, 18)
    path.quadTo(18, 5, 31, 18)
    path.quadTo(18, 31, 5, 18)
    p.drawPath(path)
    p.drawEllipse(QPointF(18, 18), 4.2, 4.2)
    if not visible:
        p.drawLine(QPointF(8, 29), QPointF(28, 7))
    p.end()
    return QIcon(pm)


# ----------------------------------------------------------------------------
# Logo box
# ----------------------------------------------------------------------------
class LogoBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pad = sc(12)
        path = find_logo()
        self.pm = QPixmap(path) if path else QPixmap()
        if not self.pm.isNull():
            self.pm = self.pm.scaledToHeight(sc(LOGO_HEIGHT), Qt.SmoothTransformation)
            self.setFixedSize(self.pm.width() + 2 * self.pad,
                              self.pm.height() + 2 * self.pad)
        else:
            self.setFixedSize(sc(76), sc(76))
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.pm.isNull():
            p.setPen(QColor(TEXT))
            p.setFont(make_font(SANS, 14, QFont.Light, 3))
            p.drawText(self.rect(), Qt.AlignCenter, "ATLAS")
        else:
            p.drawPixmap(self.pad, self.pad, self.pm)

        a = sc(10)
        p.setPen(QPen(QColor("#9aa6ad"), 1.2))
        p.drawLine(1, 1, 1 + a, 1)
        p.drawLine(1, 1, 1, 1 + a)
        p.drawLine(w - 1, h - 1, w - 1 - a, h - 1)
        p.drawLine(w - 1, h - 1, w - 1, h - 1 - a)
        p.setPen(Qt.NoPen)
        p.setBrush(CYAN)
        p.drawEllipse(QPointF(w - 3, 4), 2, 2)
        p.end()


# ----------------------------------------------------------------------------
# Form card
# ----------------------------------------------------------------------------
class RegisterCard(QFrame):
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        rect = QRectF(0.5, 0.5, w - 1, h - 1)

        p.setBrush(QColor("#ffffff" if LIGHT_MODE else QColor(10, 15, 20, 215)))
        p.setPen(QPen(QColor("#d8d0e3" if LIGHT_MODE else "#0f3a42"), 1))
        p.drawRect(rect)

        a = sc(12)
        p.setPen(QPen(CYAN_BRIGHT, 1.6))
        p.drawLine(0, 0, a, 0)
        p.drawLine(0, 0, 0, a)
        p.drawLine(w - 1 - a, 0, w - 1, 0)
        p.drawLine(w - 1, 0, w - 1, a)
        p.end()


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------
INPUT_STYLE = f"""
    QLineEdit {{
        background: #060a0f; border: 1px solid #10303a; border-radius: 3px;
        padding: 0 12px; color: {TEXT}; selection-background-color: #1f8a99;
    }}
    QLineEdit:focus {{ border: 1px solid #2a8d9b; }}
"""


def make_input(placeholder: str, password=False) -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    e.setFixedHeight(sc(36))
    e.setFont(make_font(SANS, 12))
    pal = e.palette()
    pal.setColor(QPalette.PlaceholderText, QColor(PLACEHOLDER))
    e.setPalette(pal)
    e.setStyleSheet(INPUT_STYLE)
    if password:
        e.setEchoMode(QLineEdit.Password)
        action = QAction(e)
        action.setIcon(make_eye_icon(False))
        action.setToolTip("Show / hide password")

        def toggle():
            hidden = e.echoMode() == QLineEdit.Password
            e.setEchoMode(QLineEdit.Normal if hidden else QLineEdit.Password)
            action.setIcon(make_eye_icon(hidden))

        action.triggered.connect(toggle)
        e.addAction(action, QLineEdit.TrailingPosition)
    return e


class AtlasCombo(QComboBox):
    def __init__(self, placeholder: str, items, parent=None):
        super().__init__(parent)
        self.setView(QListView())
        self.addItem(placeholder)
        self.model().item(0).setEnabled(False)
        self.addItems(items)
        self.setCurrentIndex(0)
        self.setFixedHeight(sc(36))
        self.setFont(make_font(SANS, 12))
        self.setProperty("placeholder", True)
        self.refresh_theme()
        self.currentIndexChanged.connect(self._refresh)

    def refresh_theme(self):
        bg = "#ffffff" if LIGHT_MODE else "#060a0f"
        border = "#c9bedb" if LIGHT_MODE else "#10303a"
        popup = "#ffffff" if LIGHT_MODE else "#0a0d12"
        hover = "#e8def7" if LIGHT_MODE else "#12303a"
        self.setStyleSheet(f"""
            QComboBox {{
                background: {bg}; border: 1px solid {border}; border-radius: 3px;
                padding: 0 12px; color: {TEXT};
            }}
            QComboBox[placeholder="true"] {{ color: {PLACEHOLDER}; }}
            QComboBox:focus, QComboBox:on {{ border: 1px solid {CYAN.name()}; }}
            QComboBox::drop-down {{ border: none; width: {sc(34)}px; }}
            QComboBox::down-arrow {{ image: none; }}
            QComboBox QAbstractItemView {{
                background: {popup}; border: 1px solid {border}; outline: 0;
                color: {TEXT}; selection-background-color: {hover};
                selection-color: {TEXT};
            }}
            QComboBox QAbstractItemView::item {{ padding: 6px 10px; min-height: 22px; }}
            QComboBox QAbstractItemView::item:disabled {{ color: {PLACEHOLDER}; }}
        """)

    def _refresh(self):
        self.setProperty("placeholder", self.currentIndex() <= 0)
        self.style().unpolish(self)
        self.style().polish(self)

    def has_value(self) -> bool:
        return self.currentIndex() > 0

    def value(self) -> str:
        return self.currentText() if self.has_value() else ""

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#8b959d"), 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx, cy = self.width() - sc(18), self.height() / 2
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2))
        p.drawLine(QPointF(cx, cy + 2), QPointF(cx + 4, cy - 2))
        p.end()


class PillButton(QPushButton):
    """Short, circular (pill-shaped) submit button with the cyan gradient."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(sc(180), sc(46))
        self.setFont(make_font(MONO, 11, QFont.Bold, 3.0))

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

        if LIGHT_MODE and self.isDown():
            c0, c1 = "#6040aa", "#8b69cb"
        elif LIGHT_MODE and self._hover:
            c0, c1 = "#865fc4", "#b59ee0"
        elif LIGHT_MODE:
            c0, c1 = "#7048b8", "#a78bfa"
        elif self.isDown():
            c0, c1 = "#2bb4c6", "#62d9de"
        elif self._hover:
            c0, c1 = "#4ddbec", "#98f4f7"
        else:
            c0, c1 = "#38cde0", "#7aeef3"
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0, QColor(c0))
        g.setColorAt(1, QColor(c1))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)

        p.setFont(self.font())
        p.setPen(QColor("#ffffff" if LIGHT_MODE else "#04141a"))
        p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self.text())
        p.end()


# ----------------------------------------------------------------------------
# Registration page
# ----------------------------------------------------------------------------
class RegisterPage(QWidget):
    register_submitted = Signal(dict)
    back_to_login_requested = Signal()

    DEPARTMENTS = [
        "Radiology", "Oncology", "Neurology", "Neurosurgery",
        "Pathology", "Internal Medicine", "Biomedical / IT",
    ]
    ROLES = ["Doctor", "Radiologist", "Technician", "Nurse", "Administrator"]

    def __init__(self, parent=None):
        super().__init__(parent)
        load_custom_fonts()
        self.setMinimumSize(1100, 800)
        self._build_ui()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), BG)

        def glow(cx, cy, radius, color, alpha):
            g = QRadialGradient(QPointF(cx, cy), radius)
            c0 = QColor(color)
            c0.setAlpha(alpha)
            c1 = QColor(color)
            c1.setAlpha(0)
            g.setColorAt(0.0, c0)
            g.setColorAt(1.0, c1)
            p.fillRect(self.rect(), g)

        if LIGHT_MODE:
            glow(0, h * 0.45, w * 0.42, QColor(182, 158, 220), 50)
            glow(w * 0.5, h * 0.42, 330, QColor(210, 198, 230), 34)
            glow(w, h * 0.68, w * 0.34, QColor(183, 160, 220), 35)
        else:
            glow(0, h * 0.45, w * 0.42, QColor(70, 35, 170), 80)
            glow(w * 0.5, h * 0.42, 330, QColor(60, 50, 150), 40)
            glow(w, h * 0.68, w * 0.34, QColor(0, 140, 130), 70)
        p.end()

    def set_theme(self, dark: bool):
        global BG, CYAN, CYAN_BRIGHT, CYAN_DIM, PURPLE, TEXT, TEXT_DIM, TEXT_FAINT
        global LABEL_COLOR, PLACEHOLDER, INPUT_STYLE, LIGHT_MODE
        light = not dark
        if LIGHT_MODE == light:
            return
        old = {TEXT: "#20182e" if light else "#e8eef2",
               TEXT_DIM: "#655d75" if light else "#5b6670",
               TEXT_FAINT: "#857d95" if light else "#46515a",
               LABEL_COLOR: "#665f73" if light else "#8b959d",
               PLACEHOLDER: "#938aa0" if light else "#4d5861",
               CYAN.name(): "#7048b8" if light else "#3fd0e2",
               CYAN_BRIGHT.name(): "#815abd" if light else "#7aeef3",
               CYAN_DIM.name(): "#d8cde8" if light else "#12303a",
               PURPLE.name(): "#7048b8" if light else "#7c5cff",
               "#6fe6f2": "#7048b8" if light else "#6fe6f2"}
        LIGHT_MODE = light
        BG = QColor("#f4f1f8" if light else "#04050a")
        CYAN = QColor("#7048b8" if light else "#3fd0e2")
        CYAN_BRIGHT = QColor("#815abd" if light else "#7aeef3")
        CYAN_DIM = QColor("#d8cde8" if light else "#12303a")
        PURPLE = QColor("#7048b8" if light else "#7c5cff")
        TEXT = "#20182e" if light else "#e8eef2"
        TEXT_DIM = "#655d75" if light else "#5b6670"
        TEXT_FAINT = "#857d95" if light else "#46515a"
        LABEL_COLOR = "#665f73" if light else "#8b959d"
        PLACEHOLDER = "#938aa0" if light else "#4d5861"
        input_bg = "#ffffff" if light else "#060a0f"
        input_border = "#c9bedb" if light else "#10303a"
        selection = "#e8def7" if light else "#1f8a99"
        INPUT_STYLE = f"""
            QLineEdit {{ background: {input_bg}; border: 1px solid {input_border}; border-radius: 3px;
                        padding: 0 12px; color: {TEXT}; selection-background-color: {selection}; }}
            QLineEdit:focus {{ border: 1px solid {CYAN.name()}; }}
        """
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
            if isinstance(widget, QLineEdit):
                widget.setStyleSheet(INPUT_STYLE)
                pal = widget.palette()
                pal.setColor(QPalette.PlaceholderText, QColor(PLACEHOLDER))
                widget.setPalette(pal)
            if isinstance(widget, AtlasCombo):
                widget.refresh_theme()
            widget.update()
        self.update()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 18, 30, 18)
        root.setSpacing(0)

        column = QWidget()
        column.setMaximumWidth(sc(1000))
        column.setStyleSheet("background: transparent;")
        col = QVBoxLayout(column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        col.addWidget(self._build_header())
        col.addSpacing(sc(14))
        self.card = self._build_card()
        col.addWidget(self.card)

        root.addStretch(1)
        root.addWidget(column, 0, Qt.AlignHCenter)
        root.addStretch(1)

    def _build_header(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(sc(4))

        v.addWidget(LogoBox(), 0, Qt.AlignHCenter)
        v.addSpacing(sc(4))
        v.addWidget(make_label("MEDICAL IMAGING INTELLIGENCE", MONO, 10, TEXT_DIM,
                               spacing=2.4, align=Qt.AlignHCenter))
        v.addWidget(make_label("Ai-driven Tumor Localization and Analysis System",
                               TITLE_FONT, 22, TEXT, QFont.Medium, 1.4,
                               Qt.AlignHCenter))
        v.addWidget(make_label("New Staff Account Registration & Clearance Portal",
                               MONO, 10, "#6b7680", spacing=1.2, align=Qt.AlignHCenter))
        return box

    def _field(self, label: str, widget: QWidget) -> QWidget:
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(sc(6))
        lay.addWidget(make_label(label, MONO, 8, LABEL_COLOR, spacing=1.4))
        lay.addWidget(widget)
        return box

    def _step_marker(self) -> QWidget:
        box = QWidget()
        box.setFixedWidth(sc(84))
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(sc(6))
        lay.addWidget(make_label("01", MONO, 8, "#3fd0e2", spacing=1))
        line = QFrame()
        line.setFixedSize(sc(28), 1)
        line.setStyleSheet("background: #3fd0e2;")
        lay.addWidget(line)
        lay.addWidget(make_label("02", MONO, 8, TEXT_FAINT, spacing=1))
        return box

    def _build_card(self) -> QWidget:
        card = RegisterCard()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(sc(48), sc(22), sc(48), sc(24))
        lay.setSpacing(0)

        top = QHBoxLayout()
        spacer = QWidget()
        spacer.setFixedWidth(sc(84))
        top.addWidget(spacer)
        top.addStretch(1)
        top.addWidget(make_label("SECURE IDENTITY ENROLLMENT", MONO, 8, "#3fd0e2",
                                 QFont.Bold, 2.4, Qt.AlignHCenter))
        top.addStretch(1)
        top.addWidget(self._step_marker())
        lay.addLayout(top)
        lay.addSpacing(sc(6))
        lay.addWidget(make_label("Enter Professional Credentials", TITLE_FONT, 18,
                                 "#6fe6f2", QFont.Medium, 1.2, Qt.AlignHCenter))
        lay.addSpacing(sc(20))

        self.first_name = make_input("Enter first name")
        self.last_name = make_input("Enter last name")
        self.email = make_input("name@hospital.org")

        # Contact number: allow digits and an optional + at the beginning.
        self.phone = make_input("+60 xx xxx xxxx")
        self.phone.setValidator(
            QRegularExpressionValidator(
                QRegularExpression(r"\+?[0-9]*"),
                self.phone
            )
        )

        self.username = make_input("Create username")
        self.password = make_input("Enter password", password=True)
        self.department = AtlasCombo("Select department", self.DEPARTMENTS)
        self.role = AtlasCombo("Select clearance role", self.ROLES)
        self.license_no = make_input("e.g., MMC Registration No.")

        grid = QGridLayout()
        grid.setHorizontalSpacing(sc(18))
        grid.setVerticalSpacing(sc(12))
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.addWidget(self._field("FIRST NAME", self.first_name), 0, 0)
        grid.addWidget(self._field("LAST NAME", self.last_name), 0, 1)
        grid.addWidget(self._field("PROFESSIONAL EMAIL", self.email), 1, 0)
        grid.addWidget(self._field("CONTACT NUMBER", self.phone), 1, 1)
        grid.addWidget(self._field("DESIRED USERNAME", self.username), 2, 0)
        grid.addWidget(self._field("SECURE PASSWORD", self.password), 2, 1)
        grid.addWidget(self._field("HOSPITAL DEPARTMENT", self.department), 3, 0)
        grid.addWidget(self._field("STAFF POSITION / ROLE", self.role), 3, 1)
        grid.addWidget(self._field("MEDICAL LICENSE NUMBER", self.license_no), 4, 0, 1, 2)
        lay.addLayout(grid)
        lay.addSpacing(sc(8))

        note = QHBoxLayout()
        note.setSpacing(6)
        note.addStretch(1)
        info = QLabel("i")
        info.setFixedSize(sc(12), sc(12))
        info.setAlignment(Qt.AlignCenter)
        info.setFont(make_font(SANS, 8, QFont.Bold))
        info.setStyleSheet("color: #3fd0e2; border: 1px solid #3fd0e2;"
                           f" border-radius: {sc(6)}px; background: transparent;")
        note.addWidget(info)
        note.addWidget(make_label("Required for doctors to validate diagnostic sign-offs.",
                                  SANS, 9, TEXT_DIM))
        note.addStretch(1)
        lay.addLayout(note)

        self.error_label = make_label("", SANS, 10, ERROR, align=Qt.AlignHCenter)
        self.error_label.hide()
        lay.addSpacing(sc(6))
        lay.addWidget(self.error_label)
        lay.addSpacing(sc(10))

        self.submit_btn = PillButton("SUBMIT")
        self.submit_btn.clicked.connect(self._on_submit)
        lay.addWidget(self.submit_btn, 0, Qt.AlignHCenter)
        lay.addSpacing(sc(14))

        back = QHBoxLayout()
        back.addStretch(1)
        back.addWidget(make_label("Already have clearance?", SANS, 9, TEXT_DIM))
        link = QPushButton("Return to Login")
        link.setFlat(True)
        link.setCursor(Qt.PointingHandCursor)
        link.setFont(make_font(SANS, 9))
        link.setStyleSheet("QPushButton { color: #3fd0e2; background: transparent;"
                           " border: none; padding: 0 0 0 4px; }"
                           "QPushButton:hover { color: #98f4f7; }")
        link.clicked.connect(self.back_to_login_requested.emit)
        back.addWidget(link)
        back.addStretch(1)
        lay.addLayout(back)
        return card

    # ---- actions ----------------------------------------------------------
    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.setVisible(bool(msg))

    def _on_submit(self):
        data = {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "department": self.department.value(),
            "role": self.role.value(),
            "license_no": self.license_no.text().strip(),
        }

        if not all([data["first_name"], data["last_name"], data["email"],
                    data["phone"], data["username"], data["password"]]):
            return self._show_error("Please fill in all required fields.")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", data["email"]):
            return self._show_error("Please enter a valid professional email.")
        if len(data["password"]) < 8:
            return self._show_error("Password must be at least 8 characters.")
        if not data["department"] or not data["role"]:
            return self._show_error("Please select a department and a role.")
        if data["role"] == "Doctor" and not data["license_no"]:
            return self._show_error("A medical license number is required for doctors.")

        self._show_error("")
        self.register_submitted.emit(data)

    def clear(self):
        for e in (self.first_name, self.last_name, self.email, self.phone,
                  self.username, self.password, self.license_no):
            e.clear()
        self.department.setCurrentIndex(0)
        self.role.setCurrentIndex(0)
        self._show_error("")


# ----------------------------------------------------------------------------
# Preview
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    page = RegisterPage()
    page.register_submitted.connect(lambda d: print("REGISTER:", {**d, "password": "***"}))
    page.back_to_login_requested.connect(lambda: print("BACK TO LOGIN clicked"))
    page.resize(1210, 860)
    page.setWindowTitle("ATLAS - Register")
    page.show()
    sys.exit(app.exec())
