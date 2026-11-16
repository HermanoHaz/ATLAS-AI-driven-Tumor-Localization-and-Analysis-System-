"""
ATLAS - AI Scanner page  (interfaces/scanner.py)

The AI engineer's MedSAM viewer, turned into a page of the ATLAS app: it uses the shared header and
footer, the ATLAS colours (theme/scanner_theme.py) and the model code in ai/segment.py.

3D view : VTK (OpenGL) - volume ray casting, textured orthogonal planes, tumor surfaces.
Slices  : per plane, a full-slice view and a zoomed detail view of the crosshair area.

Signals:  back_requested()  "Dashboard" button     user_clicked()  LOGOUT button in the header
Methods:  set_user(name, department)     cleanup()  (called when the program exits)
"""
import inspect
import os
import sys
import threading
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import numpy as np
import nrrd
import pyvista as pv
import vtk
from pyvistaqt import QtInteractor
from vtkmodules.util.numpy_support import numpy_to_vtk
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (QColor, QIcon, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QShortcut)
from PySide6.QtWidgets import (QApplication, QBoxLayout, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QSlider, QSplitter, QVBoxLayout, QWidget)

from ai import segment
from components.footer import AppFooter
from components.header import AppHeader
from theme.theme import find_logo
from theme.scanner_theme import (ACCENT, ACCENT_HI, ACCENT_INK, DANGER, FAINT, GT, GT_RGB, LINE, MUTED, OK,
                                 PLANE, PRED, PRED_RGB, TEXT, TRACK, VIEW, WARN)
from theme.scanner_theme import QSS as SCANNER_QSS

PRED_C = np.array(PRED_RGB, dtype=np.uint8)
GT_C = np.array(GT_RGB, dtype=np.uint8)
ORDER = (0, 2, 1)                                   # rows: sagittal, axial, coronal
DEFAULT_SCAN_DIR = r"C:\Users\User\Desktop\testing fyp\Tumor Data"  # default folder for "Open scan"
NAMES = {0: "Sagittal", 1: "Coronal", 2: "Axial"}
EMPTY_RESULTS = (f"<span style='color:{MUTED};'>Results appear here after you run a segmentation "
                 f"or open the actual tumor.</span>")


def get_slice(vol, a, i, rot=False):
    """2D image for plane a at index i (rows x cols). a: 0=x, 1=y, 2=z.
    rot=True draws the sagittal plane on its side (rows=y, cols=z) so a long, narrow slice is horizontal."""
    if a == 2:
        return vol[:, :, i].T
    if a == 0:
        return vol[i, :, :] if rot else np.flipud(vol[i, :, :].T)
    return np.flipud(vol[:, i, :].T)


def fmt_time(sec):
    sec = max(float(sec), 0.0)
    return f"{sec:.0f} s" if sec < 60 else f"{int(sec // 60)} min {int(sec % 60)} s"


def fmt(v):
    return f"{v:.0f}" if abs(v) >= 100 else f"{v:.2f}"


def edge_of(m):
    """Outline pixels of a 2D boolean mask."""
    inner = m.copy()
    inner[1:, :] &= m[:-1, :]
    inner[:-1, :] &= m[1:, :]
    inner[:, 1:] &= m[:, :-1]
    inner[:, :-1] &= m[:, 1:]
    return m & ~inner


def make_icon(name, color):
    """Small crisp vector icons drawn at 2x so they stay sharp on any screen."""
    pm = QPixmap(36, 36)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    p.setPen(QPen(c, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    if name == "folder":
        path = QPainterPath()
        path.moveTo(2.5, 5)
        for x, y in ((7, 5), (9, 7.2), (15.5, 7.2), (15.5, 14.5), (2.5, 14.5)):
            path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "target":
        p.drawEllipse(QPointF(9, 9), 6, 6)
        p.drawEllipse(QPointF(9, 9), 2.2, 2.2)
    elif name == "spark":
        p.setBrush(c)
        p.drawPolygon(QPolygonF([QPointF(*q) for q in ((9, 2), (10.8, 7.2), (16, 9), (10.8, 10.8),
                                                      (9, 16), (7.2, 10.8), (2, 9), (7.2, 7.2))]))
    elif name == "x":
        p.drawLine(QPointF(4.5, 4.5), QPointF(13.5, 13.5))
        p.drawLine(QPointF(13.5, 4.5), QPointF(4.5, 13.5))
    elif name == "save":
        p.drawRoundedRect(QRectF(3, 3, 12, 12), 2, 2)
        p.drawLine(QPointF(6, 3.5), QPointF(6, 7))
        p.drawLine(QPointF(6, 7), QPointF(11, 7))
        p.drawLine(QPointF(11, 7), QPointF(11, 3.5))
        p.drawRect(QRectF(5.5, 10.5, 7, 4))
    elif name == "play":
        p.setBrush(c)
        p.drawPolygon(QPolygonF([QPointF(5, 3.5), QPointF(5, 14.5), QPointF(14.5, 9)]))
    elif name == "stop":
        p.setBrush(c)
        p.drawRoundedRect(QRectF(4.5, 4.5, 9, 9), 2, 2)
    elif name == "back":
        p.drawLine(QPointF(14.5, 9), QPointF(3.5, 9))
        p.drawLine(QPointF(3.5, 9), QPointF(8, 4.5))
        p.drawLine(QPointF(3.5, 9), QPointF(8, 13.5))
    p.end()
    return QIcon(pm)


# ----------------------------------------------------------------- widgets
class Segmented(QFrame):
    changed = Signal(str)

    def __init__(self, options, value, accent=False):
        super().__init__()
        self.setObjectName("seg")
        self.setProperty("accent", "true" if accent else "false")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.group, self.buttons, self.value = QButtonGroup(self), {}, value
        self.group.setExclusive(True)
        for key, text in options:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setChecked(key == value)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            self.group.addButton(b)
            lay.addWidget(b, 1)
            self.buttons[key] = b

    def _pick(self, key):
        self.value = key
        self.changed.emit(key)

    def set(self, key):
        self.value = key
        self.buttons[key].setChecked(True)


class RangeSlider(QWidget):
    """Two-handle slider over 0..1."""
    changed = Signal(float, float)

    def __init__(self, lo=0.0, hi=1.0):
        super().__init__()
        self.lo, self.hi, self.active = lo, hi, None
        self.setFixedHeight(26)
        self.setCursor(Qt.PointingHandCursor)

    def set(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.update()

    def _x(self, v):
        return 10 + v * (self.width() - 20)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cy = self.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(TRACK))
        p.drawRoundedRect(QRectF(10, cy - 2.5, self.width() - 20, 5), 2.5, 2.5)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(QRectF(self._x(self.lo), cy - 2.5, self._x(self.hi) - self._x(self.lo), 5), 2.5, 2.5)
        for v in (self.lo, self.hi):
            p.setBrush(QColor("#ffffff"))
            p.setPen(QPen(QColor(ACCENT), 2))
            p.drawEllipse(QPointF(self._x(v), cy), 7, 7)

    def mousePressEvent(self, e):
        x = e.position().x()
        self.active = "lo" if (abs(x - self._x(self.lo)) < abs(x - self._x(self.hi)) or x < self._x(self.lo)) else "hi"
        self._move(x)

    def mouseMoveEvent(self, e):
        self._move(e.position().x())

    def _move(self, x):
        v = min(max((x - 10) / max(self.width() - 20, 1), 0.0), 1.0)
        if self.active == "lo":
            self.lo = min(v, self.hi - 0.005)
        else:
            self.hi = max(v, self.lo + 0.005)
        self.update()
        self.changed.emit(self.lo, self.hi)


class Toggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, text, checked=True):
        super().__init__()
        self.text, self.on = text, checked
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self):
        return self.on

    def mousePressEvent(self, _e):
        self.on = not self.on
        self.update()
        self.toggled.emit(self.on)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cy = self.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT if self.on else "#33404f"))
        p.drawRoundedRect(QRectF(1, cy - 10, 36, 20), 10, 10)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(28 if self.on else 11, cy), 7.5, 7.5)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(48, 0, self.width() - 48, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text)


class SliceView(QWidget):
    """A slice view. detail=False: full slice (axial lets you drag a box).
    detail=True: magnified crop around the crosshair (click to move the crosshair)."""
    cross = Signal(int, float, float)
    boxChanged = Signal(object)
    step = Signal(int, int)
    expand = Signal(int)

    def __init__(self, axis, detail=False):
        super().__init__()
        self.axis, self.detail = axis, detail
        self.qimg, self.rgb = None, None
        self._scaled, self._scaled_key = None, None
        self.nc = self.nr = 1
        self.crop = (0, 0, 1, 1)                      # c0, r0, width, height in image pixels
        self.sc = self.sr = 1.0
        self.cross_pos, self.cross_cols = (0, 0), (PLANE[0], PLANE[1])
        self.box, self.locator = None, None
        self.press, self.moved = None, False
        self.setMinimumSize(40, 40)
        self.setCursor(Qt.CrossCursor)

    def set_slice(self, rgb, spacing, cross_pos, cross_cols, box=None, crop=None, locator=None):
        self.rgb = np.ascontiguousarray(rgb)
        h, w = self.rgb.shape[:2]
        self.qimg = QImage(self.rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._scaled = None
        self.nc, self.nr, (self.sc, self.sr) = w, h, spacing
        self.crop = crop if crop else (0, 0, w, h)
        self.cross_pos, self.cross_cols, self.box, self.locator = cross_pos, cross_cols, box, locator
        self.update()

    def _geom(self):
        c0, r0, cw, rh = self.crop
        W, H = self.width(), self.height()
        wp, hp = cw * self.sc, rh * self.sr
        f = min(W / wp, H / hp)
        dw, dh = wp * f, hp * f
        return (W - dw) / 2, (H - dh) / 2, dw, dh

    def _scaled_image(self, dw, dh):
        dpr = self.devicePixelRatioF()
        key = (round(dw * dpr), round(dh * dpr), dpr, self.crop)
        if self._scaled is None or self._scaled_key != key:
            c0, r0, cw, rh = self.crop
            src = self.qimg.copy(c0, r0, cw, rh) if self.crop != (0, 0, self.nc, self.nr) else self.qimg
            img = src.scaled(key[0], key[1], Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            img.setDevicePixelRatio(dpr)
            self._scaled, self._scaled_key = img, key
        return self._scaled

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(VIEW))
        if self.qimg is None:
            p.setPen(QColor(FAINT))
            p.drawText(self.rect(), Qt.AlignCenter, "No scan")
            return
        ox, oy, dw, dh = self._geom()
        c0, r0, cw, rh = self.crop
        kx, ky = dw / cw, dh / rh
        p.drawImage(QPointF(ox, oy), self._scaled_image(dw, dh))
        p.setClipRect(QRectF(ox, oy, dw, dh))
        cc, rc = self.cross_pos
        px, py = ox + (cc - c0) * kx, oy + (rc - r0) * ky
        for col, line in ((self.cross_cols[0], (px, oy, px, oy + dh)), (self.cross_cols[1], (ox, py, ox + dw, py))):
            c = QColor(col)
            c.setAlpha(190)
            p.setPen(QPen(c, 1.2))
            p.drawLine(QPointF(line[0], line[1]), QPointF(line[2], line[3]))
        if self.axis == 2 and self.box:
            x0, y0, x1, y1 = self.box
            r = QRectF(ox + (x0 - c0) * kx, oy + (y0 - r0) * ky, (x1 - x0) * kx, (y1 - y0) * ky)
            fill = QColor(ACCENT)
            fill.setAlpha(36)
            p.setBrush(fill)
            p.setPen(QPen(QColor(ACCENT_HI), 1.6))
            p.drawRect(r)
            if not self.detail:
                p.setBrush(QColor("#ffffff"))
                p.setPen(QPen(QColor(ACCENT), 1.6))
                for corner in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                    p.drawEllipse(corner, 3.5, 3.5)
        if self.locator and not self.detail:       # shows which part the detail view magnifies
            a0, b0, a1, b1 = self.locator
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 170), 1, Qt.DashLine))
            p.drawRect(QRectF(ox + a0 * kx, oy + b0 * ky, (a1 - a0) * kx, (b1 - b0) * ky))

    def _img_xy(self, e):
        ox, oy, dw, dh = self._geom()
        c0, r0, cw, rh = self.crop
        c = c0 + (e.position().x() - ox) / dw * cw
        r = r0 + (e.position().y() - oy) / dh * rh
        return min(max(c, 0), self.nc - 1e-6), min(max(r, 0), self.nr - 1e-6)

    def mousePressEvent(self, e):
        if self.qimg is None or e.button() != Qt.LeftButton:
            return
        self.press, self.moved = (e.position(), self._img_xy(e)), False
        if self.axis != 2 or self.detail:
            self.cross.emit(self.axis, *self._img_xy(e))

    def mouseMoveEvent(self, e):
        if self.press is None:
            return
        c, r = self._img_xy(e)
        if self.axis != 2 or self.detail:
            self.cross.emit(self.axis, c, r)
            return
        d = e.position() - self.press[0]
        if abs(d.x()) + abs(d.y()) > 4:
            self.moved = True
        if self.moved:
            c0, r0 = self.press[1]
            self.box = (min(c0, c), min(r0, r), max(c0, c), max(r0, r))
            self.update()

    def mouseReleaseEvent(self, e):
        if self.press is None:
            return
        if self.axis == 2 and not self.detail:
            if self.moved:
                self.boxChanged.emit(self.box)
            else:
                self.cross.emit(2, *self._img_xy(e))
        self.press = None

    def mouseDoubleClickEvent(self, _e):
        self.expand.emit(self.axis)

    def wheelEvent(self, e):
        self.step.emit(self.axis, 1 if e.angleDelta().y() > 0 else -1)


class PlanePane(QWidget):
    """Holds the full-slice view and the zoom view of one plane and sizes them to the image shape:
    the full view always matches the slice aspect ratio, so a portrait slice gets a vertical box."""
    resized = Signal()

    def __init__(self, full, detail):
        super().__init__()
        self.full, self.detail = full, detail
        full.setParent(self)
        detail.setParent(self)
        self.aspect, self.stack = 1.0, True
        self.setMinimumSize(120, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_aspect(self, aspect):
        self.aspect = max(aspect, 0.05)
        self._place()

    def set_stack(self, stack):
        self.stack = stack
        self._place()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place()
        self.resized.emit()

    def _place(self):
        W, H, gap = self.width(), self.height(), 10
        if W < 40 or H < 40:
            return
        if self.stack:                      # full view on top, zoom view below it
            w1 = min(W, 0.36 * H * self.aspect)
            h1 = w1 / self.aspect
            self.full.setGeometry(round((W - w1) / 2), 0, round(w1), round(h1))
            self.detail.setGeometry(0, round(h1) + gap, W, max(H - round(h1) - gap, 20))
        else:                               # full view on the left, zoom view on the right
            h1 = min(H, 0.38 * W / self.aspect)
            w1 = h1 * self.aspect
            self.full.setGeometry(0, 0, round(w1), round(h1))
            self.detail.setGeometry(round(w1) + gap, 0, max(W - round(w1) - gap, 20), H)
        self.full.show()
        self.detail.show()


class SegThread(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, float, bool)     # runs finished, expected total, seconds this run took, reused

    def __init__(self, vol, k, box, center, width, follow, step, spacing, cache_key):
        super().__init__()
        self.args = (vol, k, box, center, width, follow, step, spacing, cache_key)

    def run(self):
        try:
            t0 = time.perf_counter()
            was_loaded = segment.is_loaded()
            seg = segment.get_segmenter()                 # waits if the model is still loading
            t1 = time.perf_counter()
            vol, k, box, c, w, follow, step, spacing, key = self.args
            mask = seg.segment_volume(vol, k, box, c, w, follow, step, spacing, cache_key=key,
                                      progress=self.progress.emit)
            t2 = time.perf_counter()
            self.done.emit({"mask": mask, "load_s": 0.0 if was_loaded else t1 - t0, "seg_s": t2 - t1,
                            "calls": seg.last_calls, "reused": seg.last_reused})
        except Exception as e:
            msg = str(e)
            if "out of memory" in msg.lower():
                msg += ("\n\nThe GPU memory is full. Close other programs that use the GPU "
                        "(browser, games) and try again, or set SAM_DEVICE=cpu.")
            self.failed.emit(msg)


class PrefetchThread(QThread):
    """Runs the slow image encoder on slices in the background while the GPU would otherwise sit idle
    (you are looking at the scan or drawing the box). A later run reuses those results. It pauses while
    you are working with the views and stops completely while a segmentation runs, so only one thing
    uses the GPU at a time."""

    def __init__(self, user_idle):
        super().__init__()
        self.user_idle, self.cv, self.task = user_idle, threading.Condition(), None
        self.alive, self.paused = True, False
        self.gate = threading.Lock()
        self.free = threading.Event()
        self.free.set()                                  # set whenever no slice is being encoded

    def set_task(self, task):                            # task = (vol, slice list, center, width, cache key) or None
        with self.cv:
            self.task = task
            self.cv.notify()

    def pause_and_wait(self, timeout=3.0):
        with self.gate:
            self.paused = True
        self.free.wait(timeout)                          # lets a slice that is already running finish

    def stop(self):
        self.alive = False
        with self.cv:
            self.cv.notify()

    def run(self):
        while self.alive:
            with self.cv:
                while self.alive and self.task is None:
                    self.cv.wait(0.5)
                task = self.task
            if not self.alive or task is None:
                continue
            vol, ks, center, width, key = task
            try:
                if not segment.checkpoint_ready():
                    raise RuntimeError("no weights")
                seg = segment.get_segmenter()
                i = 0
                while self.alive and i < len(ks) and self.task is task:
                    with self.gate:
                        ready = (not self.paused) and self.user_idle()
                        if ready:
                            self.free.clear()
                    if not ready:
                        self.msleep(200)
                        continue
                    try:
                        seg.prefetch_slice(vol, ks[i], center, width, key)
                    finally:
                        self.free.set()
                    i += 1
                    self.msleep(80)
            except Exception:
                pass                                     # best effort only: never disturb the user
            with self.cv:
                if self.task is task:
                    self.task = None


class WarmThread(QThread):
    """Loads MedSAM and runs one dummy slice in the background right after start-up."""
    ready = Signal()
    failed = Signal(str)

    def run(self):
        try:
            segment.get_segmenter()
            self.ready.emit()
        except Exception as e:
            self.failed.emit(str(e))


# ------------------------------------------------------------------ helpers
def make_card(title=None):
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(8)
    if title:
        t = QLabel(title)
        t.setObjectName("cardTitle")
        lay.addWidget(t)
    return f, lay


def label(text="", muted=True, wrap=False, name=None):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    elif muted:
        lb.setObjectName("muted")
    lb.setWordWrap(wrap)
    return lb


def button(text, slot, primary=False, icon=None):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    if icon:
        b.setIcon(make_icon(icon, ACCENT_INK if primary else TEXT))
        b.setIconSize(QSize(18, 18))
    b.setCursor(Qt.PointingHandCursor)
    b.setMinimumHeight(38)
    b.clicked.connect(slot)
    return b


def row(*widgets):
    h = QHBoxLayout()
    h.setSpacing(8)
    for w in widgets:
        h.addWidget(w)
    return h


# --------------------------------------------------------------- main window
class ScannerPage(QWidget):
    back_requested = Signal()        # "Dashboard" button
    user_clicked = Signal()          # user chip in the header
    settings_clicked = Signal()      # settings gear in the shared header

    def __init__(self, parent=None):
        super().__init__(parent)
        icon_path = find_logo("Atlas_Bulat")
        self._atlas_icon = QIcon(icon_path) if icon_path else QIcon()
        if not self._atlas_icon.isNull():
            self.setWindowIcon(self._atlas_icon)
        self.setMinimumSize(1100, 700)

        self.vol = self.mask = self.gt = self.seg = self.grid = None
        self.spacing, self.md, self.vmin, self.vmax, self.name = (1, 1, 1), 1.0, 0.0, 1.0, ""
        self.idx, self.mode, self.box = [0, 0, 0], "2d", None
        self.pred_cc = self.gt_cc = self.dice = self.run_info = None
        self.opacity, self.dir, self.light, self.zoom = 0.25, "Left", False, 3.0
        self.props, self.slices, self.outlines = [], {}, {}
        self.mask_actor = self.gt_actor = None
        self.expanded, self._sized, self._pending = None, False, (False, False)
        self.layout_mode, self.n_live = "rows", 0
        self.eta, self.pct_shown = None, 0
        self.gt_stash, self.gt_name = None, ""          # a hidden actual tumor is kept here so it can come back
        self.last_dir = ""
        self.sag_rot = False
        self._ui_dark = True
        self.p_done, self.p_exp, self.t_first, self.p_last = 0, 1, None, 0.0
        self.thread, self.t_run = None, 0.0

        self._build()
        self.anim = QTimer(self)
        self.anim.timeout.connect(self.anim_tick)
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self.tick_run)
        self.last_activity = time.perf_counter()
        self.prefetch = PrefetchThread(lambda: time.perf_counter() - self.last_activity > 1.0)
        self.prefetch.start()
        self.pf_timer = QTimer(self)
        self.pf_timer.setSingleShot(True)
        self.pf_timer.timeout.connect(self.do_prefetch)
        QShortcut(QKeySequence("Up"), self, activated=lambda: self.wheel(2, 1))
        QShortcut(QKeySequence("Down"), self, activated=lambda: self.wheel(2, -1))
        self.set_bg_mode("dark")
        self.set_mode("2d")
        self.set_layout("rows")                 # always: each plane is a row, full view left, zoom view right
        self.update_hint()
        QTimer.singleShot(600, self.start_warmup)

    def set_user(self, full_name: str, department: str = ""):
        self.header.set_user(full_name, department)

    def set_photo(self, pixmap):
        """Profile photo shown in the header avatar (QPixmap or None)."""
        self.header.set_photo(pixmap)

    def set_theme(self, dark: bool):
        """Switch scanner controls and panels between dark and light UI palettes."""
        global TEXT, MUTED, FAINT, ACCENT, ACCENT_HI, LINE
        self._ui_dark = bool(dark)
        if dark:
            TEXT, MUTED, FAINT = "#e8eef2", "#8b959d", "#5b6670"
            ACCENT, ACCENT_HI, LINE = "#7c5cff", "#a98bff", "#1f2433"
            self._scanner_content.setStyleSheet(SCANNER_QSS)
        else:
            TEXT, MUTED, FAINT = "#20182e", "#665f73", "#847c90"
            ACCENT, ACCENT_HI, LINE = "#7048b8", "#815abd", "#d7d0e0"
            qss = SCANNER_QSS
            replacements = {
                "#05070c": "#f4f1f8", "#0d1017": "#ffffff", "#141a26": "#efebf5",
                "#1f2433": "#d7d0e0", "#04060a": "#ffffff", "#e8eef2": "#20182e",
                "#8b959d": "#665f73", "#5b6670": "#847c90", "#7c5cff": "#7048b8",
                "#a98bff": "#815abd", "#0a0d14": "#f3f0f7", "#111620": "#ffffff",
                "#0d1118": "#f5f2f9", "#1a1f2e": "#e8e2f0", "#1c2333": "#eae5f2",
                "#2f3a5a": "#b6a8ca", "#0e1219": "#eeeaf4", "#151a26": "#d7d0e0",
                "#20263a": "#e4dced", "#262d3d": "#d6cee0", "#343d52": "#c6bbd6",
            }
            for old, new in replacements.items():
                qss = qss.replace(old, new)
            self._scanner_content.setStyleSheet(qss)
        self._scanner_content.update()
        self.update()

    # ------------------------------------------------------------- build UI
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = AppHeader()                       # shared ATLAS header
        self.header.logout_clicked.connect(self.user_clicked.emit)
        self.header.settings_clicked.connect(self.settings_clicked.emit)
        outer.addWidget(self.header)

        content = QWidget()                             # the viewer keeps its own stylesheet inside this box
        self._scanner_content = content
        content.setStyleSheet(SCANNER_QSS)
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(56)
        t = QHBoxLayout(top)
        t.setContentsMargins(20, 0, 20, 0)
        t.setSpacing(10)
        btn_back = button("Dashboard", self.back_requested.emit, icon="back")
        btn_back.setMinimumHeight(34)
        t.addWidget(btn_back)
        title = QLabel("AI SCANNER")
        title.setObjectName("title")
        t.addWidget(title)
        self.file_lbl = label("No scan open", name="pill")
        self.gt_lbl = label("", name="pill")
        self.gt_lbl.setStyleSheet(f"color:{GT};")
        self.gt_lbl.hide()
        t.addWidget(self.file_lbl)
        t.addWidget(self.gt_lbl)
        self.sam_lbl = label("", name="pill")           # used only if the footer cannot show the status
        self.sam_lbl.hide()
        t.addWidget(self.sam_lbl)
        t.addStretch()
        self.seg_bg = Segmented([("dark", "Dark"), ("light", "Light")], "dark")
        self.seg_bg.setFixedWidth(180)
        self.seg_bg.changed.connect(self.set_bg_mode)
        self.seg_mode = Segmented([("2d", "Planes"), ("3d", "Volume")], "2d", accent=True)
        self.seg_mode.setFixedWidth(200)
        self.seg_mode.changed.connect(self.set_mode)
        t.addWidget(self.seg_bg)
        t.addWidget(self.seg_mode)
        self.btn_gt = button("Remove actual", self.toggle_actual, icon="x")
        self.btn_gt.setFixedWidth(160)
        self.btn_gt.setEnabled(False)
        self.btn_gt.setToolTip("No actual tumor is loaded")
        t.addWidget(self.btn_gt)
        btn_open = button("Open scan", self.open_file, primary=True, icon="folder")
        btn_open.setFixedWidth(140)
        btn_open.setToolTip("Choose the scan. Its actual tumor is opened automatically: the file with the same number "
                            "(DATA_130 and MASK_130). Or hold Ctrl and select both files yourself.")
        t.addWidget(btn_open)
        v.addWidget(top)

        body = QHBoxLayout()
        body.setContentsMargins(16, 12, 16, 10)
        body.setSpacing(12)
        v.addLayout(body, 1)
        body.addWidget(self._sidebar())
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(12)
        self.splitter.addWidget(self._viewport())
        self.splitter.addWidget(self._slice_area())
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        body.addWidget(self.splitter, 1)

        outer.addWidget(content, 1)
        self.footer = AppFooter()                       # shared ATLAS footer (shows the MedSAM status)
        outer.addWidget(self.footer)
        self.set_sam_state("will run")

    def showEvent(self, e):
        super().showEvent(e)
        if not self._atlas_icon.isNull():
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(self._atlas_icon)
            self.window().setWindowIcon(self._atlas_icon)
        if not self._sized:
            self._sized = True
            QTimer.singleShot(0, self.push_slices_right)
            QTimer.singleShot(250, self.push_slices_right)      # again once the window has finished maximizing

    def push_slices_right(self):
        """Default position: divider dragged all the way to the right, so the 3D view gets the room."""
        self.splitter.setSizes([self.splitter.width(), 1])

    def _set_status(self, text, online):
        """Show the MedSAM status in the footer; if this footer has no status area, use a pill in the toolbar."""
        try:
            self.footer.set_status(text, online=online)
            self.sam_lbl.hide()
        except Exception:
            self.sam_lbl.setText(text)
            self.sam_lbl.setStyleSheet(f"color:{OK if online else DANGER};")
            self.sam_lbl.show()

    def set_sam_state(self, verb):
        dev = segment.device_info()
        prec = f" ({segment.precision()})" if segment.precision() else ""
        self._set_status(f"{segment.MODEL_NAME} {verb} on {dev}{prec}", dev.startswith("GPU"))

    def _sidebar(self):
        scroll = QScrollArea()
        scroll.setFixedWidth(306)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)
        scroll.setWidget(inner)

        c, cl = make_card("Display")
        cl.setSpacing(6)
        self.val_wl, self.val_th, self.val_op, self.val_zoom = (label(name="pill") for _ in range(4))
        h = row(label("Window and level", muted=False))
        h.addStretch()
        h.addWidget(self.val_wl)
        cl.addLayout(h)
        self.wl = RangeSlider()
        self.wl.changed.connect(self.on_levels)
        cl.addWidget(self.wl)
        h = row(label("Threshold", muted=False))
        h.addStretch()
        h.addWidget(self.val_th)
        cl.addLayout(h)
        self.th = RangeSlider()
        self.th.changed.connect(self.on_levels)
        cl.addWidget(self.th)
        h = row(label("Zoom view magnification", muted=False))
        h.addStretch()
        h.addWidget(self.val_zoom)
        cl.addLayout(h)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(15, 80)
        self.zoom_slider.setValue(int(self.zoom * 10))
        self.zoom_slider.valueChanged.connect(self.on_zoom)
        cl.addWidget(self.zoom_slider)
        self.op_head = [label("Opacity", muted=False), self.val_op]
        h = row(self.op_head[0])
        h.addStretch()
        h.addWidget(self.op_head[1])
        cl.addLayout(h)
        self.op_slider = QSlider(Qt.Horizontal)
        self.op_slider.setRange(2, 100)
        self.op_slider.setValue(int(self.opacity * 100))
        self.op_slider.valueChanged.connect(self.on_opacity)
        cl.addWidget(self.op_slider)
        self.op_widgets = self.op_head + [self.op_slider]
        self.info = label("No scan loaded. Use Open scan.", wrap=True)
        cl.addWidget(self.info)
        lay.addWidget(c)

        c, cl = make_card("Segmentation")
        cl.setSpacing(7)
        self.follow = Toggle("Follow through slices")
        cl.addWidget(self.follow)
        self.prefetch_on = Toggle("Prepare slices in the background")
        self.prefetch_on.setToolTip("Uses the time while you look at the scan to get slices ready, so Run is much faster. "
                                    "Turn off to time a cold run, or if the views feel slow.")
        self.prefetch_on.toggled.connect(lambda _on: self.do_prefetch())
        cl.addWidget(self.prefetch_on)
        h = row(label("Speed", muted=False))
        h.addStretch()
        self.quality = Segmented([("1", "Best"), ("0", "Smart"), ("3", "Fast")], "0")
        self.quality.setToolTip("Best: every slice. Smart: skips slices where the shape changes smoothly. "
                                "Fast: every 3rd slice.")
        h.addWidget(self.quality)
        cl.addLayout(h)
        self.btn_gtbox = button("Box from actual tumor", self.box_from_actual, icon="target")
        self.btn_run = button("Run segmentation", self.run_seg, primary=True, icon="spark")
        self.btn_clr = button("Clear", self.clear_mask, icon="x")
        self.btn_save = button("Save mask", self.save_mask, icon="save")
        for w in (self.btn_gtbox, self.btn_run, self.btn_clr, self.btn_save):
            w.setMinimumHeight(34)
            w.setEnabled(False)
        self.btn_gtbox.setToolTip("Draws a tight box around the real tumor (open the actual tumor first)")
        cl.addWidget(self.btn_gtbox)
        cl.addWidget(self.btn_run)
        cl.addLayout(row(self.btn_clr, self.btn_save))
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.hide()
        cl.addWidget(self.busy)
        self.status = label(wrap=True)
        cl.addWidget(self.status)
        lay.addWidget(c)

        c, cl = make_card()
        title = QLabel("Animation")
        title.setObjectName("cardTitle")
        self.btn_anim = button("Animate", self.toggle_anim, icon="play")
        self.btn_anim.setMinimumHeight(30)
        self.btn_anim.setFixedWidth(116)
        h = QHBoxLayout()
        h.addWidget(title)
        h.addStretch()
        h.addWidget(self.btn_anim)
        cl.addLayout(h)
        h = QHBoxLayout()
        h.setSpacing(10)
        seg = Segmented([("Left", "\u2190"), ("Right", "\u2192"), ("Up", "\u2191"), ("Down", "\u2193")], "Left")
        seg.setToolTip("Rotation direction")
        seg.changed.connect(lambda k: setattr(self, "dir", k))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(1, 10)
        self.speed.setValue(3)
        self.speed.setMinimumWidth(60)
        self.speed.setToolTip("Rotation speed")
        h.addWidget(seg)
        h.addWidget(self.speed, 1)
        cl.addLayout(h)
        lay.addWidget(c)

        c, cl = make_card("Results")
        cl.setSpacing(4)
        self.result = QLabel(EMPTY_RESULTS)
        self.result.setTextFormat(Qt.RichText)
        self.result.setWordWrap(True)
        cl.addWidget(self.result)
        lay.addWidget(c)
        lay.addWidget(label("Scroll a view to change slice. Click to move the crosshair. "
                            "Double-click a view to enlarge it.", wrap=True))
        lay.addStretch()
        return scroll

    def _make_plotter(self, frame):
        """Create the 3D widget. A failed attempt must not leave a blank widget behind on the frame."""
        wanted = {"multi_samples": 4, "line_smoothing": True, "allow_quit_keypress": False}
        try:
            names = inspect.signature(QtInteractor.__init__).parameters
            wanted = {k: v for k, v in wanted.items() if k in names}
        except (TypeError, ValueError):
            pass
        attempts = [wanted, {k: v for k, v in wanted.items() if k != "allow_quit_keypress"}, {}]
        for kw in attempts:
            before = set(frame.children())
            try:
                return QtInteractor(frame, **kw)
            except TypeError:
                for stray in set(frame.children()) - before:
                    stray.setParent(None)
                    stray.deleteLater()
        return QtInteractor(frame)

    def _viewport(self):
        frame = QFrame()
        frame.setObjectName("viewport")
        frame.setMinimumWidth(280)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)
        self.plotter = self._make_plotter(frame)
        iren = self.plotter.interactor
        lay.addWidget(iren, 1)
        if iren is not self.plotter and isinstance(self.plotter, QWidget):
            self.plotter.hide()                   # never leave an unused blank widget in the corner
        try:
            self.plotter.add_axes(line_width=2, interactive=False)
        except Exception:
            pass
        return frame

    def _slice_area(self):
        area = QWidget()
        self.slice_area = area
        self.slice_box = QBoxLayout(QBoxLayout.LeftToRight, area)
        self.slice_box.setContentsMargins(0, 0, 0, 0)
        self.slice_box.setSpacing(10)
        self.views, self.details, self.panes, self.sliders = {}, {}, {}, {}
        self.idx_lbl, self.cards, self.caps = {}, {}, {}
        for a in ORDER:
            c, cl = make_card()
            cl.setContentsMargins(12, 10, 12, 12)
            cl.setSpacing(6)
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background:{PLANE[a]}; border-radius:5px;")
            name = QLabel(NAMES[a])
            name.setObjectName("cardTitle")
            name.setFixedWidth(60)
            s = QSlider(Qt.Horizontal)
            s.setMinimumWidth(50)
            s.setStyleSheet(f"QSlider::sub-page:horizontal{{background:{PLANE[a]}; border-radius:2px;}}"
                            f"QSlider::handle:horizontal{{background:#fff; width:14px; height:14px; margin:-5px 0;"
                            f"border-radius:7px; border:2px solid {PLANE[a]};}}")
            s.valueChanged.connect(lambda val, a=a: self.set_idx(a, val))
            self.idx_lbl[a] = label(name="pill")
            head = QHBoxLayout()
            head.setSpacing(8)
            head.addWidget(dot)
            head.addWidget(name)
            head.addWidget(s, 1)
            head.addWidget(self.idx_lbl[a])
            cl.addLayout(head)
            self.caps[a] = label("", name="hint")        # axial: the segmentation hint; others: a caption
            self.caps[a].setWordWrap(True)
            cl.addWidget(self.caps[a])

            full, zoom = SliceView(a), SliceView(a, detail=True)
            for w in (full, zoom):
                w.cross.connect(self.set_cross)
                w.step.connect(self.wheel)
                w.expand.connect(self.toggle_expand)
            full.boxChanged.connect(self.on_box)
            pane = PlanePane(full, zoom)
            pane.resized.connect(lambda: self.request(panels=True, scene=False))
            cl.addWidget(pane, 1)
            self.views[a], self.details[a], self.panes[a] = full, zoom, pane
            self.sliders[a], self.cards[a] = s, c
            self.slice_box.addWidget(c, 1)
        self.axial_hint = self.caps[2]           # the hint sits above the view, never on the image
        return area

    def set_layout(self, k):
        """Columns: each plane is a tall column (full view above, zoom below). Rows: views side by side."""
        self.layout_mode = k
        cols = k == "cols"
        self.slice_box.setDirection(QBoxLayout.LeftToRight if cols else QBoxLayout.TopToBottom)
        self.slice_area.setMinimumWidth(700 if cols else 480)
        for a in ORDER:
            self.panes[a].set_stack(cols)
        self.apply_stretch()
        QTimer.singleShot(0, self.push_slices_right)
        self.request(panels=True, scene=False)

    def apply_stretch(self):
        """Give each plane the width its image shape needs, so portrait slices get a narrower, taller box."""
        for a in ORDER:
            asp = 1.0
            if self.vol is not None:
                nc, nr = self.dims(a)
                sc, sr = self.pix_sp(a)
                asp = (nc * sc) / (nr * sr)
            self.panes[a].set_aspect(asp)
            self.slice_box.setStretchFactor(self.cards[a],
                                            max(int(asp * 100), 35) if self.layout_mode == "cols" else 100)

    def box_from_actual(self):
        """Draw a tight box around the real tumor (the standard way MedSAM is evaluated)."""
        if self.gt is None:
            return
        k, b = segment.box_from_mask(self.gt, pad=3)
        self.idx[2] = k
        self.sliders[2].blockSignals(True)
        self.sliders[2].setValue(k)
        self.sliders[2].blockSignals(False)
        self.box = (b[0], b[1], b[2], b[3], k)
        self.btn_run.setEnabled(True)
        self.update_hint()
        self.request()

    def toggle_expand(self, a):
        self.expanded = None if self.expanded == a else a
        for b, card in self.cards.items():
            card.setVisible(self.expanded in (None, b))
        if self.expanded is None:
            self.push_slices_right()
        else:                                   # make room so the enlarged plane is really bigger
            w = self.splitter.width()
            self.splitter.setSizes([int(w * 0.42), int(w * 0.58)])
        self.request(panels=True, scene=False)

    def update_hint(self):
        h, on = self.axial_hint, False
        if self.vol is None:
            text = "Open a scan to start."
        elif self.mask is not None:
            text = "Predicted tumor is pink."
        elif self.box is not None:
            text, on = f"Box set on slice {self.box[4] + 1}. Press Run.", True
        else:
            text = "Drag on the image to outline the tumor."
        h.setText(text)
        h.setStyleSheet(f"color:{ACCENT_HI}; font-weight:600; font-size:12px;" if on else "")

    # ------------------------------------------------------------ settings
    def set_mode(self, m):
        self.mode = m
        self.seg_mode.set(m)
        for w in self.op_widgets:
            w.setVisible(m == "3d")
        self.apply_visibility()
        self.update_readouts()
        self.update_labels()
        self.render3d()

    def set_bg_mode(self, k):
        self.light = k == "light"
        self.seg_bg.set(k)
        try:
            if self.light:
                self.plotter.set_background("#e6ebf1", top="#ffffff")
            else:
                self.plotter.set_background("#0a0f16", top="#1b2635")
        except Exception:
            self.plotter.set_background("#ffffff" if self.light else "#0a0f16")
        self.update_labels()
        self.render3d()

    def update_labels(self):
        col = "#1b2430" if self.light else "#e8eef4"
        mode = "Orthogonal planes" if self.mode == "2d" else "Volume rendering"
        try:
            self.plotter.add_text(mode if self.vol is not None else "Open a scan to begin", position="upper_left",
                                  font_size=11, color=col, name="mode_label")
            self.plotter.add_text("Drag to rotate, scroll to zoom" if self.vol is not None else " ",
                                  position="lower_edge", font_size=9, color="#8a99a9", name="hint_label")
            self.plotter.add_text(f"Predicted {self.pred_cc:.2f} cc" if self.pred_cc is not None else " ",
                                  position="upper_right", font_size=11, color=PRED, name="tumor_label")
            self.plotter.add_text(f"Actual {self.gt_cc:.2f} cc" if self.gt_cc is not None else " ",
                                  position="upper_edge", font_size=11, color=GT, name="gt_label")
        except Exception:
            pass

    def levels(self):
        r = max(self.vmax - self.vmin, 1e-6)
        return (self.vmin + self.wl.lo * r, self.vmin + self.wl.hi * r,
                self.vmin + self.th.lo * r, self.vmin + self.th.hi * r)

    def update_readouts(self):
        self.val_op.setText(f"{int(self.opacity * 100)}%")
        self.val_zoom.setText(f"{self.zoom:.1f}x")
        for a in (0, 1):
            self.caps[a].setText(f"Full slice and {self.zoom:.1f}x zoom view")
        if self.vol is None:
            self.val_wl.setText("-")
            self.val_th.setText("-")
            return
        lo, hi, tl, th = self.levels()
        self.val_wl.setText(f"{fmt(lo)} to {fmt(hi)}")
        self.val_th.setText(f"{fmt(tl)} to {fmt(th)}")

    def on_levels(self, *_):
        self.update_readouts()
        self.request(panels=True, scene=True)

    def on_opacity(self, v):
        self.opacity = v / 100.0
        self.update_readouts()
        self.request(panels=False, scene=True)

    def on_zoom(self, v):
        self.zoom = v / 10.0
        self.update_readouts()
        self.request(panels=True, scene=False)

    # -------------------------------------------------------------- files
    def open_file(self):
        start = DEFAULT_SCAN_DIR if os.path.isdir(DEFAULT_SCAN_DIR) else self.last_dir     # straight to the DATA folder
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open scan (also select its actual tumor file to open both)", start,
            "NRRD (*.nrrd *.nhdr);;All files (*)")
        if not paths:
            return
        self.last_dir = os.path.dirname(paths[0])
        if len(paths) > 2:
            QMessageBox.information(self, "Too many files",
                                    "Select one scan, or the scan together with its actual tumor file.")
            return
        base = lambda p: p.replace("\\", "/").split("/")[-1]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if len(paths) == 2:                  # the scan and the actual tumor, in any order
                pair = segment.load_pair(paths[0], paths[1])
                vol, spacing, scan_path = pair["vol"], pair["spacing"], pair["scan_path"]
                gt, gt_path = pair["mask"], pair["mask_path"]
            else:
                vol, spacing = segment.load_nrrd(paths[0])
                scan_path, gt, gt_path = paths[0], None, None
            self.load_volume(vol, spacing, base(scan_path))
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Could not open file", str(e))
            return
        QApplication.restoreOverrideCursor()
        if gt is None:                           # one scan chosen: find its tumor by the number in the name
            gt_path = segment.find_matching_mask(scan_path)
            if gt_path is None:
                num = segment.case_number(scan_path)
                self.status.setText(f"No actual tumor found for number {num}." if num is not None else
                                    "The file name has no number after an underscore, so its actual tumor "
                                    "could not be matched.")
                return
            try:
                gt = segment.load_mask(gt_path)
            except Exception as e:
                self.status.setText(f"Could not read {base(gt_path)}: {e}")
                return
        self.apply_actual(gt, base(gt_path))

    def load_volume(self, vol, spacing, name):
        self.vol, self.spacing, self.name = vol, spacing, name
        self.mask = self.gt = self.box = None
        self.gt_stash = None
        self.pred_cc = self.gt_cc = self.dice = self.run_info = None
        nx, ny, nz = vol.shape
        self.sag_rot = nz * spacing[2] > ny * spacing[1]          # sagittal: long side horizontal
        segment.clear_cache()
        self.prefetch.set_task(None)
        self.md = max(nx * spacing[0], ny * spacing[1], nz * spacing[2])
        self.vmin, self.vmax = float(vol.min()), float(vol.max())
        rng = max(self.vmax - self.vmin, 1e-6)
        p1, p99 = np.percentile(vol, [1, 99])
        self.wl.set((p1 - self.vmin) / rng, max((p99 - self.vmin) / rng, (p1 - self.vmin) / rng + 0.01))
        self.th.set(0.0, 1.0)
        self.idx = [nx // 2, ny // 2, nz // 2]
        for a in range(3):
            s = self.sliders[a]
            s.blockSignals(True)
            s.setRange(0, vol.shape[a] - 1)
            s.setValue(self.idx[a])
            s.blockSignals(False)

        u16 = np.clip((vol - self.vmin) / rng * 65535.0, 0, 65535).astype(np.uint16)
        self.grid = pv.ImageData(dimensions=vol.shape, spacing=spacing, origin=(0.0, 0.0, 0.0))
        self.grid.point_data["scalars"] = u16.flatten(order="F")
        self.grid.set_active_scalars("scalars")
        self.build_scene()

        sx, sy, sz = spacing
        self.file_lbl.setText(name)
        self.gt_lbl.hide()
        self.info.setText(f"{name}\n{nx} x {ny} x {nz} voxels, {sx:.2f} x {sy:.2f} x {sz:.2f} mm")
        self.apply_stretch()
        self.status.setText("")
        self.update_gt_button()                    # no actual tumor until one is found for this scan
        for w in (self.btn_gtbox, self.btn_run, self.btn_clr, self.btn_save):
            w.setEnabled(False)
        self.update_results()
        self.update_readouts()
        self.update_labels()
        self.update_hint()
        self.request(panels=True, scene=True)

    def update_gt_button(self):
        """One button, two jobs: hide the actual tumor, or bring a hidden one back."""
        if self.gt is not None:
            text, icon, tip, on = "Remove actual", "x", "Hide the actual tumor (you can show it again)", True
        elif self.gt_stash is not None:
            text, icon, tip, on = "Show actual", "target", "Show the actual tumor again", True
        else:
            text, icon, tip, on = "Remove actual", "x", "No actual tumor is loaded", False
        self.btn_gt.setText(text)
        self.btn_gt.setIcon(make_icon(icon, TEXT))
        self.btn_gt.setToolTip(tip)
        self.btn_gt.setEnabled(on)

    def toggle_actual(self):
        """Hide the actual tumor (it stays in memory) or show it again."""
        if self.gt is not None:
            self.gt_stash = (self.gt, self.gt_name)
            self.gt = self.gt_cc = self.dice = None
            self.set_surface("gt_actor", None)
            self.gt_lbl.hide()
            self.btn_gtbox.setEnabled(False)
            self.status.setText("Actual tumor hidden.")
            self.update_gt_button()
            self.update_results()
            self.update_labels()
            self.update_hint()
            self.request()
        elif self.gt_stash is not None:
            gt, name = self.gt_stash
            self.apply_actual(gt, name, jump=False)
            self.status.setText("Actual tumor shown.")

    def apply_actual(self, gt, name, jump=True):
        if gt.shape != self.vol.shape:
            QMessageBox.warning(self, "Size does not match",
                                f"The actual-tumor file is {gt.shape} but the scan is {self.vol.shape}.\n"
                                "Open the tumor file that belongs to this scan.")
            return
        if not gt.any():
            QMessageBox.warning(self, "No tumor found", "This file does not contain any tumor voxels.")
            return
        self.gt, self.gt_cc, self.gt_name, self.gt_stash = gt, segment.volume_cc(gt, self.spacing), name, None
        self.gt_lbl.setText(f"Actual: {name}")
        self.gt_lbl.show()
        self.set_surface("gt_actor", gt, GT, 0.6, "gt_surface", ambient=0.65)
        self.update_gt_button()
        self.btn_gtbox.setEnabled(True)
        if self.mask is not None:
            self.dice = segment.dice(self.mask, gt)
        if jump:                                  # move the crosshair to the middle of the real tumor
            centre = np.argwhere(gt).mean(axis=0).round().astype(int)
            for a in range(3):
                self.idx[a] = int(min(max(centre[a], 0), self.vol.shape[a] - 1))
                self.sliders[a].blockSignals(True)
                self.sliders[a].setValue(self.idx[a])
                self.sliders[a].blockSignals(False)
        self.update_results()
        self.update_labels()
        self.request()

    def build_scene(self):
        r = self.plotter.renderer
        for p in self.props:
            r.RemoveViewProp(p)
        for a in list(self.outlines):
            self.plotter.remove_actor(self.outlines[a][1])
        self.props, self.slices, self.outlines = [], {}, {}
        self.set_surface("mask_actor", None)
        self.set_surface("gt_actor", None)

        self.lut = vtk.vtkLookupTable()
        self.lut.SetNumberOfTableValues(4096)
        self.lut.SetRange(0, 65535)
        for a in range(3):
            m = vtk.vtkImageSliceMapper()
            m.SetInputData(self.grid)
            (m.SetOrientationToX, m.SetOrientationToY, m.SetOrientationToZ)[a]()
            m.BorderOn()
            s = vtk.vtkImageSlice()
            s.SetMapper(m)
            pr = s.GetProperty()
            pr.SetInterpolationTypeToLinear()
            pr.SetLookupTable(self.lut)
            pr.UseLookupTableScalarRangeOn()
            r.AddViewProp(s)
            self.props.append(s)
            self.slices[a] = m
            pts = self.corners(a, self.idx[a])
            poly = pv.lines_from_points(np.array(pts + [pts[0]]))
            actor = self.plotter.add_mesh(poly, color=PLANE[a], line_width=2.5, lighting=False,
                                          reset_camera=False, name=f"outline{a}")
            self.outlines[a] = (poly, actor)

        self.ctf, self.otf = vtk.vtkColorTransferFunction(), vtk.vtkPiecewiseFunction()
        mapper = vtk.vtkGPUVolumeRayCastMapper()
        mapper.SetInputData(self.grid)
        mapper.SetAutoAdjustSampleDistances(True)
        mapper.SetUseJittering(True)
        prop = vtk.vtkVolumeProperty()
        prop.SetColor(self.ctf)
        prop.SetScalarOpacity(self.otf)
        prop.SetInterpolationTypeToLinear()
        prop.ShadeOn()
        prop.SetAmbient(0.35)
        prop.SetDiffuse(0.7)
        prop.SetSpecular(0.15)
        prop.SetScalarOpacityUnitDistance(self.md / 250.0)
        self.volume = vtk.vtkVolume()
        self.volume.SetMapper(mapper)
        self.volume.SetProperty(prop)
        r.AddViewProp(self.volume)
        self.props.append(self.volume)

        self.update_scene()
        self.apply_visibility()
        self.plotter.view_isometric()
        self.plotter.reset_camera()

    def corners(self, a, i):
        nx, ny, nz = self.vol.shape
        sx, sy, sz = self.spacing
        x0, x1 = -sx / 2, (nx - 0.5) * sx
        y0, y1 = -sy / 2, (ny - 0.5) * sy
        z0, z1 = -sz / 2, (nz - 0.5) * sz
        if a == 0:
            x = i * sx
            return [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)]
        if a == 1:
            y = i * sy
            return [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
        z = i * sz
        return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]

    def apply_visibility(self):
        if self.vol is None or not self.slices:
            return
        planes = self.mode == "2d"
        for p in self.props:
            if isinstance(p, vtk.vtkImageSlice):
                p.SetVisibility(planes)
        self.volume.SetVisibility(not planes)
        for _poly, actor in self.outlines.values():
            actor.SetVisibility(planes)

    def update_scene(self):
        """Push slice positions, window/level, threshold and opacity into VTK."""
        if self.vol is None:
            return
        S = 65535.0
        wlo, whi, tlo, thi = self.wl.lo, self.wl.hi, self.th.lo, self.th.hi
        f = np.linspace(0, 1, 4096)
        g = np.clip((f - wlo) / max(whi - wlo, 1e-4), 0, 1)
        inside = ((f >= tlo) & (f <= thi)).astype(np.float64)
        rgba = (np.stack([g, g, g, inside], axis=1) * 255).astype(np.uint8)
        self.lut.SetTable(numpy_to_vtk(rgba, deep=True, array_type=vtk.VTK_UNSIGNED_CHAR))
        self.lut.Modified()

        fs = np.linspace(0, 1, 257)
        gs = np.clip((fs - wlo) / max(whi - wlo, 1e-4), 0, 1)
        op = self.opacity * 0.08 * np.power(gs, 1.4) * ((fs >= tlo) & (fs <= thi))
        self.ctf.RemoveAllPoints()
        self.otf.RemoveAllPoints()
        for fi, gi, oi in zip(fs, gs, op):
            self.ctf.AddRGBPoint(fi * S, gi, gi, gi)
            self.otf.AddPoint(fi * S, float(oi))

        for a in range(3):
            self.slices[a].SetSliceNumber(int(self.idx[a]))
            poly, _ = self.outlines[a]
            pts = self.corners(a, self.idx[a])
            poly.points = np.array(pts + [pts[0]], dtype=float)
            poly.Modified()

    def render3d(self):
        try:
            self.plotter.render()
        except Exception:
            pass

    def set_surface(self, attr, mask, color=PRED, opacity=0.9, name="surface", **extra):
        """(Re)build a smooth 3D surface for a mask. attr is 'mask_actor' or 'gt_actor'."""
        old = getattr(self, attr)
        if old is not None:
            self.plotter.remove_actor(old)
            setattr(self, attr, None)
        if mask is None or not mask.any():
            return
        mg = pv.ImageData(dimensions=self.vol.shape, spacing=self.spacing, origin=(0.0, 0.0, 0.0))
        mg.point_data["m"] = mask.astype(np.float32).flatten(order="F")
        try:
            mg = mg.gaussian_smooth(std_dev=1.0, scalars="m")
        except Exception:
            pass
        surf = mg.contour([0.5], scalars="m")
        if surf.n_points == 0:
            return
        try:
            surf = surf.smooth(n_iter=40, relaxation_factor=0.1)
        except Exception:
            pass
        actor = self.plotter.add_mesh(surf, color=color, opacity=opacity, smooth_shading=True, specular=0.4,
                                      specular_power=30, reset_camera=False, name=name, **extra)
        setattr(self, attr, actor)

    # ------------------------------------------------------- slice panels
    def request(self, panels=True, scene=True):
        self.last_activity = time.perf_counter()
        if hasattr(self, "pf_timer"):
            self.pf_timer.start(900)                     # plan background work once the views have settled
        p, s = self._pending
        self._pending = (p or panels, s or scene)
        if not (p or s):
            QTimer.singleShot(0, self._flush)

    def _flush(self):
        panels, scene = self._pending
        self._pending = (False, False)
        if self.vol is None:
            return
        if panels:
            self.refresh_panels()
        if scene:
            self.update_scene()
            self.render3d()

    def gray(self, a, i):
        raw = get_slice(self.vol, a, i, self.sag_rot)
        lo, hi, tl, th = self.levels()
        u8 = segment.slice_to_uint8(raw, (lo + hi) / 2, max(hi - lo, 1e-6))
        if self.th.lo > 0 or self.th.hi < 1:
            u8 = np.where((raw < tl) | (raw > th), 0, u8).astype(np.uint8)
        return u8

    def rgb(self, a, i):
        rgb = np.stack([self.gray(a, i)] * 3, axis=-1)
        gt = get_slice(self.gt, a, i, self.sag_rot) if self.gt is not None else None
        if gt is not None and gt.any():                       # actual tumor: bright fill ...
            rgb[gt] = (0.55 * rgb[gt] + 0.45 * GT_C).astype(np.uint8)
        if self.mask is not None:                             # predicted tumor: pink fill
            m = get_slice(self.mask, a, i, self.sag_rot)
            if m.any():
                rgb[m] = (0.5 * rgb[m] + 0.5 * PRED_C).astype(np.uint8)
        if gt is not None and gt.any():                       # ... and a solid bright outline on top
            rgb[edge_of(gt)] = GT_C
        return rgb

    def cuts(self, a):
        i, j, k = self.idx
        nz = self.vol.shape[2]
        return {2: (i + .5, j + .5), 0: (k + .5, j + .5) if self.sag_rot else (j + .5, nz - (k + .5)),
                1: (i + .5, nz - (k + .5))}[a]

    def pix_sp(self, a):
        sx, sy, sz = self.spacing
        return {2: (sx, sy), 0: (sz, sy) if self.sag_rot else (sy, sz), 1: (sx, sz)}[a]

    def dims(self, a):
        nx, ny, nz = self.vol.shape
        return {2: (nx, ny), 0: (nz, ny) if self.sag_rot else (ny, nz), 1: (nx, nz)}[a]          # (cols, rows)

    def crop_for(self, a):
        """The part of the slice the zoom view magnifies, sized so it exactly fills the zoom box."""
        nc, nr = self.dims(a)
        sc, sr = self.pix_sp(a)
        full, det = self.views[a], self.details[a]
        f1 = min(max(full.width(), 1) / (nc * sc), max(full.height(), 1) / (nr * sr))   # px per mm
        f2 = f1 * self.zoom
        cw = min(max(int(round(det.width() / (f2 * sc))), 8), nc)
        rh = min(max(int(round(det.height() / (f2 * sr))), 8), nr)
        cc, rc = self.cuts(a)
        c0 = min(max(int(round(cc - cw / 2)), 0), nc - cw)
        r0 = min(max(int(round(rc - rh / 2)), 0), nr - rh)
        return (c0, r0, cw, rh)

    def refresh_panels(self):
        cols = {2: (PLANE[0], PLANE[1]), 0: (PLANE[2], PLANE[1]) if self.sag_rot else (PLANE[1], PLANE[2]),
                1: (PLANE[0], PLANE[2])}
        for a in range(3):
            if self.expanded not in (None, a):
                continue
            box = self.box[:4] if (a == 2 and self.box and self.box[4] == self.idx[2]) else None
            rgb, crop = self.rgb(a, self.idx[a]), self.crop_for(a)
            c0, r0, cw, rh = crop
            self.views[a].set_slice(rgb, self.pix_sp(a), self.cuts(a), cols[a], box, locator=(c0, r0, c0 + cw, r0 + rh))
            self.details[a].set_slice(rgb, self.pix_sp(a), self.cuts(a), cols[a], box, crop=crop)
            self.idx_lbl[a].setText(f"{self.idx[a] + 1} / {self.vol.shape[a]}")

    def set_idx(self, a, v):
        self.idx[a] = v
        self.request()

    def wheel(self, a, d):
        if self.vol is None:
            return
        v = min(max(self.idx[a] + d, 0), self.vol.shape[a] - 1)
        self.sliders[a].setValue(v)          # triggers set_idx

    def set_cross(self, a, c, r):
        if self.vol is None:
            return
        nz = self.vol.shape[2]
        if a == 2:
            new = {0: int(c), 1: int(r)}
        elif a == 0:
            new = {2: int(c), 1: int(r)} if self.sag_rot else {1: int(c), 2: nz - 1 - int(r)}
        else:
            new = {0: int(c), 2: nz - 1 - int(r)}
        for b, val in new.items():
            self.idx[b] = val
            self.sliders[b].blockSignals(True)
            self.sliders[b].setValue(val)
            self.sliders[b].blockSignals(False)
        self.request()

    def on_box(self, b):
        ok = b is not None and b[2] - b[0] > 4 and b[3] - b[1] > 4
        self.box = (*b, self.idx[2]) if ok else None
        self.btn_run.setEnabled(bool(ok))
        self.update_hint()
        self.request(panels=True, scene=False)

    # ------------------------------------------------------- segmentation
    def start_warmup(self):
        """Load MedSAM while you look at the scan, so the first run is not slowed down by loading."""
        if not segment.checkpoint_ready():
            self._set_status("MedSAM weights not found: put medsam_vit_b.pth in the ai folder", False)
            return
        self.set_sam_state("loading")
        self.warm = WarmThread()
        self.warm.ready.connect(lambda: self.set_sam_state("running" if self.busy.isVisible() else "ready"))
        self.warm.failed.connect(lambda m: self._set_status("MedSAM could not load", False))
        self.warm.start()

    def cache_key(self):
        return (self.name, self.vol.shape, id(self.vol))

    def do_prefetch(self):
        """Decide which slices to prepare: the whole tumor range if the actual tumor is loaded (only to choose
        WHICH slices to encode; the prediction itself still comes from your box), else the slices around
        the one you are viewing."""
        if self.vol is None or not self.prefetch_on.isChecked():
            self.prefetch.set_task(None)
            return
        if self.thread is not None and self.thread.isRunning():
            return
        lo, hi, _, _ = self.levels()
        nz = self.vol.shape[2]
        if self.gt is not None:
            area = self.gt.sum(axis=(0, 1))
            zs = np.where(area > 0)[0]
            peak, ks = int(np.argmax(area)), range(max(int(zs.min()) - 6, 0), min(int(zs.max()) + 7, nz))
        else:
            peak = int(self.idx[2])
            ks = range(max(peak - 40, 0), min(peak + 41, nz))
        self.prefetch.set_task((self.vol, sorted(ks, key=lambda k: abs(k - peak)), (lo + hi) / 2,
                                max(hi - lo, 1e-6), self.cache_key()))

    def run_seg(self):
        if self.box is None:
            return
        x0, y0, x1, y1, k = self.box
        lo, hi, _, _ = self.levels()
        self.btn_run.setEnabled(False)
        self.busy.setRange(0, 0)                    # a moving bar until the first slice is finished
        self.busy.show()
        self.set_sam_state("running")
        self.eta, self.pct_shown = segment.EtaEstimator(), 0
        self.prefetch.pause_and_wait()                # only one thing may use the GPU at a time
        self.t_run = time.perf_counter()
        self.run_timer.start(100)
        self.thread = SegThread(self.vol, k, [round(x0), round(y0), round(x1), round(y1)],
                                (lo + hi) / 2, max(hi - lo, 1e-6), self.follow.isChecked(),
                                int(self.quality.value), self.spacing, self.cache_key())
        self.thread.done.connect(self.on_seg_done)
        self.thread.failed.connect(self.on_seg_failed)
        self.thread.progress.connect(self.on_progress)
        self.thread.start()

    def on_progress(self, done, expected, dt, hit):
        """After every model run. The time left is a guess that gets better as the run goes on."""
        self.eta.update(done, expected, dt, hit, time.perf_counter())
        if self.busy.maximum() == 0:
            self.busy.setRange(0, 100)

    def tick_run(self):
        now = time.perf_counter()
        el = now - self.t_run
        eta = self.eta
        if eta is None or eta.t_start is None:
            loading = "" if segment.is_loaded() else " (the model is still loading)"
            self.status.setText(f"Starting... {fmt_time(el)}{loading}")
            return
        if eta.finishing:
            self.busy.setValue(99)
            self.status.setText(f"Finishing up... ({fmt_time(el)} so far)")
            return
        self.pct_shown = max(self.pct_shown, int(100 * eta.fraction(now)))       # never goes backwards
        self.busy.setValue(self.pct_shown)
        self.status.setText(f"Segmenting {self.pct_shown}%, about {fmt_time(eta.remaining(now))} left "
                            f"({fmt_time(el)} so far)")

    def on_seg_done(self, info):
        self.run_timer.stop()
        self.busy.hide()
        self.btn_run.setEnabled(True)
        self.prefetch.paused = False
        self.pf_timer.start(1500)
        self.mask = info["mask"]
        st = segment.mask_stats(self.mask, self.spacing)
        self.pred_cc = st["volume_cc"]
        total = info["seg_s"] + info["load_s"]
        self.run_info = {"total": total, "load": info["load_s"], "per": info["seg_s"] / max(info["calls"], 1),
                         "calls": info["calls"], "reused": info["reused"],
                         "slices": st["slices"], "range": st["slice_range"]}
        if self.gt is not None:
            self.dice = segment.dice(self.mask, self.gt)
        reuse = f" ({info['reused']} of {info['calls']} model runs reused)" if info["reused"] else ""
        self.set_sam_state("ready")
        self.btn_clr.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.status.setText("Building the 3D surface...")
        QApplication.processEvents()                 # show the message before the short pause
        self.set_surface("mask_actor", self.mask, PRED, 0.9, "mask_surface")
        self.status.setText(f"Segmentation complete{reuse}.")
        self.update_results()
        self.update_labels()
        self.update_hint()
        self.request()

    def on_seg_failed(self, msg):
        self.run_timer.stop()
        self.busy.hide()
        self.btn_run.setEnabled(True)
        self.prefetch.paused = False
        self.status.setText("Segmentation failed.")
        self.set_sam_state("will run")
        QMessageBox.critical(self, "Segmentation failed", msg)

    def update_results(self):
        """Results card: time, predicted volume, then the actual tumor volume (all in cc)."""
        rows = []

        def add(name, value, dot=None):
            d = f"<span style='color:{dot};'>&#9679;</span>&nbsp;" if dot else ""
            rows.append(f"<tr><td style='color:{MUTED};'>{d}{name}</td>"
                        f"<td align='right'><b>{value}</b></td></tr>")

        ri = self.run_info
        if ri:
            add("Time taken", fmt_time(ri["total"]) if ri["total"] >= 10 else f"{ri['total']:.1f} s")
            add("Model runs", f"{ri['calls']} x {ri['per']:.2f} s" + (f", {ri['reused']} reused" if ri["reused"] else ""))
            rng = f" ({ri['range'][0] + 1} to {ri['range'][1] + 1})" if ri["range"] else ""
            add("Slices segmented", f"{ri['slices']}{rng}")
        if self.pred_cc is not None:
            add("Predicted tumor volume", f"{self.pred_cc:.2f} cc", PRED)
        if self.gt_cc is not None:
            add("Actual tumor volume", f"{self.gt_cc:.2f} cc", GT)
        if self.pred_cc is not None and self.gt_cc:
            diff = self.pred_cc - self.gt_cc
            add("Difference", f"{diff:+.2f} cc ({diff / self.gt_cc * 100:+.1f}%)")
            if self.dice is not None:
                add("Dice overlap", f"{self.dice:.3f}")
        if rows:
            self.result.setText("<table width='100%' cellspacing='0' cellpadding='2'>" + "".join(rows) + "</table>")
        else:
            self.result.setText(EMPTY_RESULTS)

    def clear_mask(self):
        self.mask = self.pred_cc = self.dice = self.run_info = None
        self.set_surface("mask_actor", None)
        self.status.setText("")
        self.btn_clr.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.update_results()
        self.update_labels()
        self.update_hint()
        self.request()

    def save_mask(self):
        if self.mask is None:
            return
        default = self.name.rsplit(".", 1)[0] + "_tumor_mask.nrrd"
        path, _ = QFileDialog.getSaveFileName(self, "Save mask", default, "NRRD (*.nrrd)")
        if not path:
            return
        data = self.mask.astype(np.uint8)
        try:
            nrrd.write(path, data, {"space": "left-posterior-superior",
                                    "space directions": np.diag(self.spacing)})
        except Exception:
            nrrd.write(path, data)
        self.status.setText("Mask saved.")

    # ---------------------------------------------------------- animation
    def toggle_anim(self):
        if self.anim.isActive():
            self.anim.stop()
            self.btn_anim.setText("Animate")
            self.btn_anim.setIcon(make_icon("play", TEXT))
        else:
            self.anim.start(16)
            self.btn_anim.setText("Stop")
            self.btn_anim.setIcon(make_icon("stop", TEXT))

    def anim_tick(self):
        if self.vol is None:
            return
        cam, s = self.plotter.camera, 0.35 * self.speed.value()
        if self.dir in ("Left", "Right"):
            cam.Azimuth(s if self.dir == "Left" else -s)
        else:
            cam.Elevation(s if self.dir == "Up" else -s)
            cam.OrthogonalizeViewUp()
        self.render3d()

    def cleanup(self):
        """Stop timers and close the 3D view (called when the program exits)."""
        self.anim.stop()
        self.run_timer.stop()
        self.prefetch.stop()
        self.prefetch.wait(2000)
        try:
            self.plotter.close()
        except Exception:
            pass

    def closeEvent(self, e):
        self.cleanup()
        super().closeEvent(e)
