"""
PIN Dialog
Handles Master PIN creation and vault unlock flows.
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PySide6.QtCore import Signal, Qt, QThread, QObject

from app.services.firebase_service import firebase_service, FirebaseError
from app.services.encryption_service import encryption_service
from app.utils.session import session
from app.utils.helpers import is_valid_pin
from app.components.toast import show_toast


# --------------------------------------------------------------------------- #
#  Worker threads                                                               #
# --------------------------------------------------------------------------- #

class _FetchHashWorker(QObject):
    finished = Signal(object)   # str | None
    error = Signal(str)

    def run(self):
        try:
            pin_hash = firebase_service.get_master_pin_hash(
                session.user_id, session.id_token
            )
            self.finished.emit(pin_hash)
        except Exception as e:
            self.error.emit(str(e))


class _SaveHashWorker(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, pin_hash: str):
        super().__init__()
        self._pin_hash = pin_hash

    def run(self):
        try:
            firebase_service.set_master_pin_hash(
                session.user_id, session.id_token, self._pin_hash
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# --------------------------------------------------------------------------- #
#  Shared styling helpers                                                       #
# --------------------------------------------------------------------------- #

_DIALOG_STYLE = """
QDialog {
    background-color: #0d0d1a;
}
QLabel#title {
    color: #fff;
    font-size: 20px;
    font-weight: bold;
}
QLabel#subtitle {
    color: #888;
    font-size: 13px;
}
"""

_INPUT_STYLE = """
QLineEdit {
    background-color: #1a1a2a;
    border: 1px solid #2e2e4e;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 0 12px;
    font-size: 22px;
    letter-spacing: 12px;
    text-align: center;
}
QLineEdit:focus { border: 1px solid #6c5ce7; }
"""

_BTN_STYLE = """
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


class _PinInputWidget(QLineEdit):
    """Large PIN entry box (digits only, 4-6 chars)."""

    def __init__(self):
        super().__init__()
        self.setPlaceholderText("• • • •")
        self.setMaxLength(6)
        self.setEchoMode(QLineEdit.Password)
        self.setFixedHeight(64)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(_INPUT_STYLE)
        self.setInputMask("")

    def keyPressEvent(self, event):  # noqa: N802
        # Only allow digits and control keys
        if event.text().isdigit() or not event.text():
            super().keyPressEvent(event)


# --------------------------------------------------------------------------- #
#  Setup PIN Dialog (first time)                                               #
# --------------------------------------------------------------------------- #

class SetupPinDialog(QDialog):
    """
    Shown when a user has never set a Master PIN.
    Creates and stores a bcrypt hash in Firestore.

    Signals
    -------
    pin_set(pin: str)   – emitted with the raw PIN after it has been saved
    """

    pin_set = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Up Master PIN")
        self.setFixedSize(420, 380)
        self.setStyleSheet(_DIALOG_STYLE)
        self._threads: list[QThread] = []
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 32, 40, 32)
        lay.setSpacing(0)

        icon = QLabel("🔐")
        icon.setStyleSheet("font-size:48px;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)
        lay.addSpacing(12)

        title = QLabel("Create Master PIN")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addSpacing(6)

        sub = QLabel("This PIN encrypts your vault. Remember it – it cannot be recovered.")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)
        lay.addSpacing(24)

        pin_lbl = QLabel("Enter a 4–6 digit PIN")
        pin_lbl.setStyleSheet("color:#aaa;font-size:12px;")
        lay.addWidget(pin_lbl)
        self._pin_input = _PinInputWidget()
        lay.addWidget(self._pin_input)
        lay.addSpacing(12)

        confirm_lbl = QLabel("Confirm PIN")
        confirm_lbl.setStyleSheet("color:#aaa;font-size:12px;")
        lay.addWidget(confirm_lbl)
        self._confirm_input = _PinInputWidget()
        lay.addWidget(self._confirm_input)
        lay.addSpacing(20)

        self._ok_btn = QPushButton("Set PIN")
        self._ok_btn.setFixedHeight(46)
        self._ok_btn.setCursor(Qt.PointingHandCursor)
        self._ok_btn.setStyleSheet(_BTN_STYLE)
        self._ok_btn.clicked.connect(self._on_ok)
        lay.addWidget(self._ok_btn)

    def _set_loading(self, loading: bool):
        self._ok_btn.setEnabled(not loading)
        self._ok_btn.setText("Saving…" if loading else "Set PIN")

    def _on_ok(self):
        pin = self._pin_input.text().strip()
        confirm = self._confirm_input.text().strip()

        if not is_valid_pin(pin):
            show_toast(self.parent() or self, "PIN must be 4–6 digits.", "warning")
            return
        if pin != confirm:
            show_toast(self.parent() or self, "PINs do not match.", "warning")
            return

        self._set_loading(True)
        pin_hash = encryption_service.hash_pin(pin)

        worker = _SaveHashWorker(pin_hash)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda: self._on_saved(pin))
        worker.error.connect(lambda e: self._on_error(e))
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    def _on_saved(self, pin: str):
        self._set_loading(False)
        self.pin_set.emit(pin)
        self.accept()

    def _on_error(self, msg: str):
        self._set_loading(False)
        show_toast(self.parent() or self, f"Error saving PIN: {msg}", "error", 4000)


# --------------------------------------------------------------------------- #
#  Unlock PIN Dialog (subsequent logins)                                       #
# --------------------------------------------------------------------------- #

class UnlockPinDialog(QDialog):
    """
    Validate the entered PIN against the stored bcrypt hash.

    Signals
    -------
    unlocked(pin: str)
    """

    unlocked = Signal(str)

    def __init__(self, pin_hash: str, parent=None):
        super().__init__(parent)
        self._pin_hash = pin_hash
        self.setWindowTitle("Unlock Vault")
        self.setFixedSize(380, 320)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 32, 40, 32)
        lay.setSpacing(0)

        icon = QLabel("🔒")
        icon.setStyleSheet("font-size:48px;")
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)
        lay.addSpacing(12)

        title = QLabel("Vault Locked")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addSpacing(6)

        sub = QLabel("Enter your Master PIN to unlock the vault.")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)
        lay.addSpacing(24)

        pin_lbl = QLabel("Master PIN")
        pin_lbl.setStyleSheet("color:#aaa;font-size:12px;")
        lay.addWidget(pin_lbl)
        self._pin_input = _PinInputWidget()
        self._pin_input.returnPressed.connect(self._on_unlock)
        lay.addWidget(self._pin_input)
        lay.addSpacing(20)

        self._unlock_btn = QPushButton("Unlock Vault")
        self._unlock_btn.setFixedHeight(46)
        self._unlock_btn.setCursor(Qt.PointingHandCursor)
        self._unlock_btn.setStyleSheet(_BTN_STYLE)
        self._unlock_btn.clicked.connect(self._on_unlock)
        lay.addWidget(self._unlock_btn)

        lay.addSpacing(8)
        forgot_btn = QPushButton("Forgot PIN? Reset via email")
        forgot_btn.setStyleSheet(
            "background:none;border:none;color:#6c5ce7;font-size:12px;"
        )
        forgot_btn.setCursor(Qt.PointingHandCursor)
        forgot_btn.clicked.connect(self._on_forgot_pin)
        lay.addWidget(forgot_btn, alignment=Qt.AlignCenter)

    def _on_unlock(self):
        pin = self._pin_input.text().strip()
        if not is_valid_pin(pin):
            show_toast(self.parent() or self, "PIN must be 4–6 digits.", "warning")
            return
        if not encryption_service.verify_pin(pin, self._pin_hash):
            show_toast(self.parent() or self, "Incorrect PIN. Try again.", "error")
            self._pin_input.clear()
            return
        self.unlocked.emit(pin)
        self.accept()

    def _on_forgot_pin(self):
        if session.email:
            try:
                firebase_service.send_password_reset(session.email)
                show_toast(
                    self.parent() or self,
                    f"A password reset email has been sent to {session.email}. "
                    "After resetting, re-register your Master PIN.",
                    "info",
                    6000,
                )
            except FirebaseError as e:
                show_toast(self.parent() or self, str(e), "error", 4000)
        else:
            show_toast(self.parent() or self, "Could not determine account email.", "warning")
