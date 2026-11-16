"""
ATLAS - app entry point.

Place at the PROJECT ROOT (same level as assets/, components/, interfaces/ ...)
Run with:  python main.py
"""
import glob
import os
import sys
import hashlib

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QStackedWidget

from interfaces.login import LoginPage
from interfaces.user_register import RegisterPage
from interfaces.dashboard import DashboardPage
from interfaces.settings import SettingsPage
from databases.db_connection import db_cursor
from databases import staff_repository as staff_repo

# ============================================================================
#  APP ICON (window + taskbar)
#  Put your logo in assets/ and type the START of its file name below.
#  A .ico file looks sharpest; .png / .jpg / .webp also work.
# ============================================================================
APP_ICON_NAME = "Atlas_Bulat"
APP_ID = "UniKL.ATLAS.TumorLocalization"      # makes Windows show YOUR icon, not Python's


def load_app_icon() -> QIcon:
    base = os.path.dirname(os.path.abspath(__file__))
    for folder in (os.path.join(base, "assets"), os.path.join(os.getcwd(), "assets")):
        for ext in (".ico", ".png", ".webp", ".jpg", ".jpeg"):       # .ico first
            for path in glob.glob(os.path.join(folder, APP_ICON_NAME + "*" + ext)):
                return QIcon(path)
    print(f"[main] App icon '{APP_ICON_NAME}' not found in assets/")
    return QIcon()


# ============================================================================
#  SCREEN SCALING  (fixes the empty gaps on big screens)
#  "auto"  = scale the whole UI to fit your screen
#  1.0     = no scaling (original size)
#  1.3     = any number you like (bigger = larger UI)
# ============================================================================
UI_SCALE = "auto"
DESIGN_W, DESIGN_H = 1210, 860      # the size the screens were designed for


def detect_scale() -> float:
    if UI_SCALE != "auto":
        return float(UI_SCALE)
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)  # work area
        w = rect.right - rect.left
        h = rect.bottom - rect.top - 32           # minus the window title bar
        return max(0.85, min(w / DESIGN_W, h / DESIGN_H, 1.75))
    except Exception:
        return 1.0


def hash_password(password: str) -> str:
    """Secure SHA-256 password hashing."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(provided_password: str, stored_hash: str) -> bool:
    return hash_password(provided_password) == stored_hash


DARK_DIALOG_STYLE = """
    QMessageBox { background: #0a0d12; }
    QMessageBox QLabel { color: #e8eef2; }
    QMessageBox QPushButton {
        background: #0f1a20; color: #e8eef2; border: 1px solid #1f8a99;
        border-radius: 3px; padding: 6px 18px; min-width: 70px;
    }
    QMessageBox QPushButton:hover { background: #12303a; }
"""

LIGHT_DIALOG_STYLE = """
    QMessageBox { background: #f4f1f8; }
    QMessageBox QLabel { color: #20182e; }
    QMessageBox QPushButton {
        background: #ffffff; color: #20182e; border: 1px solid #c9bedb;
        border-radius: 3px; padding: 6px 18px; min-width: 70px;
    }
    QMessageBox QPushButton:hover { background: #e8def7; }
"""


class AtlasWindow(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATLAS")
        self.current_user = None          # {"full_name": ..., "department": ...} while logged in
        self.scanner_page = None          # created the first time the AI Scanner is opened
        self.settings_return_widget = None
        self.photo = None                 # QPixmap of the logged-in user's profile photo
        self.dark_mode = True

        # --- pages ---
        self.login_page = LoginPage()
        self.register_page = RegisterPage()
        self.dashboard_page = DashboardPage()
        self.settings_page = SettingsPage()
        self.addWidget(self.login_page)       # index 0
        self.addWidget(self.register_page)    # index 1
        self.addWidget(self.dashboard_page)   # index 2
        self.addWidget(self.settings_page)    # index 3

        # --- login / register navigation ---
        self.login_page.register_requested.connect(self.show_register)
        self.register_page.back_to_login_requested.connect(self.show_login)

        # --- actions ---
        self.login_page.login_requested.connect(self.handle_login)
        self.register_page.register_submitted.connect(self.handle_register)

        # --- dashboard ---
        self.dashboard_page.module_selected.connect(self.handle_module)
        # TEMPORARY: clicking the user chip (top right) logs out
        self.dashboard_page.user_clicked.connect(self.handle_logout)
        self.dashboard_page.settings_clicked.connect(self.open_settings)

        # --- settings ---
        self.settings_page.back_requested.connect(self.return_from_settings)
        self.settings_page.user_clicked.connect(self.handle_logout)      # TEMPORARY: same as the dashboard
        self.settings_page.theme_toggled.connect(self.handle_theme)
        self.settings_page.profile_save_requested.connect(self.handle_profile_save)
        self.settings_page.photo_selected.connect(self.handle_photo)
        self.settings_page.task_add_requested.connect(self.handle_task_add)

        self.resize(DESIGN_W, DESIGN_H)

    # ---- navigation ----
    def show_login(self):
        self.setCurrentWidget(self.login_page)

    def show_register(self):
        self.setCurrentWidget(self.register_page)

    def show_dashboard(self):
        self.setCurrentWidget(self.dashboard_page)

    def return_from_settings(self):
        page = self.settings_return_widget or self.dashboard_page
        self.setCurrentWidget(page)

    # ---- actions ----
    def handle_login(self, username: str, password: str):
        try:
            with db_cursor(commit=False, dict_rows=True) as cur:
                cur.execute(
                    "SELECT * FROM staff WHERE username = %s OR email = %s",
                    (username.strip(), username.strip())
                )
                user = cur.fetchone()

            if user and user["is_active"] and verify_password(password, user["password_hash"]):
                full_name = f"{user['first_name']} {user['last_name']}"
                department = user.get("department") or ""      # "" if the column is empty (NULL)
                self.current_user = {"username": user["username"], "full_name": full_name,
                                     "department": department}
                self.dashboard_page.set_user(full_name, department)
                self.load_session_data()
                self.login_page.clear()
                self.show_dashboard()
            else:
                QMessageBox.warning(
                    self, "Login failed",
                    "Invalid username, email, or password, or account is inactive.")
        except Exception as e:
            QMessageBox.critical(
                self, "Database Error",
                f"Could not connect to database or query failed:\n{e}")

    def handle_logout(self):
        self.current_user = None
        self.apply_photo(None)
        self.dashboard_page.set_today_tasks([])
        self.dashboard_page.set_upcoming([])
        self.show_login()

    # ---- session data: profile photo + personal tasks ----
    def load_session_data(self):
        """Called after login. A problem here never blocks the login itself."""
        username = (self.current_user or {}).get("username")
        if not username:
            return
        try:
            staff_repo.ensure_schema()                      # adds photo column + tasks table if missing
            data = staff_repo.get_avatar(username)
            self.apply_photo(self._pixmap(data) if data else None)
            self.refresh_dashboard_tasks()
        except Exception as e:
            print("[session] could not load photo / tasks:", repr(e))

    @staticmethod
    def _pixmap(data: bytes):
        pm = QPixmap()
        return pm if pm.loadFromData(data) else None

    def apply_photo(self, pixmap):
        """Show the photo (QPixmap or None) in every header."""
        self.photo = pixmap if (pixmap is not None and not pixmap.isNull()) else None
        self.dashboard_page.set_photo(self.photo)
        if self.scanner_page is not None:
            self.scanner_page.set_photo(self.photo)

    def refresh_dashboard_tasks(self):
        username = (self.current_user or {}).get("username")
        if not username:
            return
        today_rows, upcoming_rows = staff_repo.dashboard_tasks(username)
        self.dashboard_page.set_today_tasks(today_rows)
        self.dashboard_page.set_upcoming(upcoming_rows)

    def _set_user_everywhere(self, full_name: str, department: str):
        self.dashboard_page.set_user(full_name, department)
        self.settings_page.set_user(full_name, department)
        if self.scanner_page is not None:
            self.scanner_page.set_user(full_name, department)

    # ---- settings page ----
    def open_settings(self):
        username = (self.current_user or {}).get("username")
        if not username:
            return
        try:
            staff_repo.ensure_schema()
            profile = staff_repo.get_profile(username)
            self.settings_page.set_profile(profile)
            self.settings_page.set_user(self.current_user["full_name"], self.current_user["department"])
            self.settings_page.set_photo_bytes(staff_repo.get_avatar(username))
        except Exception as e:
            QMessageBox.warning(self, "Settings", f"Could not load your profile:\n{e}")
            return
        current = self.currentWidget()
        if current is not self.settings_page:
            self.settings_return_widget = current
        self.setCurrentWidget(self.settings_page)

    def handle_profile_save(self, data: dict):
        username = (self.current_user or {}).get("username")
        try:
            staff_repo.update_profile(username, data["full_name"], data["email"],
                                      data["phone"], data["department"])
            profile = staff_repo.get_profile(username)
        except ValueError as e:                              # e.g. email already used
            self.settings_page.notify_profile(str(e), False)
            return
        except Exception as e:
            print("[settings] save failed:", repr(e))
            self.settings_page.notify_profile("Could not save. Please try again.", False)
            return
        self.current_user["full_name"] = profile["full_name"]
        self.current_user["department"] = profile["department"]
        self.settings_page.set_profile(profile)
        self._set_user_everywhere(profile["full_name"], profile["department"])
        self.settings_page.notify_profile("Profile saved.", True)

    def handle_photo(self, data):
        username = (self.current_user or {}).get("username")
        try:
            staff_repo.set_avatar(username, data)
        except Exception as e:
            print("[settings] photo failed:", repr(e))
            self.settings_page.notify_profile("Could not save the photo. Please try again.", False)
            return
        self.apply_photo(self._pixmap(data) if data else None)
        self.settings_page.notify_profile("Profile photo updated." if data else "Profile photo removed.", True)

    def handle_task_add(self, task: dict):
        username = (self.current_user or {}).get("username")
        try:
            staff_repo.add_task(username, task["title"], task["description"],
                                task["due_date"], task["due_time"], task["note"])
            self.refresh_dashboard_tasks()
        except Exception as e:
            print("[settings] task failed:", repr(e))
            self.settings_page.notify_task("Could not save the task. Please try again.", False)
            return
        self.settings_page.clear_task_form()
        self.settings_page.notify_task("Task added. It now shows on your dashboard.", True)

    def handle_theme(self, dark: bool):
        self.dark_mode = bool(dark)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(DARK_DIALOG_STYLE if dark else LIGHT_DIALOG_STYLE)
        self.settings_page.set_theme(dark)
        self.dashboard_page.set_theme(dark)
        if self.scanner_page is not None:
            self.scanner_page.set_theme(dark)
        self.login_page.set_theme(dark)
        self.register_page.set_theme(dark)

    def handle_register(self, data: dict):
        print("DEBUG FORM DATA RECEIVED:", data)
        try:
            hashed_pwd = hash_password(data.get("password", ""))

            # Catch license number
            license_number = (
                data.get("license_number") or
                data.get("license") or
                data.get("license_no") or
                data.get("licence_number")
            )
            if license_number:
                license_number = str(license_number).strip()
            if not license_number:
                license_number = None

            # Catch phone number (handles variations like phone, contact_no, contact)
            contact_no = (
                data.get("contact_no") or
                data.get("phone") or
                data.get("contact") or
                data.get("mobile")
            )
            if contact_no:
                contact_no = str(contact_no).strip()
            if not contact_no:
                contact_no = None

            # The registration form sends the chosen role as "role" (Doctor, Radiologist, ...)
            staff_role = data.get("staff_role") or data.get("role") or "Doctor"

            with db_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO staff (
                        first_name, last_name, username,
                        password_hash, staff_role, department, email, license_number, contact_no, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data.get("first_name", "New"),
                    data.get("last_name", "User"),
                    data.get("username"),
                    hashed_pwd,
                    staff_role,
                    data.get("department"),
                    data.get("email"),
                    license_number,
                    contact_no,
                    True
                ))

            QMessageBox.information(
                self, "Registration Successful",
                "Your account has been created successfully! Please log in."
            )
            self.register_page.clear()
            self.show_login()

        except Exception as e:
            QMessageBox.warning(
                self, "Registration Failed",
                f"Could not register user. Error: {e}"
            )

    def handle_module(self, key: str):
        if key == "scanner":
            self.open_scanner()
            return
        print("MODULE selected:", key)
        # TODO: switch to the page for this module once it is built
        #   "patients" -> pt_info.py   "queue" -> scan_queue.py   "reports" -> reports.py

    # ---- AI scanner (MedSAM) ----
    def open_scanner(self):
        """The scanner needs heavy packages (torch, VTK), so it is only loaded when first opened."""
        if self.scanner_page is None:
            try:
                from interfaces.scanner import ScannerPage
                page = ScannerPage()
            except Exception as e:
                print("[scanner] could not start:", repr(e))
                QMessageBox.warning(
                    self, "AI Scanner unavailable",
                    "The AI Scanner could not start. Some packages may not be installed yet "
                    "(torch, pyvista, pyvistaqt, vtk, pynrrd, segment-anything).\n\n"
                    f"Details: {e}")
                return
            page.back_requested.connect(self.show_dashboard)
            page.user_clicked.connect(self.handle_logout)          # TEMPORARY: same as the dashboard
            page.settings_clicked.connect(self.open_settings)
            page.set_theme(self.dark_mode)
            QApplication.instance().aboutToQuit.connect(page.cleanup)
            self.addWidget(page)
            self.scanner_page = page

        user = self.current_user or {}
        self.scanner_page.set_user(user.get("full_name", "User"), user.get("department", ""))
        self.scanner_page.set_photo(self.photo)
        self.setCurrentWidget(self.scanner_page)


if __name__ == "__main__":
    # The scale factor must be set BEFORE QApplication is created.
    os.environ["QT_SCALE_FACTOR"] = str(round(detect_scale(), 2))

    # Windows: give the app its own identity so the taskbar shows our icon, not Python's.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_DIALOG_STYLE)
    icon = load_app_icon()
    app.setWindowIcon(icon)
    window = AtlasWindow()
    window.setWindowIcon(icon)
    window.showMaximized()
    sys.exit(app.exec())
