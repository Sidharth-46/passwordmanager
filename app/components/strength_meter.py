"""
Password strength meter widget.
Shows 4 colored bars and a label.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from app.utils.helpers import password_strength, STRENGTH_COLORS


class StrengthBar(QFrame):
    """A single colored segment of the strength meter."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(6)
        self.setStyleSheet("background-color: #3a3a4a; border-radius: 3px;")

    def set_active(self, color: str):
        self.setStyleSheet(f"background-color: {color}; border-radius: 3px;")

    def set_inactive(self):
        self.setStyleSheet("background-color: #3a3a4a; border-radius: 3px;")


class StrengthMeter(QWidget):
    """4-segment password strength meter with descriptive label."""

    SEGMENTS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        bars_row = QHBoxLayout()
        bars_row.setSpacing(4)
        self._bars: list[StrengthBar] = []
        for _ in range(self.SEGMENTS):
            bar = StrengthBar()
            self._bars.append(bar)
            bars_row.addWidget(bar)

        self._label = QLabel("")
        self._label.setStyleSheet("color: #888; font-size: 11px;")
        self._label.setAlignment(Qt.AlignRight)

        root.addLayout(bars_row)
        root.addWidget(self._label)

    def update_strength(self, password: str):
        """Recalculate and repaint based on *password*."""
        score, label = password_strength(password)
        color = STRENGTH_COLORS[score]

        # Decide how many bars to light up (map 0-4 → 0-4 bars)
        active = score  # 0 bars for Very Weak, 4 for Very Strong

        for i, bar in enumerate(self._bars):
            if i < active:
                bar.set_active(color)
            else:
                bar.set_inactive()

        self._label.setText(label)
        self._label.setStyleSheet(f"color: {color}; font-size: 11px;")
