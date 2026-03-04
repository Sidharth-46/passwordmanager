"""
Google OAuth Service
Implements the OAuth 2.0 Installed Application flow for desktop apps.

Why this works reliably on Windows
-----------------------------------
``InstalledAppFlow.run_local_server()`` calls ``webbrowser.open()``
internally.  On Windows, ``webbrowser.open()`` fails silently from a
background thread.

Fix: immediately before calling ``run_local_server()``, we replace
``webbrowser.open`` with our own subprocess-based launcher, then restore
it in a ``finally`` block.  This means:

* There is **one** call to ``flow.authorization_url()`` (made inside
  ``run_local_server``), so only one OAuth state is generated — fixing
  the ``MismatchingStateError: CSRF Warning!`` that occurs when
  ``authorization_url()`` is called a second time manually.
* The browser is opened via ``subprocess.Popen`` which is thread-safe
  on every OS and always works from a background thread on Windows.
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import subprocess
import webbrowser

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# Path to the OAuth 2.0 client secrets file downloaded from Google Cloud Console.
# Must be a "Desktop app" credential (not "Web application").
CLIENT_SECRET_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "client_secret.json",
)

# OAuth scopes – 'openid' is mandatory to receive an id_token JWT
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class GoogleAuthError(Exception):
    """Raised when the Google OAuth flow fails."""


# --------------------------------------------------------------------------- #
#  Internal helpers                                                             #
# --------------------------------------------------------------------------- #

def _open_browser(url: str) -> None:
    """Open *url* using the OS shell command.

    Uses ``subprocess.Popen`` — thread-safe on every OS.  Works from a
    background thread on Windows where ``webbrowser.open`` fails silently.
    """
    system = platform.system()
    print(f"[DEBUG] _open_browser: OS={system}", flush=True)
    print(f"[DEBUG] _open_browser: url={url[:80]}...", flush=True)
    log.debug("_open_browser: OS=%s url=%s", system, url)
    try:
        if system == "Windows":
            subprocess.Popen(f'start "" "{url}"', shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
        print("[DEBUG] _open_browser: subprocess dispatched", flush=True)
        log.debug("_open_browser: browser subprocess dispatched")
    except Exception as exc:
        print(f"[DEBUG] _open_browser: FAILED – {exc}", flush=True)
        log.warning("_open_browser: failed to launch browser: %s", exc)


def _reserve_free_port() -> int:
    """Ask the OS for a free TCP port and immediately release it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log.debug("_reserve_free_port: using port %d", port)
    return port


# --------------------------------------------------------------------------- #
#  Public API                                                                   #
# --------------------------------------------------------------------------- #

def get_google_id_token() -> str:
    """Run the Google OAuth 2.0 Installed Application flow.

    ``run_local_server()`` is the single point that generates the
    authorization URL and the CSRF state token.  We patch ``webbrowser.open``
    just before calling it so the browser is opened via subprocess (reliable
    from any thread on Windows), then restore the original immediately after.

    Returns
    -------
    str
        The Google ID token (a signed JWT) for Firebase's ``signInWithIdp``.

    Raises
    ------
    GoogleAuthError
        If ``client_secret.json`` is missing, the user cancels, or no
        id_token is returned by Google.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GoogleAuthError(
            "google-auth-oauthlib is not installed.\n"
            "Run:  pip install \"google-auth-oauthlib>=1.2.0\""
        ) from exc

    # ── 1. Verify client_secret.json ─────────────────────────────────────
    print(f"[DEBUG] get_google_id_token: looking for client_secret.json at {CLIENT_SECRET_FILE}", flush=True)
    log.debug("get_google_id_token: looking for client_secret.json at %s", CLIENT_SECRET_FILE)
    if not os.path.isfile(CLIENT_SECRET_FILE):
        raise GoogleAuthError(
            f"client_secret.json not found at:\n  {CLIENT_SECRET_FILE}\n\n"
            "Download it from Google Cloud Console:\n"
            "  APIs & Services → Credentials → your Desktop app OAuth client "
            "→ Download JSON\n"
            "Rename the file to client_secret.json and place it in the project root."
        )
    print("[DEBUG] get_google_id_token: client_secret.json found", flush=True)
    log.debug("get_google_id_token: client_secret.json found")

    # ── 2. Build the flow ─────────────────────────────────────────────────
    print("[DEBUG] get_google_id_token: building InstalledAppFlow", flush=True)
    log.debug("get_google_id_token: building InstalledAppFlow from client_secret.json")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes=SCOPES)

    # ── 3. Reserve a free port ────────────────────────────────────────────
    port = _reserve_free_port()
    print(f"[DEBUG] get_google_id_token: reserved port {port}", flush=True)
    log.debug("get_google_id_token: reserved port %d", port)

    # ── 4. Patch webbrowser.open with our subprocess launcher ─────────────
    # IMPORTANT: do NOT call flow.authorization_url() here.
    # run_local_server() calls it internally — that is the single place
    # where the OAuth state is generated.  Calling authorization_url()
    # a second time would generate a new state, causing:
    #   MismatchingStateError: CSRF Warning! State not equal in request and response.
    _real_webbrowser_open = webbrowser.open

    def _subprocess_browser_open(url: str, new: int = 0, autoraise: bool = True) -> bool:
        """Drop-in replacement for webbrowser.open that uses subprocess."""
        _open_browser(url)
        return True

    webbrowser.open = _subprocess_browser_open  # type: ignore[assignment]
    print("[DEBUG] get_google_id_token: webbrowser.open patched with subprocess launcher", flush=True)
    log.debug("get_google_id_token: webbrowser.open patched")

    # ── 5. Run the full OAuth flow (generates URL, opens browser, waits) ──
    print(f"[DEBUG] get_google_id_token: starting callback server on port {port}", flush=True)
    log.debug("get_google_id_token: calling run_local_server(port=%d, open_browser=True)", port)
    try:
        credentials = flow.run_local_server(
            port=port,
            open_browser=True,  # triggers our patched webbrowser.open above
            prompt="select_account",
            success_message=(
                "Google sign-in successful! "
                "You may close this tab and return to VaultKey."
            ),
        )
        print("[DEBUG] get_google_id_token: OAuth callback received – credentials obtained", flush=True)
        log.debug("get_google_id_token: OAuth callback received")
    except Exception as exc:
        log.error("get_google_id_token: OAuth flow failed: %s", exc, exc_info=True)
        raise GoogleAuthError(f"Google OAuth flow failed: {exc}") from exc
    finally:
        webbrowser.open = _real_webbrowser_open  # always restore
        log.debug("get_google_id_token: webbrowser.open restored")

    # ── 6. Extract the ID token ───────────────────────────────────────────
    id_token: str | None = credentials.id_token
    print(f"[DEBUG] get_google_id_token: id_token present={bool(id_token)}", flush=True)
    log.debug("get_google_id_token: id_token present=%s", bool(id_token))

    if not id_token:
        raise GoogleAuthError(
            "Google returned credentials but no id_token.\n"
            "Ensure 'openid' is in SCOPES and your OAuth client is of type "
            "\"Desktop app\" in Google Cloud Console."
        )

    log.debug("get_google_id_token: returning id_token successfully")
    return id_token
