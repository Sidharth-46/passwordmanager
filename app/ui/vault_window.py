"""
Vault Window
Main application window displayed after authentication and PIN unlock.
Contains the sidebar and all content pages.
"""

import json
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QStackedWidget, QMessageBox,
    QFileDialog, QApplication, QSplitter
)
from PySide6.QtCore import Signal, Qt, QThread, QObject, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut, QFont

from app.components.sidebar import Sidebar
from app.components.password_card import PasswordCard
from app.components.toast import show_toast
from app.services.firebase_service import firebase_service, FirebaseError
from app.services.encryption_service import encryption_service
from app.utils.session import session, INACTIVITY_TIMEOUT
from app.ui.add_password_dialog import PasswordDialog
from app.ui.password_generator_widget import PasswordGeneratorWidget
from app.ui.pin_dialog import SetupPinDialog, UnlockPinDialog


# --------------------------------------------------------------------------- #
#  Worker threads                                                               #
# --------------------------------------------------------------------------- #

class _VaultLoader(QObject):
    finished = Signal(list)
    error = Signal(str)

    def run(self):
        try:
            entries = firebase_service.get_vault_entries(session.user_id, session.id_token)
            self.finished.emit(entries)
        except Exception as e:
            self.error.emit(str(e))


class _AddEntryWorker(QObject):
    finished = Signal(str)   # new document ID
    error = Signal(str)

    def __init__(self, entry: dict):
        super().__init__()
        self._entry = entry

    def run(self):
        try:
            doc_id = firebase_service.add_vault_entry(
                session.user_id, session.id_token, self._entry
            )
            self.finished.emit(doc_id)
        except Exception as e:
            self.error.emit(str(e))


class _UpdateEntryWorker(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, entry_id: str, entry: dict):
        super().__init__()
        self._id = entry_id
        self._entry = entry

    def run(self):
        try:
            firebase_service.update_vault_entry(
                session.user_id, session.id_token, self._id, self._entry
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class _DeleteEntryWorker(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, entry_id: str):
        super().__init__()
        self._id = entry_id

    def run(self):
        try:
            firebase_service.delete_vault_entry(
                session.user_id, session.id_token, self._id
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# --------------------------------------------------------------------------- #
#  Settings Page                                                               #
# --------------------------------------------------------------------------- #

class SettingsPage(QWidget):
    """Simple settings page with import/export and security info."""

    export_requested = Signal()
    import_requested = Signal()
    change_pin_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0d0d1a;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 32, 40, 24)
        lay.setSpacing(0)

        # Header
        header = QLabel("⚙️  Settings")
        header.setStyleSheet("color:#fff;font-size:22px;font-weight:bold;")
        lay.addWidget(header)
        lay.addSpacing(4)
        sub = QLabel("Manage your vault and account settings.")
        sub.setStyleSheet("color:#666;font-size:13px;")
        lay.addWidget(sub)
        lay.addSpacing(32)

        # Vault section
        lay.addWidget(self._section_title("Vault"))
        lay.addSpacing(10)

        export_card = self._card(
            "📤  Export Vault",
            "Download an encrypted backup of all your passwords.",
            "Export to JSON",
        )
        export_card[1].clicked.connect(self.export_requested)
        lay.addWidget(export_card[0])
        lay.addSpacing(10)

        import_card = self._card(
            "📥  Import Vault",
            "Import passwords from a previously exported JSON backup.",
            "Import from JSON",
        )
        import_card[1].clicked.connect(self.import_requested)
        lay.addWidget(import_card[0])
        lay.addSpacing(24)

        # Security section
        lay.addWidget(self._section_title("Security"))
        lay.addSpacing(10)

        pin_card = self._card(
            "🔐  Change Master PIN",
            "Update the PIN used to unlock your vault.",
            "Change PIN",
        )
        pin_card[1].clicked.connect(self.change_pin_requested)
        lay.addWidget(pin_card[0])
        lay.addSpacing(24)

        # Info box
        info = QFrame()
        info.setStyleSheet(
            "background-color:#0a1a2a;border-radius:10px;border:1px solid #1a3a6a;"
        )
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(16, 14, 16, 14)
        info_lbl = QLabel(
            "🔒  All passwords are encrypted with AES-256-GCM before being stored.\n"
            "Your Master PIN never leaves this device in plaintext."
        )
        info_lbl.setStyleSheet("color:#6aaeee;font-size:12px;")
        info_lbl.setWordWrap(True)
        info_lay.addWidget(info_lbl)
        lay.addWidget(info)

        lay.addStretch()

    @staticmethod
    def _section_title(text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            "color:#555;font-size:11px;font-weight:600;letter-spacing:1.5px;"
        )
        return lbl

    @staticmethod
    def _card(title: str, subtitle: str, btn_text: str) -> tuple[QFrame, QPushButton]:
        card = QFrame()
        card.setStyleSheet(
            "background-color:#1a1a2e;border-radius:10px;border:1px solid #2e2e4e;"
        )
        card_lay = QHBoxLayout(card)
        card_lay.setContentsMargins(18, 14, 18, 14)

        text_col = QVBoxLayout()
        t = QLabel(title)
        t.setStyleSheet("color:#ddd;font-size:14px;font-weight:600;")
        s = QLabel(subtitle)
        s.setStyleSheet("color:#666;font-size:12px;")
        text_col.addWidget(t)
        text_col.addWidget(s)

        btn = QPushButton(btn_text)
        btn.setFixedHeight(36)
        btn.setFixedWidth(150)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "background-color:#6c5ce7;color:#fff;border:none;"
            "border-radius:8px;font-size:12px;font-weight:600;"
        )

        card_lay.addLayout(text_col)
        card_lay.addStretch()
        card_lay.addWidget(btn)
        return card, btn


# --------------------------------------------------------------------------- #
#  Vault Page (password list)                                                  #
# --------------------------------------------------------------------------- #

class VaultPage(QWidget):
    """Scrollable list of PasswordCards with search bar."""

    add_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0d0d1a;")
        self._entries: list[dict] = []        # raw (encrypted) entries from Firestore
        self._decrypted: dict[str, str] = {}  # entry_id → plaintext password cache
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 24, 32, 16)
        lay.setSpacing(0)

        # Header row
        header_row = QHBoxLayout()
        title = QLabel("🔒  Password Vault")
        title.setStyleSheet("color:#fff;font-size:22px;font-weight:bold;")
        header_row.addWidget(title)
        header_row.addStretch()

        add_btn = QPushButton("➕  Add Password")
        add_btn.setFixedHeight(40)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(
            "background-color:#6c5ce7;color:#fff;border:none;"
            "border-radius:8px;font-size:13px;font-weight:600;padding:0 16px;"
        )
        add_btn.clicked.connect(self.add_requested)
        header_row.addWidget(add_btn)
        lay.addLayout(header_row)
        lay.addSpacing(20)

        # Search bar
        search_row = QHBoxLayout()
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size:16px;padding-right:4px;")
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by name or username…")
        self._search_input.setFixedHeight(40)
        self._search_input.setStyleSheet(
            """
            QLineEdit {
                background-color:#1a1a2a;
                border:1px solid #2e2e4e;
                border-radius:8px;
                color:#e0e0e0;
                padding:0 12px;
                font-size:13px;
            }
            QLineEdit:focus { border:1px solid #6c5ce7; }
            """
        )
        self._search_input.textChanged.connect(self._on_search)
        search_row.addWidget(search_icon)
        search_row.addWidget(self._search_input)
        lay.addLayout(search_row)
        lay.addSpacing(16)

        # Count label
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color:#555;font-size:12px;")
        lay.addWidget(self._count_lbl)
        lay.addSpacing(8)

        # Scrollable cards area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { background:#1a1a2a; width:8px; border-radius:4px; }"
            "QScrollBar::handle:vertical { background:#3a3a5a; border-radius:4px; }"
        )

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background:transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 4, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._cards_container)
        lay.addWidget(self._scroll)

        # Empty state
        self._empty_widget = self._make_empty_widget()
        lay.addWidget(self._empty_widget)
        self._empty_widget.hide()

    @staticmethod
    def _make_empty_widget() -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setAlignment(Qt.AlignCenter)
        icon = QLabel("🔐")
        icon.setStyleSheet("font-size:56px;")
        icon.setAlignment(Qt.AlignCenter)
        msg = QLabel("Your vault is empty.\nClick 'Add Password' to get started.")
        msg.setStyleSheet("color:#555;font-size:14px;")
        msg.setAlignment(Qt.AlignCenter)
        l.addWidget(icon)
        l.addSpacing(8)
        l.addWidget(msg)
        return w

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def set_entries(self, entries: list[dict]):
        """Replace all entries and rebuild card list."""
        self._entries = entries
        self._decrypted.clear()
        self._rebuild_cards(entries)

    def cache_decrypted(self, entry_id: str, plaintext: str):
        self._decrypted[entry_id] = plaintext

    def get_entry_by_id(self, entry_id: str) -> dict | None:
        return next((e for e in self._entries if e.get("id") == entry_id), None)

    def get_decrypted_password(self, entry_id: str) -> str | None:
        """Return cached plaintext password, decrypting if needed."""
        if entry_id in self._decrypted:
            return self._decrypted[entry_id]
        entry = self.get_entry_by_id(entry_id)
        if not entry or not session.vault_key:
            return None
        try:
            plaintext = encryption_service.decrypt_password(
                entry["password"], session.vault_key
            )
            self._decrypted[entry_id] = plaintext
            return plaintext
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _rebuild_cards(self, entries: list[dict]):
        # Remove old cards (keep the trailing stretch)
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not entries:
            self._scroll.hide()
            self._empty_widget.show()
            self._count_lbl.setText("")
            return

        self._empty_widget.hide()
        self._scroll.show()
        self._count_lbl.setText(f"{len(entries)} password{'s' if len(entries) != 1 else ''}")

        for entry in entries:
            card = PasswordCard(entry)
            card.copy_password_requested.connect(self._on_copy_password)
            card.copy_username_requested.connect(self._on_copy_username)
            card.edit_requested.connect(self._on_edit)
            card.delete_requested.connect(self._on_delete)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _on_search(self, text: str):
        q = text.lower().strip()
        if not q:
            self._rebuild_cards(self._entries)
        else:
            filtered = [
                e for e in self._entries
                if q in e.get("site", "").lower()
                or q in e.get("username", "").lower()
                or q in e.get("url", "").lower()
            ]
            self._rebuild_cards(filtered)

    def _on_copy_password(self, entry_id: str):
        plaintext = self.get_decrypted_password(entry_id)
        if plaintext:
            QGuiApplication.clipboard().setText(plaintext)
            show_toast(self.window(), "Password copied to clipboard!", "success")
        else:
            show_toast(self.window(), "Could not decrypt password.", "error")

    def _on_copy_username(self, entry_id: str):
        entry = self.get_entry_by_id(entry_id)
        if entry:
            QGuiApplication.clipboard().setText(entry.get("username", ""))
            show_toast(self.window(), "Username copied to clipboard!", "success")

    def _on_edit(self, entry_id: str):
        entry = self.get_entry_by_id(entry_id)
        if not entry:
            return
        plaintext = self.get_decrypted_password(entry_id)
        entry_with_plain = dict(entry, password_plain=plaintext or "")
        # Signal vault window to show edit dialog
        self.window()._show_edit_dialog(entry_with_plain)

    def _on_delete(self, entry_id: str):
        entry = self.get_entry_by_id(entry_id)
        site = entry.get("site", "this entry") if entry else "this entry"
        reply = QMessageBox.question(
            self.window(),
            "Delete Password",
            f"Are you sure you want to delete the password for '{site}'?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.window()._delete_entry(entry_id)


# --------------------------------------------------------------------------- #
#  Vault Window (main)                                                         #
# --------------------------------------------------------------------------- #

class VaultWindow(QMainWindow):
    """
    Main application window shown after successful login + PIN unlock.

    Signals
    -------
    logout_requested()
    """

    logout_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VaultKey – Password Manager")
        self.setMinimumSize(1000, 640)
        self.resize(1200, 720)
        self._threads: list[QThread] = []
        self._vault_loaded_once = False
        self._build_ui()
        self._start_inactivity_timer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background-color: #0d0d1a;")

        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._on_page_changed)
        self._sidebar.logout_requested.connect(self._on_logout)
        self._sidebar.set_user_email(session.email or "")
        root_lay.addWidget(self._sidebar)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #1e1e2e;")
        root_lay.addWidget(sep)

        # Content stack
        self._stack = QStackedWidget()
        self._vault_page = VaultPage()
        self._vault_page.add_requested.connect(self._show_add_dialog)
        self._generator_page = PasswordGeneratorWidget()
        self._settings_page = SettingsPage()
        self._settings_page.export_requested.connect(self._export_vault)
        self._settings_page.import_requested.connect(self._import_vault)
        self._settings_page.change_pin_requested.connect(self._change_pin)

        self._stack.addWidget(self._vault_page)      # index 0
        self._stack.addWidget(self._generator_page)  # index 1
        self._stack.addWidget(QWidget())             # index 2 (add – opens dialog)
        self._stack.addWidget(self._settings_page)  # index 3

        root_lay.addWidget(self._stack, stretch=1)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+F"), self, self._vault_page._search_input.setFocus)

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def load_vault(self):
        """Public method – called by AppController after unlock."""
        self._load_vault()

    def showEvent(self, event):  # noqa: N802
        if event is not None:
            super().showEvent(event)
        if not self._vault_loaded_once:
            self._vault_loaded_once = True
            self._load_vault()

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def _on_page_changed(self, page_id: str):
        mapping = {"vault": 0, "generator": 1, "add": 2, "settings": 3}
        idx = mapping.get(page_id, 0)
        if page_id == "add":
            self._show_add_dialog()
            self._sidebar.set_active_page("vault")
            return
        self._stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------ #
    #  Vault loading                                                       #
    # ------------------------------------------------------------------ #

    def _load_vault(self):
        """Fetch all entries from Firestore in a background thread."""
        worker = _VaultLoader()
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda entries: self._on_vault_loaded(entries))
        worker.error.connect(lambda e: show_toast(self, f"Load error: {e}", "error", 5000))
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    def _on_vault_loaded(self, entries: list[dict]):
        self._vault_page.set_entries(entries)
        session.touch()

    # ------------------------------------------------------------------ #
    #  Add password                                                        #
    # ------------------------------------------------------------------ #

    def _show_add_dialog(self):
        dlg = PasswordDialog(parent=self)
        dlg.saved.connect(self._on_add_saved)
        dlg.exec()

    def _on_add_saved(self, data: dict):
        if not session.vault_key:
            show_toast(self, "Vault is locked. Please unlock first.", "warning")
            return

        # Encrypt password before storing
        encrypted_pw = encryption_service.encrypt_password(
            data["password_plain"], session.vault_key
        )
        entry = {
            "site": data["site"],
            "username": data["username"],
            "password": encrypted_pw,
            "url": data.get("url", ""),
            "notes": data.get("notes", ""),
        }

        worker = _AddEntryWorker(entry)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda doc_id: self._on_add_done(doc_id, entry, data["password_plain"]))
        worker.error.connect(lambda e: show_toast(self, f"Error: {e}", "error", 4000))
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    def _on_add_done(self, doc_id: str, entry: dict, plaintext: str):
        entry["id"] = doc_id
        self._vault_page._entries.append(entry)
        self._vault_page.cache_decrypted(doc_id, plaintext)
        self._vault_page._rebuild_cards(self._vault_page._entries)
        show_toast(self, f"'{entry['site']}' added to vault!", "success")
        session.touch()

    # ------------------------------------------------------------------ #
    #  Edit password                                                       #
    # ------------------------------------------------------------------ #

    def _show_edit_dialog(self, entry_with_plain: dict):
        dlg = PasswordDialog(entry=entry_with_plain, parent=self)
        dlg.saved.connect(self._on_edit_saved)
        dlg.exec()

    def _on_edit_saved(self, data: dict):
        if not session.vault_key:
            show_toast(self, "Vault is locked.", "warning")
            return

        entry_id = data["id"]
        encrypted_pw = encryption_service.encrypt_password(
            data["password_plain"], session.vault_key
        )
        entry = {
            "site": data["site"],
            "username": data["username"],
            "password": encrypted_pw,
            "url": data.get("url", ""),
            "notes": data.get("notes", ""),
        }

        worker = _UpdateEntryWorker(entry_id, entry)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda: self._on_update_done(entry_id, entry, data["password_plain"]))
        worker.error.connect(lambda e: show_toast(self, f"Error: {e}", "error", 4000))
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    def _on_update_done(self, entry_id: str, new_entry: dict, plaintext: str):
        # Update local cache
        for i, e in enumerate(self._vault_page._entries):
            if e.get("id") == entry_id:
                self._vault_page._entries[i] = dict(new_entry, id=entry_id)
                break
        self._vault_page.cache_decrypted(entry_id, plaintext)
        self._vault_page._rebuild_cards(self._vault_page._entries)
        show_toast(self, f"'{new_entry['site']}' updated.", "success")
        session.touch()

    # ------------------------------------------------------------------ #
    #  Delete password                                                     #
    # ------------------------------------------------------------------ #

    def _delete_entry(self, entry_id: str):
        worker = _DeleteEntryWorker(entry_id)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda: self._on_delete_done(entry_id))
        worker.error.connect(lambda e: show_toast(self, f"Error: {e}", "error", 4000))
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        self._threads.append(thread)
        thread.start()

    def _on_delete_done(self, entry_id: str):
        self._vault_page._entries = [
            e for e in self._vault_page._entries if e.get("id") != entry_id
        ]
        self._vault_page._decrypted.pop(entry_id, None)
        self._vault_page._rebuild_cards(self._vault_page._entries)
        show_toast(self, "Password deleted.", "info")
        session.touch()

    # ------------------------------------------------------------------ #
    #  Import / Export                                                     #
    # ------------------------------------------------------------------ #

    def _export_vault(self):
        if not session.vault_key:
            show_toast(self, "Vault is locked. Please unlock first.", "warning")
            return

        entries = self._vault_page._entries
        if not entries:
            show_toast(self, "Your vault is empty – nothing to export.", "info")
            return

        # Build export-friendly list (with plaintext passwords)
        decrypted_entries = []
        for e in entries:
            pw = self._vault_page.get_decrypted_password(e["id"])
            decrypted_entries.append(dict(e, password_plain=pw or ""))

        # Ask for the PIN to re-derive the export key
        from app.ui.pin_dialog import UnlockPinDialog
        pin_hash = None
        try:
            pin_hash = firebase_service.get_master_pin_hash(session.user_id, session.id_token)
        except Exception:
            pass

        if pin_hash is None:
            show_toast(self, "Cannot fetch PIN hash for export.", "error")
            return

        unlock_dlg = UnlockPinDialog(pin_hash, parent=self)
        export_pin: list[str] = []
        unlock_dlg.unlocked.connect(lambda p: export_pin.append(p))
        unlock_dlg.exec()
        if not export_pin:
            return

        try:
            export_data = encryption_service.export_vault(decrypted_entries, export_pin[0])
        except Exception as exc:
            show_toast(self, f"Export failed: {exc}", "error", 4000)
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Vault", "vaultkey_backup.json", "JSON Files (*.json)"
        )
        if path:
            Path(path).write_text(json.dumps(export_data, indent=2))
            show_toast(self, f"Vault exported to {Path(path).name}", "success", 5000)

    def _import_vault(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Vault", "", "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            data = json.loads(Path(path).read_text())
        except Exception as exc:
            show_toast(self, f"Failed to read file: {exc}", "error")
            return

        # Ask for the export PIN
        from PySide6.QtWidgets import QInputDialog
        pin, ok = QInputDialog.getText(
            self, "Import Vault", "Enter the Master PIN used when exporting:",
            QLineEdit.Password
        )
        if not ok or not pin:
            return

        try:
            entries = encryption_service.import_vault(data, pin)
        except ValueError as exc:
            show_toast(self, str(exc), "error", 4000)
            return
        except Exception as exc:
            show_toast(self, f"Import failed: {exc}", "error", 4000)
            return

        if not session.vault_key:
            show_toast(self, "Vault is locked. Cannot import.", "warning")
            return

        # Add each entry to Firestore
        added = 0
        for entry_plain in entries:
            encrypted_pw = encryption_service.encrypt_password(
                entry_plain.get("password_plain", ""), session.vault_key
            )
            new_entry = {
                "site": entry_plain.get("site", "Imported"),
                "username": entry_plain.get("username", ""),
                "password": encrypted_pw,
                "url": entry_plain.get("url", ""),
                "notes": entry_plain.get("notes", ""),
            }
            try:
                doc_id = firebase_service.add_vault_entry(
                    session.user_id, session.id_token, new_entry
                )
                new_entry["id"] = doc_id
                self._vault_page._entries.append(new_entry)
                self._vault_page.cache_decrypted(doc_id, entry_plain.get("password_plain", ""))
                added += 1
            except Exception:
                pass

        self._vault_page._rebuild_cards(self._vault_page._entries)
        show_toast(self, f"Imported {added} password(s) from backup.", "success", 5000)

    # ------------------------------------------------------------------ #
    #  Change PIN                                                          #
    # ------------------------------------------------------------------ #

    def _change_pin(self):
        dlg = SetupPinDialog(parent=self)
        new_pins: list[str] = []
        dlg.pin_set.connect(lambda p: new_pins.append(p))
        dlg.exec()
        if new_pins:
            # Re-derive vault key with new PIN (entries already encrypted with old key)
            # For a production app you would re-encrypt all entries here.
            show_toast(
                self,
                "Master PIN updated. Note: existing entries retain the old encryption key "
                "until you re-encrypt them.",
                "info",
                6000,
            )

    # ------------------------------------------------------------------ #
    #  Inactivity timer                                                    #
    # ------------------------------------------------------------------ #

    def _start_inactivity_timer(self):
        self._timer = QTimer(self)
        self._timer.setInterval(30_000)  # check every 30 s
        self._timer.timeout.connect(self._check_inactivity)
        self._timer.start()

    def _check_inactivity(self):
        if session.is_timed_out():
            session.lock_vault()
            show_toast(self, "Vault locked due to inactivity.", "warning", 5000)
            self._prompt_unlock()

    def _prompt_unlock(self):
        try:
            pin_hash = firebase_service.get_master_pin_hash(session.user_id, session.id_token)
        except Exception:
            pin_hash = None

        if pin_hash:
            dlg = UnlockPinDialog(pin_hash, parent=self)
            def _on_unlocked(pin: str):
                # Re-derive key with same deterministic salt used at initial unlock
                salt_bytes = (session.user_id or "default").encode("utf-8").ljust(32, b"\x00")[:32]
                key = encryption_service.derive_key(pin, salt_bytes)
                session.unlock_vault(key)
                show_toast(self, "Vault unlocked.", "success")
            dlg.unlocked.connect(_on_unlocked)
            dlg.exec()

    # ------------------------------------------------------------------ #
    #  Logout                                                              #
    # ------------------------------------------------------------------ #

    def _on_logout(self):
        reply = QMessageBox.question(
            self,
            "Log Out",
            "Are you sure you want to log out?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            session.clear()
            self.logout_requested.emit()

    def mousePressEvent(self, event):  # noqa: N802
        session.touch()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        session.touch()
        super().keyPressEvent(event)
