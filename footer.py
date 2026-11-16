"""
ATLAS - Shared footer  (components/footer.py)

Use it on any page:

    from components.footer import AppFooter

    self.footer = AppFooter()
    layout.addWidget(self.footer)

    self.footer.set_status("SYSTEM ONLINE", online=True)   # optional
    self.footer.set_version("v1.0.0")                       # optional

Preview on its own:  python components\\footer.py
"""
import os
import sys
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from theme.theme import (
    MONO, GREEN,
    SHELL_BG_TOP, SHELL_BG_BOTTOM, SHELL_BORDER, SHELL_ACCENT,
    SHELL_TEXT_DIM, SHELL_TEXT_FAINT,
    Dot, make_label, vline,
)

# PURPLE HEADER / FOOTER THEME
SHELL_BG_TOP = "#100B20"
SHELL_BG_BOTTOM = "#19112E"
SHELL_BORDER = "#49336F"
SHELL_ACCENT = "#A78BFA"
SHELL_TEXT_DIM = "#A99ACB"
SHELL_TEXT_FAINT = "#786A99"

# ============================================================================
#  >>>  FOOTER SETTINGS - EDIT HERE  <<<
# ============================================================================
COPYRIGHT_TEXT = "© 2026 - HAK CIPTA TERPELIHARA"
SYSTEM_TEXT = "ATLAS : Ai-driven Tumor Localization and Analysis System"
APP_VERSION = "v1.0.0"
SHOW_CLOCK = True
# ============================================================================


class AppFooter(QWidget):
    HEIGHT = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(36, 0, 36, 0)
        lay.setSpacing(12)

        # ---- left: copyright + system name ----
        lay.addWidget(make_label(COPYRIGHT_TEXT, MONO, 9, SHELL_TEXT_DIM, spacing=1.4))
        lay.addWidget(vline(12))
        lay.addWidget(make_label(SYSTEM_TEXT, MONO, 9, SHELL_TEXT_FAINT, spacing=1.0))
        lay.addStretch(1)

        # ---- optional live status (scanner uses this; hidden until set_status) ----
        self.status_dot = Dot(GREEN, 5)
        self.status_label = make_label("", MONO, 9, GREEN, spacing=0.8)
        self.status_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._status_sep = vline(12)
        self.status_dot.hide()
        self.status_label.hide()
        self._status_sep.hide()
        lay.addWidget(self.status_dot)
        lay.addWidget(self.status_label)
        lay.addWidget(self._status_sep)

        # ---- right: version | clock ----
        self.version_label = make_label(APP_VERSION, MONO, 9, SHELL_TEXT_DIM, spacing=1.2)
        lay.addWidget(self.version_label)

        self.clock_label = make_label("", MONO, 9, SHELL_TEXT_DIM, spacing=1.2)
        if SHOW_CLOCK:
            lay.addWidget(vline(12))
            lay.addWidget(self.clock_label)
            self._tick()
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(1000)

    def _tick(self):
        self.clock_label.setText(datetime.now().strftime("%d %b %Y  %H:%M:%S").upper())

    # ---- public API ----
    def set_status(self, text: str, online: bool = True):
        color = GREEN if online else "#ff7b8a"
        self.status_label.setText(text.upper())
        self.status_label.setStyleSheet(f"color: {color}; background: transparent;")
        self.status_dot.set_color(color)
        show = bool(text)
        self.status_dot.setVisible(show)
        self.status_label.setVisible(show)
        self._status_sep.setVisible(show)

    def set_version(self, text: str):
        self.version_label.setText(text)

    # ---- painting: navy band + glowing accent line on the top edge ----
    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(SHELL_BG_BOTTOM))
        g.setColorAt(1, QColor(SHELL_BG_TOP))
        p.fillRect(self.rect(), g)

        p.setPen(QPen(QColor(SHELL_BORDER), 1))
        p.drawLine(0, 0, w, 0)

        ag = QLinearGradient(0, 0, w, 0)
        a0 = QColor(SHELL_ACCENT); a0.setAlpha(0)
        a1 = QColor(SHELL_ACCENT); a1.setAlpha(160)
        ag.setColorAt(0.0, a0)
        ag.setColorAt(0.40, a0)
        ag.setColorAt(0.85, a1)
        ag.setColorAt(1.0, a0)
        p.fillRect(QRectF(0, 0, w, 2), ag)
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
    v.addStretch(1)
    v.addWidget(AppFooter())
    box.resize(1300, 200)
    box.setWindowTitle("AppFooter preview")
    box.show()
    sys.exit(app.exec())