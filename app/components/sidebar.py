"""
Sidebar navigation widget.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, QSpacerItem,
    QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont


NAV_ITEMS = [
    ("vault",      "🔒", "Vault"),
    ("add",        "➕", "Add Password"),
    ("generator",  "⚡", "Generator"),
    ("settings",   "⚙️",  "Settings"),
]


class SidebarButton(QPushButton):
    """A single navigation button in the sidebar."""

    def __init__(self, icon: str, text: str):
        super().__init__(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(48)
        self._apply_style(active=False)

    def _apply_style(self, active: bool):
        if active:
            self.setStyleSheet(
                """
                QPushButton {
                    background-color: #6c5ce7;
                    color: #fff;
                    border: none;
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 14px;
                    font-weight: 600;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #aaa;
                    border: none;
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #2a2a3a;
                    color: #eee;
                }
                """
            )

    def setActive(self, active: bool):  # noqa: N802
        self._apply_style(active)
        self.setChecked(active)


class Sidebar(QWidget):
    """
    Left navigation panel.

    Signals
    -------
    page_changed(page_id: str)
        Emitted with the page identifier when user clicks a nav item.
    logout_requested()
    """

    page_changed = Signal(str)
    logout_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(230)
        self.setStyleSheet("background-color: #13131f;")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 20, 12, 20)
        root.setSpacing(6)

        # App logo + name
        logo_row = QHBoxLayout()
        logo_lbl = QLabel("🛡️")
        logo_lbl.setStyleSheet("font-size: 28px;")
        title_lbl = QLabel("VaultKey")
        title_lbl.setStyleSheet(
            "color: #e0e0e0; font-size: 18px; font-weight: bold;"
        )
        logo_row.addWidget(logo_lbl)
        logo_row.addWidget(title_lbl)
        logo_row.addStretch()
        root.addLayout(logo_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #2e2e3e; margin: 8px 0;")
        root.addWidget(sep)

        # Nav buttons
        self._buttons: dict[str, SidebarButton] = {}
        for page_id, icon, label in NAV_ITEMS:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda checked, pid=page_id: self._on_nav(pid))
            self._buttons[page_id] = btn
            root.addWidget(btn)

        root.addStretch()

        # Separator above logout
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #2e2e3e; margin: 4px 0;")
        root.addWidget(sep2)

        # User info + logout
        self._user_label = QLabel("user@email.com")
        self._user_label.setStyleSheet("color: #666; font-size: 11px; padding-left: 12px;")
        self._user_label.setWordWrap(True)
        root.addWidget(self._user_label)

        logout_btn = QPushButton("  ⏻  Logout")
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setFixedHeight(42)
        logout_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #e74c3c;
                border: 1px solid #3a1a1a;
                border-radius: 8px;
                text-align: left;
                padding-left: 12px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2a1a1a; }
            """
        )
        logout_btn.clicked.connect(self.logout_requested)
        root.addWidget(logout_btn)

        self.set_active_page("vault")

    def set_active_page(self, page_id: str):
        for pid, btn in self._buttons.items():
            btn.setActive(pid == page_id)

    def set_user_email(self, email: str):
        self._user_label.setText(email or "")

    def _on_nav(self, page_id: str):
        self.set_active_page(page_id)
        self.page_changed.emit(page_id)
