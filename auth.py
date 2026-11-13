"""auth.py - hardcoded login dialog (PySide6).

Default credentials (change them below):
    username: admin
    password: admin123
"""
import hmac

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout

USERNAME = "admin"
PASSWORD = "admin123"


def check_credentials(user, password):
    ok_user = hmac.compare_digest(user.encode(), USERNAME.encode())
    ok_pass = hmac.compare_digest(password.encode(), PASSWORD.encode())
    return ok_user and ok_pass


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tumor Segmenter")
        self.setFixedSize(440, 560)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 20)

        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(34, 38, 34, 30)
        lay.setSpacing(0)

        mark = QLabel("+")
        mark.setFixedSize(58, 58)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #7aaaff,stop:1 #4a82f5);"
                           "color:#06142e; border-radius:17px; font-size:32px; font-weight:800;")
        lay.addWidget(mark, alignment=Qt.AlignHCenter)
        lay.addSpacing(16)
        title = QLabel("Tumor Segmenter")
        title.setObjectName("hero")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        sub = QLabel("Sign in to open your scans")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        lay.addSpacing(26)

        for text in ("Username", "Password"):
            lab = QLabel(text)
            lab.setObjectName("muted")
            lay.addWidget(lab)
            lay.addSpacing(5)
            edit = QLineEdit()
            edit.setPlaceholderText("Enter your " + text.lower())
            if text == "Password":
                edit.setEchoMode(QLineEdit.Password)
                self.pass_e = edit
            else:
                self.user_e = edit
            edit.returnPressed.connect(self.submit)
            lay.addWidget(edit)
            lay.addSpacing(14)

        self.err = QLabel("")
        self.err.setObjectName("error")
        lay.addWidget(self.err)
        lay.addSpacing(6)
        btn = QPushButton("Sign in")
        btn.setObjectName("primary")
        btn.setMinimumHeight(46)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.submit)
        lay.addWidget(btn)
        lay.addStretch()
        outer.addWidget(card, 1)

        foot = QLabel("Research use only. Not a diagnostic tool.")
        foot.setObjectName("muted")
        foot.setAlignment(Qt.AlignCenter)
        outer.addWidget(foot)
        self.user_e.setFocus()

    def submit(self):
        if check_credentials(self.user_e.text().strip(), self.pass_e.text()):
            self.accept()
        else:
            self.err.setText("Username or password is incorrect.")
            self.pass_e.clear()


def login():
    """Show the login dialog. Returns True if the user signed in."""
    return LoginDialog().exec() == QDialog.Accepted