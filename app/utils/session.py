"""
Session Manager
Holds the authenticated user state and the unlocked encryption key in memory.
"""

import json
import os
import time
from pathlib import Path

# Persist only non-secret info between runs (tokens are refreshed as needed)
_SESSION_FILE = Path.home() / ".pm_session.json"

# Inactivity timeout before vault auto-locks (seconds)
INACTIVITY_TIMEOUT = 5 * 60  # 5 minutes


class SessionManager:
    """
    In-memory store for the current user session.

    Attributes
    ----------
    user_id : str | None
        Firebase UID of the logged-in user.
    id_token : str | None
        Firebase ID token (short-lived).
    refresh_token : str | None
        Firebase refresh token (long-lived).
    email : str | None
        User email address.
    display_name : str | None
        User display name (from Google or Firebase).
    vault_key : bytes | None
        32-byte AES key derived from the Master PIN after unlock.
    last_activity : float
        Unix timestamp of the last user activity on the vault.
    """

    def __init__(self):
        self.user_id: str | None = None
        self.id_token: str | None = None
        self.refresh_token: str | None = None
        self.email: str | None = None
        self.display_name: str | None = None
        self.vault_key: bytes | None = None
        self.last_activity: float = 0.0
        self._load_persisted()

    # ------------------------------------------------------------------ #
    #  Login helpers                                                       #
    # ------------------------------------------------------------------ #

    def set_user(self, firebase_response: dict) -> None:
        """Populate session from a Firebase Auth REST response."""
        self.user_id = firebase_response.get("localId")
        self.id_token = firebase_response.get("idToken")
        self.refresh_token = firebase_response.get("refreshToken")
        self.email = firebase_response.get("email")
        self.display_name = firebase_response.get("displayName", self.email)
        self.vault_key = None
        self._persist()

    def clear(self) -> None:
        """Log out – clear all session data."""
        self.user_id = None
        self.id_token = None
        self.refresh_token = None
        self.email = None
        self.display_name = None
        self.vault_key = None
        self.last_activity = 0.0
        if _SESSION_FILE.exists():
            _SESSION_FILE.unlink()

    # ------------------------------------------------------------------ #
    #  Vault lock / unlock                                                 #
    # ------------------------------------------------------------------ #

    def unlock_vault(self, key: bytes) -> None:
        self.vault_key = key
        self.touch()

    def lock_vault(self) -> None:
        self.vault_key = None

    @property
    def vault_unlocked(self) -> bool:
        return self.vault_key is not None

    def touch(self) -> None:
        """Record that the user just interacted with the vault."""
        self.last_activity = time.time()

    def is_timed_out(self) -> bool:
        """Return True if vault should be locked due to inactivity."""
        if not self.vault_unlocked:
            return False
        return (time.time() - self.last_activity) >= INACTIVITY_TIMEOUT

    # ------------------------------------------------------------------ #
    #  Auth state                                                          #
    # ------------------------------------------------------------------ #

    @property
    def is_logged_in(self) -> bool:
        return self.user_id is not None and self.id_token is not None

    # ------------------------------------------------------------------ #
    #  Persistence (non-secret fields only)                               #
    # ------------------------------------------------------------------ #

    def _persist(self) -> None:
        data = {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "refresh_token": self.refresh_token,
        }
        try:
            _SESSION_FILE.write_text(json.dumps(data))
        except OSError:
            pass

    def _load_persisted(self) -> None:
        if not _SESSION_FILE.exists():
            return
        try:
            data = json.loads(_SESSION_FILE.read_text())
            self.user_id = data.get("user_id")
            self.email = data.get("email")
            self.display_name = data.get("display_name")
            self.refresh_token = data.get("refresh_token")
            # id_token is not persisted – will need refresh
        except Exception:
            pass

    def update_id_token(self, new_token: str) -> None:
        """Update the short-lived ID token (after refresh)."""
        self.id_token = new_token


# Singleton instance
session = SessionManager()
