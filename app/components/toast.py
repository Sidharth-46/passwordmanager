"""
Toast Notification component – displays brief, auto-dismissing messages.
"""

from PySide6.QtCore import QPropertyAnimation, QTimer, Qt, QPoint
from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PySide6.QtGui import QColor


_COLORS = {
    "success": ("#27ae60", "#fff"),
    "error":   ("#c0392b", "#fff"),
    "info":    ("#2980b9", "#fff"),
    "warning": ("#e67e22", "#fff"),
}


class Toast(QWidget):
    """A small pop-up notification that auto-dismisses after *duration* ms."""

    def __init__(self, parent: QWidget, message: str, kind: str = "info", duration: int = 3000):
        super().__init__(parent)
        bg, fg = _COLORS.get(kind, _COLORS["info"])

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {bg};
                border-radius: 8px;
            }}
            QLabel {{
                color: {fg};
                font-size: 13px;
                font-weight: 500;
                padding: 2px;
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        icon_map = {"success": "✓", "error": "✗", "info": "ℹ", "warning": "⚠"}
        icon = icon_map.get(kind, "ℹ")

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet(f"color: {fg}; font-size: 15px;")
        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)

        layout.addWidget(lbl_icon)
        layout.addWidget(lbl_msg)

        self.adjustSize()
        self._position_bottom_right()
        self.show()

        QTimer.singleShot(duration, self.close)

    def _position_bottom_right(self):
        parent = self.parent()
        if parent:
            pr = parent.rect()
            x = pr.width() - self.width() - 24
            y = pr.height() - self.height() - 24
            self.move(x, y)


def show_toast(parent: QWidget, message: str, kind: str = "info", duration: int = 3000) -> Toast:
    """Convenience function – creates and shows a Toast relative to *parent*."""
    return Toast(parent, message, kind, duration)
