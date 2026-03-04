"""
Add / Edit Password Dialog
Provides a form for creating or modifying a vault entry.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QCheckBox
)
from PySide6.QtCore import Signal, Qt

from app.components.strength_meter import StrengthMeter
from app.components.toast import show_toast
from app.utils.helpers import generate_password


_FIELD_STYLE = """
QLineEdit, QTextEdit {
    background-color: #1a1a2a;
    border: 1px solid #2e2e4e;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus { border: 1px solid #6c5ce7; }
"""


class PasswordDialog(QDialog):
    """
    Dialog for adding or editing a vault entry.

    Parameters
    ----------
    entry : dict | None
        Existing entry (edit mode) or None (add mode).
        For edit mode, pass the entry dict with a ``password_plain`` key
        holding the *decrypted* password.

    Signals
    -------
    saved(entry_data: dict)
        dict contains: site, username, password_plain, url, notes
        (and ``id`` if in edit mode)
    """

    saved = Signal(dict)

    def __init__(self, entry: dict | None = None, parent=None):
        super().__init__(parent)
        self._edit_mode = entry is not None
        self._entry = entry or {}
        self.setWindowTitle("Edit Password" if self._edit_mode else "Add Password")
        self.setMinimumWidth(480)
        self.setStyleSheet("background-color: #0d0d1a; color: #e0e0e0;")
        self._build_ui()
        if self._edit_mode:
            self._populate()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        # Title
        title = QLabel("✏️  Edit Password" if self._edit_mode else "➕  Add Password")
        title.setStyleSheet("color:#fff;font-size:18px;font-weight:bold;")
        lay.addWidget(title)

        # Site / App name
        lay.addWidget(self._lbl("Website / App Name *"))
        self._site_input = self._input("e.g. GitHub")
        lay.addWidget(self._site_input)

        # Username
        lay.addWidget(self._lbl("Username / Email *"))
        self._username_input = self._input("your@email.com")
        lay.addWidget(self._username_input)

        # Password row
        lay.addWidget(self._lbl("Password *"))
        pw_row = QHBoxLayout()
        pw_row.setSpacing(6)
        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Enter or generate a password")
        self._password_input.setEchoMode(QLineEdit.Password)
        self._password_input.setFixedHeight(40)
        self._password_input.setStyleSheet(_FIELD_STYLE)
        self._password_input.textChanged.connect(self._on_pw_changed)

        self._show_cb = QCheckBox("👁")
        self._show_cb.setStyleSheet("color:#888;")
        self._show_cb.toggled.connect(
            lambda on: self._password_input.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password
            )
        )

        gen_btn = QPushButton("⚡ Generate")
        gen_btn.setFixedHeight(40)
        gen_btn.setCursor(Qt.PointingHandCursor)
        gen_btn.setStyleSheet(
            "background-color:#2e2e4e;color:#aaa;border:1px solid #3e3e6e;"
            "border-radius:8px;font-size:12px;"
        )
        gen_btn.clicked.connect(self._on_generate)

        pw_row.addWidget(self._password_input)
        pw_row.addWidget(self._show_cb)
        pw_row.addWidget(gen_btn)
        lay.addLayout(pw_row)

        # Strength meter
        self._strength = StrengthMeter()
        lay.addWidget(self._strength)

        # URL
        lay.addWidget(self._lbl("Website URL (optional)"))
        self._url_input = self._input("https://example.com")
        lay.addWidget(self._url_input)

        # Notes
        lay.addWidget(self._lbl("Notes (optional)"))
        self._notes_input = QTextEdit()
        self._notes_input.setPlaceholderText("Any extra information…")
        self._notes_input.setFixedHeight(80)
        self._notes_input.setStyleSheet(_FIELD_STYLE)
        lay.addWidget(self._notes_input)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(42)
        cancel_btn.setFixedWidth(100)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "background-color:#1e1e2e;color:#aaa;border:1px solid #3e3e6e;"
            "border-radius:8px;font-size:13px;"
        )
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("💾  Save")
        save_btn.setFixedHeight(42)
        save_btn.setFixedWidth(120)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(
            "background-color:#6c5ce7;color:#fff;border:none;"
            "border-radius:8px;font-size:13px;font-weight:600;"
        )
        save_btn.clicked.connect(self._on_save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#aaa;font-size:12px;")
        return lbl

    @staticmethod
    def _input(placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(40)
        edit.setStyleSheet(_FIELD_STYLE)
        return edit

    def _populate(self):
        self._site_input.setText(self._entry.get("site", ""))
        self._username_input.setText(self._entry.get("username", ""))
        self._password_input.setText(self._entry.get("password_plain", ""))
        self._url_input.setText(self._entry.get("url", ""))
        self._notes_input.setPlainText(self._entry.get("notes", ""))

    def _on_pw_changed(self, text: str):
        self._strength.update_strength(text)

    def _on_generate(self):
        pwd = generate_password(length=18)
        self._password_input.setText(pwd)
        self._password_input.setEchoMode(QLineEdit.Normal)
        self._show_cb.setChecked(True)

    def _on_save(self):
        site = self._site_input.text().strip()
        username = self._username_input.text().strip()
        password = self._password_input.text()

        if not site:
            show_toast(self.parent() or self, "Website/App name is required.", "warning")
            return
        if not username:
            show_toast(self.parent() or self, "Username is required.", "warning")
            return
        if not password:
            show_toast(self.parent() or self, "Password is required.", "warning")
            return

        data = {
            "site": site,
            "username": username,
            "password_plain": password,
            "url": self._url_input.text().strip(),
            "notes": self._notes_input.toPlainText().strip(),
        }
        if self._edit_mode:
            data["id"] = self._entry.get("id", "")

        self.saved.emit(data)
        self.accept()
