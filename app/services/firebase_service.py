"""
Firebase Service
Handles Firebase Authentication (REST) and Cloud Firestore (REST).
No Admin SDK required – runs purely from the client side using API keys.

Google sign-in uses google-auth-oauthlib's InstalledAppFlow (see
google_auth_service.py) and then authenticates with Firebase via
signInWithIdp.
"""

import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Config (read from .env)                                                     #
# --------------------------------------------------------------------------- #

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

FIREBASE_AUTH_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"
FIRESTORE_BASE = (
    f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}"
    "/databases/(default)/documents"
)


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _raise_for(response: requests.Response) -> None:
    """Raise a human-readable error from a Firebase error response."""
    try:
        msg = response.json().get("error", {}).get("message", response.text)
    except Exception:
        msg = response.text
    raise FirebaseError(msg)


class FirebaseError(Exception):
    """Wrapper for Firebase / Firestore error responses."""


# --------------------------------------------------------------------------- #
#  Firestore value helpers                                                      #
# --------------------------------------------------------------------------- #

def _to_fs_value(python_val) -> dict:
    """Convert a Python scalar to a Firestore REST value dict."""
    if python_val is None:
        return {"nullValue": None}
    if isinstance(python_val, bool):
        return {"booleanValue": python_val}
    if isinstance(python_val, int):
        return {"integerValue": str(python_val)}
    if isinstance(python_val, float):
        return {"doubleValue": python_val}
    return {"stringValue": str(python_val)}


def _from_fs_value(val: dict):
    """Convert a Firestore REST value dict to a Python scalar."""
    if "stringValue" in val:
        return val["stringValue"]
    if "integerValue" in val:
        return int(val["integerValue"])
    if "doubleValue" in val:
        return float(val["doubleValue"])
    if "booleanValue" in val:
        return val["booleanValue"]
    if "nullValue" in val:
        return None
    return str(val)


def _dict_to_fs_fields(d: dict) -> dict:
    return {"fields": {k: _to_fs_value(v) for k, v in d.items()}}


def _fs_fields_to_dict(doc: dict) -> dict:
    return {k: _from_fs_value(v) for k, v in doc.get("fields", {}).items()}


# --------------------------------------------------------------------------- #
#  FirebaseService                                                              #
# --------------------------------------------------------------------------- #

class FirebaseService:
    """All Firebase / Firestore interactions go through this class."""

    # ------------------------------------------------------------------ #
    #  Authentication                                                      #
    # ------------------------------------------------------------------ #

    def register(self, email: str, password: str) -> dict:
        """Create a new user with email + password. Returns user info dict."""
        url = f"{FIREBASE_AUTH_BASE}:signUp?key={FIREBASE_API_KEY}"
        resp = requests.post(
            url,
            json={"email": email, "password": password, "returnSecureToken": True},
        )
        if not resp.ok:
            _raise_for(resp)
        return resp.json()

    def login(self, email: str, password: str) -> dict:
        """Sign in with email + password. Returns user info dict."""
        url = f"{FIREBASE_AUTH_BASE}:signInWithPassword?key={FIREBASE_API_KEY}"
        resp = requests.post(
            url,
            json={"email": email, "password": password, "returnSecureToken": True},
        )
        if not resp.ok:
            _raise_for(resp)
        return resp.json()

    def login_with_google(self) -> dict:
        """
        Authenticate the user with Google using the OAuth 2.0 Installed
        Application flow, then sign into Firebase.

        Flow
        ----
        1. ``google_auth_service.get_google_id_token()`` opens the browser,
           handles the localhost callback, and returns a signed Google ID token.
        2. We POST that token to Firebase ``signInWithIdp``.
        3. Firebase returns idToken / refreshToken / localId (userId).

        Returns
        -------
        dict
            Firebase Auth response containing ``idToken``, ``refreshToken``,
            ``localId``, ``email``, and ``displayName``.

        Raises
        ------
        FirebaseError
            On any OAuth or Firebase failure.
        """
        from app.services.google_auth_service import get_google_id_token, GoogleAuthError

        if not FIREBASE_API_KEY:
            raise FirebaseError("FIREBASE_API_KEY is not set in .env")

        # ── Step 1: Run Google OAuth flow ─────────────────────────────────
        log.debug("login_with_google: starting Google OAuth flow")
        try:
            google_id_token = get_google_id_token()
        except GoogleAuthError as exc:
            raise FirebaseError(str(exc)) from exc

        # ── Step 2: Sign in to Firebase with Google ID token ──────────────
        log.debug("login_with_google: exchanging Google ID token with Firebase")
        fb_url = f"{FIREBASE_AUTH_BASE}:signInWithIdp?key={FIREBASE_API_KEY}"
        payload = {
            "postBody": f"id_token={google_id_token}&providerId=google.com",
            # requestUri must be "http://localhost" for installed-app flows
            "requestUri": "http://localhost",
            "returnSecureToken": True,
            "returnIdpCredential": True,
        }

        try:
            fb_resp = requests.post(fb_url, json=payload, timeout=20)
        except requests.RequestException as exc:
            raise FirebaseError(f"Network error contacting Firebase: {exc}") from exc

        if not fb_resp.ok:
            _raise_for(fb_resp)

        result = fb_resp.json()
        log.debug(
            "login_with_google: Firebase sign-in succeeded for %s",
            result.get("email", "<unknown>"),
        )
        return result

    # Keep the old name as an alias for backwards compatibility
    def login_google(self) -> dict:
        return self.login_with_google()

    def send_password_reset(self, email: str) -> None:
        """Send a Firebase password-reset email."""
        url = f"{FIREBASE_AUTH_BASE}:sendOobCode?key={FIREBASE_API_KEY}"
        resp = requests.post(url, json={"requestType": "PASSWORD_RESET", "email": email})
        if not resp.ok:
            _raise_for(resp)

    def refresh_token(self, refresh_token: str) -> dict:
        """Exchange a refresh token for a new ID token."""
        url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
        resp = requests.post(
            url,
            json={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        if not resp.ok:
            _raise_for(resp)
        return resp.json()

    # ------------------------------------------------------------------ #
    #  Firestore – user document                                           #
    # ------------------------------------------------------------------ #

    def _headers(self, id_token: str) -> dict:
        return {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}

    def _user_doc_url(self, user_id: str) -> str:
        return f"{FIRESTORE_BASE}/users/{user_id}"

    def _vault_col_url(self, user_id: str) -> str:
        return f"{FIRESTORE_BASE}/users/{user_id}/vault"

    def _vault_doc_url(self, user_id: str, entry_id: str) -> str:
        return f"{self._vault_col_url(user_id)}/{entry_id}"

    # ------------------------------------------------------------------ #
    #  Master PIN                                                          #
    # ------------------------------------------------------------------ #

    def get_master_pin_hash(self, user_id: str, id_token: str) -> str | None:
        """Return the stored bcrypt PIN hash, or None if not set."""
        resp = requests.get(
            self._user_doc_url(user_id), headers=self._headers(id_token)
        )
        if resp.status_code == 404:
            return None
        if not resp.ok:
            _raise_for(resp)
        data = _fs_fields_to_dict(resp.json())
        return data.get("masterPinHash")

    def set_master_pin_hash(self, user_id: str, id_token: str, pin_hash: str) -> None:
        """Create or update the masterPinHash field on the user document."""
        url = f"{self._user_doc_url(user_id)}?updateMask.fieldPaths=masterPinHash"
        body = _dict_to_fs_fields({"masterPinHash": pin_hash})
        resp = requests.patch(url, headers=self._headers(id_token), json=body)
        if not resp.ok:
            _raise_for(resp)

    # ------------------------------------------------------------------ #
    #  Vault CRUD                                                          #
    # ------------------------------------------------------------------ #

    def get_vault_entries(self, user_id: str, id_token: str) -> list[dict]:
        """Fetch all vault entries. Returns a list of dicts (with 'id' key)."""
        resp = requests.get(
            self._vault_col_url(user_id), headers=self._headers(id_token)
        )
        if resp.status_code == 404:
            return []
        if not resp.ok:
            _raise_for(resp)
        documents = resp.json().get("documents", [])
        entries = []
        for doc in documents:
            entry = _fs_fields_to_dict(doc)
            # Extract document ID from the 'name' path
            entry["id"] = doc["name"].split("/")[-1]
            entries.append(entry)
        return entries

    def add_vault_entry(self, user_id: str, id_token: str, entry: dict) -> str:
        """Add a new vault entry (auto-ID). Returns the new document ID."""
        resp = requests.post(
            self._vault_col_url(user_id),
            headers=self._headers(id_token),
            json=_dict_to_fs_fields(entry),
        )
        if not resp.ok:
            _raise_for(resp)
        return resp.json()["name"].split("/")[-1]

    def update_vault_entry(
        self, user_id: str, id_token: str, entry_id: str, entry: dict
    ) -> None:
        """Overwrite all fields of a vault entry."""
        fields = list(entry.keys())
        mask = "&".join(f"updateMask.fieldPaths={f}" for f in fields)
        url = f"{self._vault_doc_url(user_id, entry_id)}?{mask}"
        resp = requests.patch(
            url,
            headers=self._headers(id_token),
            json=_dict_to_fs_fields(entry),
        )
        if not resp.ok:
            _raise_for(resp)

    def delete_vault_entry(self, user_id: str, id_token: str, entry_id: str) -> None:
        """Delete a vault entry by document ID."""
        resp = requests.delete(
            self._vault_doc_url(user_id, entry_id),
            headers=self._headers(id_token),
        )
        if not resp.ok:
            _raise_for(resp)


# Singleton instance
firebase_service = FirebaseService()
