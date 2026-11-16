"""
ATLAS - colours + stylesheet for the AI Scanner page  (theme/scanner_theme.py)

Same constant names as the AI engineer's original theme.py, but re-coloured to the ATLAS look
(near-black background, purple accent). It is applied ONLY inside the scanner page, so it
never changes the other screens.
"""
from string import Template

BG, SURF, RAISED, LINE = "#05070c", "#0d1017", "#141a26", "#1f2433"
VIEW = "#04060a"
TEXT, MUTED, FAINT = "#e8eef2", "#8b959d", "#5b6670"
ACCENT, ACCENT_HI, ACCENT_INK = "#7c5cff", "#a98bff", "#ffffff"
DANGER, OK, WARN = "#ff6b6b", "#3de0a0", "#f5c542"
TRACK = "#262d3d"
PLANE = {0: "#f5c542", 1: "#3ddc84", 2: "#ff5d5d"}       # sagittal, coronal, axial
PRED = "#ff4081"                                         # tumor predicted by MedSAM
PRED_RGB = (255, 64, 129)
GT = "#00f0ff"                                           # actual (ground-truth) tumor
GT_RGB = (0, 240, 255)

_QSS = Template("""
* { font-family: "Inter", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", sans-serif; font-size: 13px; }
QWidget { background: $BG; color: $TEXT; }
QLabel { background: transparent; }
QLabel#muted { color: $MUTED; }
QLabel#title { font-size: 15px; font-weight: 700; letter-spacing: 2px; }
QLabel#cardTitle { font-size: 13px; font-weight: 700; }
QLabel#hint { color: $MUTED; font-size: 12px; }
QLabel#pill { background: #1a1f2e; color: $MUTED; border-radius: 9px; padding: 2px 9px;
              font-size: 11px; font-weight: 600; }

QFrame#topbar { background: #0a0d14; border-bottom: 1px solid #1a2030; }
QFrame#card { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #111620, stop:1 #0d1118);
              border: 1px solid $LINE; border-radius: 6px; }
QFrame#viewport { background: $VIEW; border: 1px solid $LINE; border-radius: 6px; }
QSplitter::handle { background: transparent; }

QPushButton { background: $RAISED; color: $TEXT; border: 1px solid #1f2433; border-radius: 6px;
              padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #1c2333; border: 1px solid #2f3a5a; }
QPushButton:focus { border: 1px solid $ACCENT; }
QPushButton:disabled { background: #0e1219; color: $FAINT; border: 1px solid #151a26; }
QPushButton#primary { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8a6dff, stop:1 #6a4cf0);
                      color: $ACCENT_INK; border: none; }
QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9a80ff, stop:1 #7a5dff); }
QPushButton#primary:disabled { background: #1a1730; color: $FAINT; }

QFrame#seg { background: #0a0d14; border: 1px solid $LINE; border-radius: 6px; }
QFrame#seg QPushButton { background: transparent; color: $MUTED; border: none; border-radius: 5px; padding: 6px 14px; }
QFrame#seg QPushButton:hover { color: $TEXT; }
QFrame#seg QPushButton:focus { border: none; }
QFrame#seg QPushButton:checked { background: #20263a; color: $TEXT; }
QFrame#seg[accent="true"] QPushButton:checked { background: $ACCENT; color: $ACCENT_INK; }

QSlider { background: transparent; }
QSlider::groove:horizontal { height: 5px; background: $TRACK; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ACCENT; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffffff; width: 14px; height: 14px; margin: -5px 0;
                             border-radius: 7px; border: 2px solid $ACCENT; }
QSlider::handle:horizontal:hover { width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }

QProgressBar { background: $TRACK; border: none; border-radius: 2px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: $ACCENT; border-radius: 2px; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #262d3d; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #343d52; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: $RAISED; color: $TEXT; border: 1px solid $LINE; padding: 4px 8px; }
""")

QSS = _QSS.substitute(BG=BG, SURF=SURF, RAISED=RAISED, LINE=LINE, VIEW=VIEW, TEXT=TEXT, MUTED=MUTED,
                      FAINT=FAINT, ACCENT=ACCENT, ACCENT_HI=ACCENT_HI, ACCENT_INK=ACCENT_INK,
                      DANGER=DANGER, TRACK=TRACK)