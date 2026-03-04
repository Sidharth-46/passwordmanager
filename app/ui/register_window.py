"""
Register Window
New user registration with email + password.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PySide6.QtCore import Signal, Qt, QTimer

import logging
import threading

from app.services.firebase_service import firebase_service, FirebaseError
from app.utils.session import session
from app.utils.helpers import is_valid_email
from app.components.toast import show_toast
from app.ui.login_window import _friendly_error

log = logging.getLogger(__name__)


class RegisterWindow(QWidget):
    """
    Registration form.

    Signals
    -------
    registration_successful()
    go_to_login()
    """

    registration_successful = Signal()
    go_to_login = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("background-color: #0d0d1a;")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Left panel
        left_panel = QWidget()
        left_panel.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #1a0533, stop:1 #0d0d1a);"
        )
        left_l = QVBoxLayout(left_panel)
        left_l.setAlignment(Qt.AlignCenter)
        icon_lbl = QLabel("🛡️")
        icon_lbl.setStyleSheet("font-size: 72px;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        name_lbl = QLabel("VaultKey")
        name_lbl.setStyleSheet("color:#fff;font-size:36px;font-weight:bold;")
        name_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl = QLabel("Create your secure vault today.")
        sub_lbl.setStyleSheet("color:#888;font-size:14px;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        left_l.addWidget(icon_lbl)
        left_l.addWidget(name_lbl)
        left_l.addSpacing(8)
        left_l.addWidget(sub_lbl)
        root.addWidget(left_panel, stretch=1)

        # Right panel
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #0d0d1a;")
        right_panel.setMinimumWidth(420)
        form_layout = QVBoxLayout(right_panel)
        form_layout.setContentsMargins(60, 0, 60, 0)
        form_layout.setAlignment(Qt.AlignVCenter)
        form_layout.setSpacing(0)

        title = QLabel("Create Account")
        title.setStyleSheet("color:#fff;font-size:26px;font-weight:bold;")
        subtitle = QLabel("Start protecting your passwords")
        subtitle.setStyleSheet("color:#666;font-size:13px;margin-bottom:28px;")
        form_layout.addWidget(title)
        form_layout.addSpacing(4)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(24)

        # Email
        form_layout.addWidget(self._lbl("Email Address"))
        self._email_input = self._input("your@email.com", False)
        form_layout.addWidget(self._email_input)
        form_layout.addSpacing(16)

        # Password
        form_layout.addWidget(self._lbl("Password (min 6 chars)"))
        self._password_input = self._input("Create a password", True)
        form_layout.addWidget(self._password_input)
        form_layout.addSpacing(16)

        # Confirm password
        form_layout.addWidget(self._lbl("Confirm Password"))
        self._confirm_input = self._input("Repeat your password", True)
        form_layout.addWidget(self._confirm_input)
        form_layout.addSpacing(24)

        # Register button
        self._register_btn = self._primary_btn("Create Account")
        self._register_btn.clicked.connect(self._on_register)
        form_layout.addWidget(self._register_btn)
        form_layout.addSpacing(20)

        # Back to login
        back_row = QHBoxLayout()
        back_lbl = QLabel("Already have an account?")
        back_lbl.setStyleSheet("color:#666;font-size:13px;")
        back_btn = QPushButton("Sign in")
        back_btn.setStyleSheet(
            "background:none;border:none;color:#6c5ce7;font-size:13px;"
        )
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.go_to_login)
        back_row.addWidget(back_lbl)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        form_layout.addLayout(back_row)

        root.addWidget(right_panel, stretch=1)

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#aaa;font-size:12px;margin-bottom:4px;")
        return lbl

    @staticmethod
    def _input(placeholder: str, password: bool) -> QLineEdit:
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
            QLineEdit:focus { border: 1px solid #6c5ce7; }
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
            QPushButton:disabled { background-color: #3a3a6a; color: #777; }
            """
        )
        return btn

    def _set_loading(self, loading: bool):
        self._register_btn.setEnabled(not loading)
        self._register_btn.setText("Creating account…" if loading else "Create Account")

    def _on_register(self):
        email = self._email_input.text().strip()
        password = self._password_input.text()
        confirm = self._confirm_input.text()

        if not email or not password or not confirm:
            show_toast(self, "Please fill in all fields.", "warning")
            return
        if not is_valid_email(email):
            show_toast(self, "Please enter a valid email address.", "warning")
            return
        if len(password) < 6:
            show_toast(self, "Password must be at least 6 characters.", "warning")
            return
        if password != confirm:
            show_toast(self, "Passwords do not match.", "warning")
            return

        self._set_loading(True)
        log.debug("_on_register: starting registration thread for %s", email)

        def _worker():
            try:
                log.debug("_worker: calling firebase_service.register")
                result = firebase_service.register(email, password)
                log.debug("_worker: registration succeeded")
                QTimer.singleShot(0, lambda: self._on_done(result))
            except Exception as exc:
                log.debug("_worker: registration failed: %s", exc)
                msg = str(exc)
                QTimer.singleShot(0, lambda: self._on_error(msg))

        threading.Thread(target=_worker, daemon=True).start()
        log.debug("_on_register: thread started")

    def _on_done(self, result: dict):
        log.debug("_on_done: registration successful – updating UI")
        self._set_loading(False)
        session.set_user(result)
        show_toast(self, "Account created! Setting up your vault…", "success")
        self.registration_successful.emit()

    def _on_error(self, msg: str):
        log.debug("_on_error: %s – updating UI", msg)
        self._set_loading(False)
        show_toast(self, _friendly_error(msg), "error", 4000)
