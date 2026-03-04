"""
Password Generator Widget
Full-featured standalone generator with sliders, option checkboxes,
strength meter, and copy-to-clipboard.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox,
    QPushButton, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QGuiApplication

from app.utils.helpers import generate_password, password_strength, STRENGTH_COLORS
from app.components.strength_meter import StrengthMeter
from app.components.toast import show_toast


class PasswordGeneratorWidget(QWidget):
    """
    Self-contained password generator page.

    Signals
    -------
    use_password(password: str)
        Emitted when the user clicks "Use This Password" (for integration
        into the Add Password dialog when opened from vault).
    """

    use_password = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0d0d1a;")
        self._build_ui()
        self._regenerate()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 32, 40, 24)
        lay.setSpacing(0)

        # Header
        header = QLabel("⚡  Password Generator")
        header.setStyleSheet("color:#fff;font-size:22px;font-weight:bold;")
        lay.addWidget(header)
        lay.addSpacing(4)
        sub = QLabel("Generate a strong, random password instantly.")
        sub.setStyleSheet("color:#666;font-size:13px;")
        lay.addWidget(sub)
        lay.addSpacing(28)

        # Generated password display
        pw_card = QFrame()
        pw_card.setStyleSheet(
            "background-color:#1a1a2e;border-radius:12px;border:1px solid #2e2e4e;"
        )
        pw_card_lay = QHBoxLayout(pw_card)
        pw_card_lay.setContentsMargins(16, 16, 16, 16)

        self._pw_display = QLineEdit()
        self._pw_display.setReadOnly(True)
        self._pw_display.setFont(QFont("Courier New", 17))
        self._pw_display.setStyleSheet(
            "background:transparent;border:none;color:#7efff5;font-size:17px;"
        )
        pw_card_lay.addWidget(self._pw_display)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(40, 40)
        refresh_btn.setToolTip("Regenerate")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(
            "background:#2e2e4e;border:none;border-radius:8px;font-size:18px;"
        )
        refresh_btn.clicked.connect(self._regenerate)
        pw_card_lay.addWidget(refresh_btn)

        lay.addWidget(pw_card)
        lay.addSpacing(12)

        # Strength meter
        self._strength = StrengthMeter()
        lay.addWidget(self._strength)
        lay.addSpacing(24)

        # ---- Options ----
        section = QLabel("Options")
        section.setStyleSheet("color:#888;font-size:12px;font-weight:600;letter-spacing:1px;")
        lay.addWidget(section)
        lay.addSpacing(12)

        options_card = QFrame()
        options_card.setStyleSheet(
            "background-color:#1a1a2e;border-radius:12px;border:1px solid #2e2e4e;"
        )
        options_lay = QVBoxLayout(options_card)
        options_lay.setContentsMargins(20, 16, 20, 20)
        options_lay.setSpacing(16)

        # Length slider
        len_row = QHBoxLayout()
        len_lbl = QLabel("Length")
        len_lbl.setStyleSheet("color:#ccc;font-size:13px;")
        self._len_val_lbl = QLabel("18")
        self._len_val_lbl.setStyleSheet(
            "color:#6c5ce7;font-size:14px;font-weight:bold;min-width:30px;"
        )
        self._len_val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._len_slider = QSlider(Qt.Horizontal)
        self._len_slider.setRange(8, 64)
        self._len_slider.setValue(18)
        self._len_slider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                height: 6px;
                background: #2e2e4e;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #6c5ce7;
                width: 18px;
                height: 18px;
                border-radius: 9px;
                margin: -6px 0;
            }
            QSlider::sub-page:horizontal {
                background: #6c5ce7;
                border-radius: 3px;
            }
            """
        )
        self._len_slider.valueChanged.connect(self._on_length_changed)

        len_row.addWidget(len_lbl)
        len_row.addWidget(self._len_slider)
        len_row.addWidget(self._len_val_lbl)
        options_lay.addLayout(len_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#2e2e4e;")
        options_lay.addWidget(sep)

        # Character type checkboxes
        checkbox_row = QHBoxLayout()
        self._cb_upper = self._checkbox("A–Z", True)
        self._cb_lower = self._checkbox("a–z", True)
        self._cb_digits = self._checkbox("0–9", True)
        self._cb_symbols = self._checkbox("!@#…", True)

        for cb in (self._cb_upper, self._cb_lower, self._cb_digits, self._cb_symbols):
            cb.toggled.connect(self._regenerate)
            checkbox_row.addWidget(cb)

        options_lay.addLayout(checkbox_row)
        lay.addWidget(options_card)
        lay.addSpacing(24)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        copy_btn = QPushButton("📋  Copy Password")
        copy_btn.setFixedHeight(46)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(
            "background-color:#6c5ce7;color:#fff;border:none;"
            "border-radius:8px;font-size:14px;font-weight:600;"
        )
        copy_btn.clicked.connect(self._copy_password)

        use_btn = QPushButton("Use This Password")
        use_btn.setFixedHeight(46)
        use_btn.setCursor(Qt.PointingHandCursor)
        use_btn.setStyleSheet(
            "background-color:#1e1e2e;color:#aaa;border:1px solid #3e3e6e;"
            "border-radius:8px;font-size:14px;"
        )
        use_btn.clicked.connect(
            lambda: self.use_password.emit(self._pw_display.text())
        )

        btn_row.addWidget(copy_btn)
        btn_row.addWidget(use_btn)
        lay.addLayout(btn_row)
        lay.addStretch()

    @staticmethod
    def _checkbox(label: str, checked: bool) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(checked)
        cb.setStyleSheet(
            """
            QCheckBox { color: #ccc; font-size: 13px; }
            QCheckBox::indicator {
                width: 18px; height: 18px;
                border-radius: 5px;
                border: 1px solid #3e3e6e;
                background: #1e1e2e;
            }
            QCheckBox::indicator:checked {
                background: #6c5ce7;
                border: 1px solid #6c5ce7;
            }
            """
        )
        return cb

    def _on_length_changed(self, val: int):
        self._len_val_lbl.setText(str(val))
        self._regenerate()

    def _regenerate(self):
        password = generate_password(
            length=self._len_slider.value(),
            use_upper=self._cb_upper.isChecked(),
            use_lower=self._cb_lower.isChecked(),
            use_digits=self._cb_digits.isChecked(),
            use_symbols=self._cb_symbols.isChecked(),
        )
        self._pw_display.setText(password)
        self._strength.update_strength(password)

    def _copy_password(self):
        password = self._pw_display.text()
        QGuiApplication.clipboard().setText(password)
        show_toast(self.parent() or self, "Password copied to clipboard!", "success")
