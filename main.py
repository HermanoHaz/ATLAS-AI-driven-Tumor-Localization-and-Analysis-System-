"""main.py - entry point.

Run:  python main.py
Install (Python 3.12 recommended):
    python -m pip install PySide6 pyvista pyvistaqt vtk pynrrd numpy pillow
    python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
    python -m pip install git+https://github.com/facebookresearch/segment-anything.git
Then put medsam_vit_b.pth (from https://github.com/bowang-lab/MedSAM) next to this file.
"""
import os
import sys

os.environ.setdefault("QT_API", "pyside6")      # tell qtpy / pyvistaqt which binding to use

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QApplication

import auth
import segment
import theme


def main():
    try:    # crisp rendering on 125% / 150% Windows scaling
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(theme.QSS)
    print(f"Model: {segment.MODEL_NAME} | device: {segment.device_info()}")

    if not auth.login():
        return 0
    from app import MainWindow               # imported late: VTK is heavy to load

    win = MainWindow()
    win.showMaximized()                      # more room for the slice views
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())