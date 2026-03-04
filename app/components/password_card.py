"""
Password Card – a card-style widget representing a single vault entry.
Emits signals for copy/edit/delete actions.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont


class PasswordCard(QWidget):
    """
    Compact card displaying site, username, and action buttons.

    Signals
    -------
    copy_password_requested(entry_id: str)
    copy_username_requested(entry_id: str)
    edit_requested(entry_id: str)
    delete_requested(entry_id: str)
    """

    copy_password_requested = Signal(str)
    copy_username_requested = Signal(str)
    edit_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self._entry_id = entry.get("id", "")
        self._site = entry.get("site", "Untitled")
        self._username = entry.get("username", "")
        self._url = entry.get("url", "")

        self._build_ui()

    def _build_ui(self):
        self.setObjectName("PasswordCard")
        self.setStyleSheet(
            """
            QWidget#PasswordCard {
                background-color: #1e1e2e;
                border-radius: 10px;
                border: 1px solid #2e2e3e;
            }
            QWidget#PasswordCard:hover {
                border: 1px solid #6c5ce7;
            }
            """
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 12, 12, 12)
        outer.setSpacing(12)

        # Avatar circle showing first letter
        avatar = QLabel(self._site[0].upper() if self._site else "?")
        avatar.setFixedSize(44, 44)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFont(QFont("Arial", 16, QFont.Bold))
        avatar.setStyleSheet(
            "background-color: #6c5ce7; border-radius: 22px; color: #fff;"
        )
        outer.addWidget(avatar)

        # Site + username info
        info_col = QVBoxLayout()
        info_col.setSpacing(3)

        site_lbl = QLabel(self._site)
        site_lbl.setFont(QFont("Arial", 13, QFont.Bold))
        site_lbl.setStyleSheet("color: #e0e0e0;")

        username_lbl = QLabel(self._username or "No username")
        username_lbl.setStyleSheet("color: #888; font-size: 12px;")

        url_lbl = QLabel(self._url or "")
        url_lbl.setStyleSheet("color: #6c5ce7; font-size: 11px;")

        info_col.addWidget(site_lbl)
        info_col.addWidget(username_lbl)
        if self._url:
            info_col.addWidget(url_lbl)

        outer.addLayout(info_col)
        outer.addStretch()

        # Action buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        btn_copy_pw = self._icon_btn("🔑", "Copy password")
        btn_copy_user = self._icon_btn("👤", "Copy username")
        btn_edit = self._icon_btn("✏️", "Edit")
        btn_delete = self._icon_btn("🗑️", "Delete")
        btn_delete.setStyleSheet(btn_delete.styleSheet() + "color: #e74c3c;")

        btn_copy_pw.clicked.connect(lambda: self.copy_password_requested.emit(self._entry_id))
        btn_copy_user.clicked.connect(lambda: self.copy_username_requested.emit(self._entry_id))
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._entry_id))
        btn_delete.clicked.connect(lambda: self.delete_requested.emit(self._entry_id))

        action_row = QHBoxLayout()
        action_row.setSpacing(2)
        for btn in (btn_copy_pw, btn_copy_user, btn_edit, btn_delete):
            action_row.addWidget(btn)

        outer.addLayout(action_row)

    @staticmethod
    def _icon_btn(icon: str, tooltip: str) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(32, 32)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2e2e3e;
            }
            QPushButton:pressed {
                background-color: #3a3a4e;
            }
            """
        )
        return btn

    def update_entry(self, entry: dict):
        """Refresh displayed data without rebuilding the widget."""
        self._entry_id = entry.get("id", self._entry_id)
        self._site = entry.get("site", self._site)
        self._username = entry.get("username", self._username)
        self._url = entry.get("url", self._url)
        # Full rebuild for simplicity
        for child in self.children():
            if hasattr(child, "deleteLater"):
                child.deleteLater()
        self._build_ui()
