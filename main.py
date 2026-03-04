"""
VaultKey – Desktop Password Manager
Entry point: bootstraps the PySide6 application and navigation controller.

Flow:
    1. Show LoginWindow (or RegisterWindow)
    2. On successful login → check for Master PIN in Firestore
       a. No PIN stored → show SetupPinDialog
       b. PIN stored    → show UnlockPinDialog
    3. On vault unlock  → derive AES key → show VaultWindow
    4. On logout        → return to LoginWindow
"""

import sys
import os
import platform
import logging

# Configure logging so all log.debug() calls produce visible output
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy third-party loggers
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)

# Fix High-DPI on Windows
if platform.system() == "Windows":
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PySide6.QtWidgets import QApplication, QStackedWidget, QMessageBox
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt, QTimer

from app.ui.login_window import LoginWindow
from app.ui.register_window import RegisterWindow
from app.ui.vault_window import VaultWindow
from app.ui.pin_dialog import SetupPinDialog, UnlockPinDialog
from app.services.firebase_service import firebase_service, FirebaseError
from app.services.encryption_service import encryption_service
from app.utils.session import session
from app.components.toast import show_toast

import os as _os
_os.environ.setdefault("FIREBASE_API_KEY", "")
_os.environ.setdefault("FIREBASE_PROJECT_ID", "")

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Application Controller                                                      #
# --------------------------------------------------------------------------- #

class AppController:
    """
    Manages the top-level QStackedWidget that switches between Login,
    Register, and Vault screens.
    """

    def __init__(self, app: QApplication):
        self._app = app

        self._stack = QStackedWidget()
        self._stack.setWindowTitle("VaultKey – Password Manager")
        self._stack.setMinimumSize(900, 600)
        self._stack.resize(1100, 680)

        # Set application-level dark palette / stylesheet
        self._apply_global_style()

        # Pages
        self._login_win = LoginWindow()
        self._register_win = RegisterWindow()
        self._vault_win = VaultWindow()

        self._stack.addWidget(self._login_win)     # index 0
        self._stack.addWidget(self._register_win)  # index 1
        self._stack.addWidget(self._vault_win)     # index 2

        # Wire signals
        self._login_win.login_successful.connect(self._after_login)
        self._login_win.go_to_register.connect(lambda: self._stack.setCurrentIndex(1))

        self._register_win.registration_successful.connect(self._after_login)
        self._register_win.go_to_login.connect(lambda: self._stack.setCurrentIndex(0))

        self._vault_win.logout_requested.connect(self._on_logout)

        # Try to restore a previous session
        if session.is_logged_in or (session.user_id and session.refresh_token):
            self._try_refresh_then_show_vault()
        else:
            self._stack.setCurrentIndex(0)

        self._stack.show()

    # ------------------------------------------------------------------ #
    #  Session restore                                                     #
    # ------------------------------------------------------------------ #

    def _try_refresh_then_show_vault(self):
        """Attempt to silently refresh the ID token from persisted refresh token."""
        if session.refresh_token and not session.id_token:
            try:
                resp = firebase_service.refresh_token(session.refresh_token)
                session.update_id_token(resp.get("id_token", ""))
            except Exception:
                session.clear()
                self._stack.setCurrentIndex(0)
                return
        self._after_login()

    # ------------------------------------------------------------------ #
    #  After login – PIN check                                             #
    # ------------------------------------------------------------------ #

    def _after_login(self):
        """Called after a successful Firebase auth. Check Master PIN.

        The Firestore round-trip runs in a daemon thread so the UI stays
        responsive.  All UI work resumes on the main thread via QTimer.
        """
        if not session.user_id or not session.id_token:
            log.warning("_after_login: session missing user_id or id_token – back to login")
            self._stack.setCurrentIndex(0)
            return

        log.debug("_after_login: checking master PIN for user %s", session.user_id)

        # Capture for closure
        user_id  = session.user_id
        id_token = session.id_token

        def _fetch():
            return firebase_service.get_master_pin_hash(user_id, id_token)

        def _on_pin_hash(pin_hash):
            log.debug("_after_login: pin_hash present=%s", bool(pin_hash))
            if pin_hash is None:
                self._show_setup_pin()
            else:
                self._show_unlock_pin(pin_hash)

        def _on_fetch_error(msg: str):
            log.error("_after_login: get_master_pin_hash failed: %s", msg)
            QMessageBox.critical(
                self._stack,
                "Connection Error",
                f"Could not reach the server:\n{msg}",
            )
            session.clear()
            self._stack.setCurrentIndex(0)

        import threading

        def _worker():
            try:
                result = _fetch()
                QTimer.singleShot(0, lambda: _on_pin_hash(result))
            except Exception as exc:
                err = str(exc)
                QTimer.singleShot(0, lambda: _on_fetch_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_setup_pin(self):
        dlg = SetupPinDialog(parent=self._stack)
        pin_captured: list[str] = []
        dlg.pin_set.connect(lambda p: pin_captured.append(p))
        dlg.exec()
        if pin_captured:
            self._unlock_vault_with_pin(pin_captured[0])
        else:
            # User closed dialog without setting PIN
            session.clear()
            self._stack.setCurrentIndex(0)

    def _show_unlock_pin(self, pin_hash: str):
        dlg = UnlockPinDialog(pin_hash, parent=self._stack)
        pin_captured: list[str] = []
        dlg.unlocked.connect(lambda p: pin_captured.append(p))
        dlg.exec()
        if pin_captured:
            self._unlock_vault_with_pin(pin_captured[0])
        else:
            session.clear()
            self._stack.setCurrentIndex(0)

    def _unlock_vault_with_pin(self, pin: str):
        """Derive AES key from PIN + random salt, unlock vault, show vault window."""
        import os
        # Use a deterministic salt derived from the user ID so the same PIN
        # always produces the same key on the same account.
        # (Production: store the salt alongside the PIN hash in Firestore)
        salt_bytes = (session.user_id or "default").encode("utf-8").ljust(32, b"\x00")[:32]
        vault_key = encryption_service.derive_key(pin, salt_bytes)
        session.unlock_vault(vault_key)

        self._stack.setCurrentIndex(2)
        self._vault_win.load_vault()

    # ------------------------------------------------------------------ #
    #  Logout                                                              #
    # ------------------------------------------------------------------ #

    def _on_logout(self):
        session.clear()
        self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------ #
    #  Global stylesheet                                                   #
    # ------------------------------------------------------------------ #

    def _apply_global_style(self):
        self._app.setStyle("Fusion")
        self._stack.setStyleSheet(
            """
            QStackedWidget { background-color: #0d0d1a; }
            QToolTip {
                background-color: #1e1e2e;
                color: #e0e0e0;
                border: 1px solid #3e3e5e;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QMessageBox {
                background-color: #0d0d1a;
                color: #e0e0e0;
            }
            QMessageBox QLabel { color: #e0e0e0; }
            QMessageBox QPushButton {
                background-color: #6c5ce7;
                color: #fff;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
            }
            QMessageBox QPushButton:hover { background-color: #7d6ff0; }
            QScrollBar:vertical {
                background: #1a1a2a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a5a;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            """
        )
        font = QFont("Segoe UI", 10) if platform.system() == "Windows" else QFont("SF Pro Text", 10)
        self._app.setFont(font)


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

def main():
    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("VaultKey")
    app.setOrganizationName("VaultKey")
    app.setApplicationVersion("1.0.0")

    # App icon (create a placeholder if assets/icon.png doesn't exist)
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    controller = AppController(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
