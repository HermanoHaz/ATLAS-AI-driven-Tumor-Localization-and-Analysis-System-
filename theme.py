"""theme.py - colours and the Qt stylesheet shared by the login window and the viewer."""
from string import Template

BG, SURF, RAISED, LINE = "#0a0e13", "#141a22", "#1c242e", "#243040"
VIEW = "#06080c"
TEXT, MUTED, FAINT = "#e8eef4", "#8a99a9", "#5b6876"
ACCENT, ACCENT_HI, ACCENT_INK = "#4f8cff", "#7aaaff", "#06142e"
DANGER, OK, WARN = "#ff6b6b", "#3ddc84", "#f5c542"
TRACK = "#2a3441"
PLANE = {0: "#f5c542", 1: "#3ddc84", 2: "#ff5d5d"}       # sagittal, coronal, axial
PRED = "#ff4081"                                         # tumor predicted by MedSAM
PRED_RGB = (255, 64, 129)
GT = "#00f0ff"                                           # actual (ground-truth) tumor
GT_RGB = (0, 240, 255)

_QSS = Template("""
* { font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", sans-serif; font-size: 13px; }
QWidget { background: $BG; color: $TEXT; }
QLabel { background: transparent; }
QLabel#muted { color: $MUTED; }
QLabel#title { font-size: 15px; font-weight: 700; }
QLabel#cardTitle { font-size: 13px; font-weight: 700; }
QLabel#hero { font-size: 22px; font-weight: 700; }
QLabel#error { color: $DANGER; }
QLabel#hint { color: $MUTED; font-size: 12px; }
QLabel#pill { background: #202a36; color: $MUTED; border-radius: 9px; padding: 2px 9px;
              font-size: 11px; font-weight: 600; }

QFrame#topbar { background: #0d1218; border-bottom: 1px solid #1c2530; }
QFrame#statusbar { background: #0d1218; border-top: 1px solid #1c2530; }
QFrame#card { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #18202a, stop:1 #131a22);
              border: 1px solid $LINE; border-radius: 14px; }
QFrame#viewport { background: $VIEW; border: 1px solid $LINE; border-radius: 14px; }
QSplitter::handle { background: transparent; }

QPushButton { background: $RAISED; color: $TEXT; border: 1px solid transparent; border-radius: 10px;
              padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #2a3441; }
QPushButton:focus { border: 1px solid $ACCENT; }
QPushButton:disabled { background: #161d26; color: $FAINT; }
QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6ea5ff, stop:1 #4a82f5);
                      color: $ACCENT_INK; }
QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #86b4ff, stop:1 #5b91ff); }
QPushButton#primary:disabled { background: #1c2838; color: $FAINT; }

QFrame#seg { background: #0e141b; border: 1px solid $LINE; border-radius: 11px; }
QFrame#seg QPushButton { background: transparent; color: $MUTED; border: none; border-radius: 8px; padding: 6px 14px; }
QFrame#seg QPushButton:hover { color: $TEXT; }
QFrame#seg QPushButton:focus { border: none; }
QFrame#seg QPushButton:checked { background: #2a3544; color: $TEXT; }
QFrame#seg[accent="true"] QPushButton:checked { background: $ACCENT; color: $ACCENT_INK; }

QSlider { background: transparent; }
QSlider::groove:horizontal { height: 5px; background: $TRACK; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ACCENT; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffffff; width: 14px; height: 14px; margin: -5px 0;
                             border-radius: 7px; border: 2px solid $ACCENT; }
QSlider::handle:horizontal:hover { width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }

QProgressBar { background: $TRACK; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: $ACCENT; border-radius: 2px; }

QLineEdit { background: $RAISED; color: $TEXT; border: 1px solid $LINE; border-radius: 10px; padding: 10px 12px;
            selection-background-color: $ACCENT; }
QLineEdit:focus { border: 1px solid $ACCENT; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #2a3441; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3a4757; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: $RAISED; color: $TEXT; border: 1px solid $LINE; padding: 4px 8px; }
QMessageBox, QFileDialog, QDialog { background: $BG; }
""")

QSS = _QSS.substitute(BG=BG, SURF=SURF, RAISED=RAISED, LINE=LINE, VIEW=VIEW, TEXT=TEXT, MUTED=MUTED,
                      FAINT=FAINT, ACCENT=ACCENT, ACCENT_HI=ACCENT_HI, ACCENT_INK=ACCENT_INK,
                      DANGER=DANGER, TRACK=TRACK)