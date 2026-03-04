"""
Login Window
Handles email/password login and Google OAuth sign-in.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont

import threading

from app.services.firebase_service import firebase_service, FirebaseError
from app.utils.session import session
from app.components.toast import show_toast


# --------------------------------------------------------------------------- #
#  Worker threads                                                               #
# --------------------------------------------------------------------------- #

def _run_in_thread(fn, on_done, on_error):
    """Run *fn()* in a daemon thread; deliver results on the Qt main thread.

    Parameters
    ----------
    fn       : callable, returns a value
    on_done  : callable(result) – called on the main thread on success
    on_error : callable(msg: str) – called on the main thread on failure
    """
    def _worker():
        try:
            result = fn()
            # QTimer.singleShot(0, ...) schedules the callback on the Qt
            # event loop, which always runs on the main thread.
            QTimer.singleShot(0, lambda: on_done(result))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            msg = str(exc)
            QTimer.singleShot(0, lambda: on_error(msg))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


# --------------------------------------------------------------------------- #
#  Login Window                                                                 #
# --------------------------------------------------------------------------- #

class LoginWindow(QWidget):
    """
    Full-screen login panel.

    Signals
    -------
    login_successful()
    go_to_register()
    """

    login_successful = Signal()
    go_to_register = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("background-color: #0d0d1a;")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Left decorative panel
        left_panel = QWidget()
        left_panel.setStyleSheet(
            """
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #1a0533, stop:1 #0d0d1a
            );
            """
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignCenter)

        brand_icon = QLabel("🛡️")
        brand_icon.setStyleSheet("font-size: 72px;")
        brand_icon.setAlignment(Qt.AlignCenter)

        brand_name = QLabel("VaultKey")
        brand_name.setStyleSheet(
            "color: #fff; font-size: 36px; font-weight: bold;"
        )
        brand_name.setAlignment(Qt.AlignCenter)

        brand_sub = QLabel("Your passwords, encrypted and safe.")
        brand_sub.setStyleSheet("color: #888; font-size: 14px;")
        brand_sub.setAlignment(Qt.AlignCenter)

        left_layout.addWidget(brand_icon)
        left_layout.addWidget(brand_name)
        left_layout.addSpacing(8)
        left_layout.addWidget(brand_sub)

        root.addWidget(left_panel, stretch=1)

        # Right form panel
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #0d0d1a;")
        right_panel.setMinimumWidth(420)

        form_layout = QVBoxLayout(right_panel)
        form_layout.setContentsMargins(60, 0, 60, 0)
        form_layout.setAlignment(Qt.AlignVCenter)
        form_layout.setSpacing(0)

        title = QLabel("Welcome back")
        title.setStyleSheet("color: #fff; font-size: 26px; font-weight: bold;")
        subtitle = QLabel("Sign in to your vault")
        subtitle.setStyleSheet("color: #666; font-size: 13px; margin-bottom: 28px;")

        form_layout.addWidget(title)
        form_layout.addSpacing(4)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(24)

        # Email
        form_layout.addWidget(self._field_label("Email"))
        self._email_input = self._line_edit("Enter your email", False)
        form_layout.addWidget(self._email_input)
        form_layout.addSpacing(16)

        # Password
        form_layout.addWidget(self._field_label("Password"))
        self._password_input = self._line_edit("Enter your password", True)
        form_layout.addWidget(self._password_input)
        form_layout.addSpacing(8)

        # Forgot password link
        forgot_btn = QPushButton("Forgot Password?")
        forgot_btn.setStyleSheet(
            "background: none; border: none; color: #6c5ce7; "
            "font-size: 12px; text-align: right;"
        )
        forgot_btn.setCursor(Qt.PointingHandCursor)
        forgot_btn.clicked.connect(self._on_forgot_password)
        form_layout.addWidget(forgot_btn, alignment=Qt.AlignRight)
        form_layout.addSpacing(20)

        # Login button
        self._login_btn = self._primary_btn("Sign In")
        self._login_btn.clicked.connect(self._on_login)
        form_layout.addWidget(self._login_btn)
        form_layout.addSpacing(12)

        # Divider
        div_row = QHBoxLayout()
        for _ in range(2):
            ln = QFrame()
            ln.setFrameShape(QFrame.HLine)
            ln.setStyleSheet("color: #2e2e3e;")
            div_row.addWidget(ln)
        div_lbl = QLabel("or")
        div_lbl.setStyleSheet("color: #555; padding: 0 8px;")
        div_row.insertWidget(1, div_lbl)
        form_layout.addLayout(div_row)
        form_layout.addSpacing(12)

        # Google button
        self._google_btn = QPushButton("  🌐  Continue with Google")
        self._google_btn.setFixedHeight(46)
        self._google_btn.setCursor(Qt.PointingHandCursor)
        self._google_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1e1e2e;
                color: #ddd;
                border: 1px solid #3a3a4e;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2a2a3e; }
            QPushButton:disabled { background-color: #141420; color: #555; }
            """
        )
        self._google_btn.clicked.connect(self._on_google_login)
        form_layout.addWidget(self._google_btn)
        form_layout.addSpacing(24)

        # Register link
        reg_row = QHBoxLayout()
        reg_lbl = QLabel("Don't have an account?")
        reg_lbl.setStyleSheet("color: #666; font-size: 13px;")
        reg_btn = QPushButton("Create one")
        reg_btn.setStyleSheet(
            "background: none; border: none; color: #6c5ce7; font-size: 13px;"
        )
        reg_btn.setCursor(Qt.PointingHandCursor)
        reg_btn.clicked.connect(self.go_to_register)
        reg_row.addWidget(reg_lbl)
        reg_row.addWidget(reg_btn)
        reg_row.addStretch()
        form_layout.addLayout(reg_row)

        root.addWidget(right_panel, stretch=1)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #aaa; font-size: 12px; margin-bottom: 4px;")
        return lbl

    @staticmethod
    def _line_edit(placeholder: str, password: bool) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if password:
            edit.setEchoMode(QLineEdit.Password)
        edit.setFixedHeight(44)
        edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #1a1a2a;
                border: 1px solid #2e2e4e;
                border-radius: 8px;
                color: #e0e0e0;
                padding: 0 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #6c5ce7;
            }
            """
        )
        return edit

    @staticmethod
    def _primary_btn(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(46)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            """
            QPushButton {
                background-color: #6c5ce7;
                color: #fff;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #7d6ff0; }
            QPushButton:pressed { background-color: #5a4dc4; }
            QPushButton:disabled { background-color: #3a3a6a; color: #777; }
            """
        )
        return btn

    def _set_loading(self, loading: bool):
        self._login_btn.setEnabled(not loading)
        self._login_btn.setText("Signing in…" if loading else "Sign In")
    def _set_google_loading(self, loading: bool):
        self._google_btn.setEnabled(not loading)
        self._google_btn.setText(
            "  \u23f3  Waiting for Google sign-in\u2026" if loading
            else "  \U0001f310  Continue with Google"
        )
        self._login_btn.setEnabled(not loading)
    # ------------------------------------------------------------------ #
    #  Login actions                                                       #
    # ------------------------------------------------------------------ #

    def _on_login(self):
        email = self._email_input.text().strip()
        password = self._password_input.text()
        if not email or not password:
            show_toast(self, "Please fill in all fields.", "warning")
            return

        self._set_loading(True)
        _run_in_thread(
            fn=lambda: firebase_service.login(email, password),
            on_done=self._on_login_done,
            on_error=self._on_login_error,
        )

    def _on_login_done(self, result: dict):
        self._set_loading(False)
        session.set_user(result)
        self.login_successful.emit()

    def _on_login_error(self, msg: str):
        self._set_loading(False)
        friendly = _friendly_error(msg)
        show_toast(self, friendly, "error", 4000)

    # ------------------------------------------------------------------ #
    #  Google login                                                        #
    # ------------------------------------------------------------------ #

    def _on_google_login(self):
        print("[DEBUG] Google button clicked", flush=True)
        self._set_google_loading(True)
        show_toast(self, "Browser opened \u2013 complete Google sign-in to continue.", "info", 6000)
        print("[DEBUG] Starting OAuth thread via threading.Thread", flush=True)
        _run_in_thread(
            fn=firebase_service.login_with_google,
            on_done=self._on_google_done,
            on_error=lambda msg: self._on_google_error(msg),
        )
        print("[DEBUG] threading.Thread started \u2013 browser should open now", flush=True)

    def _on_google_done(self, result: dict):
        self._set_google_loading(False)
        session.set_user(result)
        self.login_successful.emit()

    def _on_google_error(self, msg: str):
        self._set_google_loading(False)
        show_toast(self, _friendly_google_error(msg), "error", 5000)

    # ------------------------------------------------------------------ #
    #  Forgot password                                                     #
    # ------------------------------------------------------------------ #

    def _on_forgot_password(self):
        email = self._email_input.text().strip()
        if not email:
            show_toast(self, "Enter your email address first.", "warning")
            return
        try:
            firebase_service.send_password_reset(email)
            show_toast(self, f"Password reset email sent to {email}", "success", 5000)
        except FirebaseError as e:
            show_toast(self, _friendly_error(str(e)), "error", 4000)


# --------------------------------------------------------------------------- #
#  Error message prettifier                                                    #
# --------------------------------------------------------------------------- #

def _friendly_error(raw: str) -> str:
    mapping = {
        "EMAIL_NOT_FOUND": "No account found for this email.",
        "INVALID_PASSWORD": "Incorrect password.",
        "INVALID_EMAIL": "Please enter a valid email address.",
        "USER_DISABLED": "This account has been disabled.",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please try again later.",
        "INVALID_LOGIN_CREDENTIALS": "Invalid email or password.",
        "EMAIL_EXISTS": "An account already exists with this email.",
        "WEAK_PASSWORD": "Password must be at least 6 characters.",
    }
    for key, friendly in mapping.items():
        if key in raw:
            return friendly
    return raw


def _friendly_google_error(raw: str) -> str:
    """Human-readable messages for Google / Firebase OAuth errors."""
    if "GOOGLE_CLIENT_ID" in raw or "GOOGLE_CLIENT_SECRET" in raw or "not set" in raw.lower():
        return "Google credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
    if "google-auth-oauthlib is not installed" in raw:
        return "Missing dependency. Run: pip install google-auth-oauthlib"
    if "cancelled" in raw.lower() or "cancel" in raw.lower():
        return "Google sign-in was cancelled."
    if "timed out" in raw.lower():
        return "Google sign-in timed out. Please try again."
    if "INVALID_IDP_RESPONSE" in raw or "INVALID_ID_TOKEN" in raw:
        return "Google sign-in failed: invalid response. Please try again."
    if "OPERATION_NOT_ALLOWED" in raw:
        return "Google sign-in is not enabled in Firebase. Enable it in Firebase Console → Authentication."
    if "Network error" in raw:
        return "Network error. Check your internet connection and try again."
    return raw
