"""
Encryption Service
Handles AES-256-GCM encryption/decryption and bcrypt PIN hashing.
"""

import os
import base64
import json
import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class EncryptionService:
    """AES-256-GCM encryption and bcrypt PIN hashing utilities."""

    # ------------------------------------------------------------------ #
    #  Master PIN hashing (bcrypt)                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def hash_pin(pin: str) -> str:
        """Hash a Master PIN with bcrypt and return a UTF-8 string."""
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(pin.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_pin(pin: str, hashed: str) -> bool:
        """Return True if *pin* matches *hashed* bcrypt digest."""
        return bcrypt.checkpw(pin.encode("utf-8"), hashed.encode("utf-8"))

    # ------------------------------------------------------------------ #
    #  Key derivation from PIN (PBKDF2-HMAC-SHA256)                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def derive_key(pin: str, salt: bytes) -> bytes:
        """Derive a 32-byte AES key from the Master PIN + salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        return kdf.derive(pin.encode("utf-8"))

    # ------------------------------------------------------------------ #
    #  AES-256-GCM encryption / decryption                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def encrypt(plaintext: str, key: bytes) -> dict:
        """
        Encrypt *plaintext* with AES-256-GCM.

        Returns a dict::

            {
                "ciphertext": "<base64>",
                "nonce":      "<base64>",   # 12-byte GCM nonce
            }
        """
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return {
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
            "nonce": base64.b64encode(nonce).decode("utf-8"),
        }

    @staticmethod
    def decrypt(encrypted: dict, key: bytes) -> str:
        """
        Decrypt a dict produced by :meth:`encrypt`.

        Raises ``ValueError`` on authentication failure (wrong key / tampered).
        """
        nonce = base64.b64decode(encrypted["nonce"])
        ciphertext = base64.b64decode(encrypted["ciphertext"])
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    # ------------------------------------------------------------------ #
    #  Vault-level encrypt / decrypt helpers (password field only)        #
    # ------------------------------------------------------------------ #

    def encrypt_password(self, password: str, key: bytes) -> str:
        """Return a JSON string representing the encrypted password."""
        return json.dumps(self.encrypt(password, key))

    def decrypt_password(self, encrypted_json: str, key: bytes) -> str:
        """Decrypt a JSON string that was produced by :meth:`encrypt_password`."""
        return self.decrypt(json.loads(encrypted_json), key)

    # ------------------------------------------------------------------ #
    #  Full vault import / export                                          #
    # ------------------------------------------------------------------ #

    def export_vault(self, entries: list[dict], pin: str) -> dict:
        """
        Encrypt an entire list of vault entries for export.

        The returned dict can be serialised to JSON and saved to disk::

            {
                "salt":    "<base64-32-bytes>",
                "entries": [
                    {
                        "site": "...", "username": "...",
                        "url": "...", "notes": "...",
                        "password": "<encrypt_password result>",
                        "id": "..."
                    },
                    ...
                ]
            }
        """
        salt = os.urandom(32)
        key = self.derive_key(pin, salt)

        exported_entries = []
        for entry in entries:
            e = dict(entry)
            # Re-encrypt any already-decrypted password field
            raw_password = e.get("password_plain") or e.get("password", "")
            e["password"] = self.encrypt_password(raw_password, key)
            e.pop("password_plain", None)
            exported_entries.append(e)

        return {
            "salt": base64.b64encode(salt).decode("utf-8"),
            "entries": exported_entries,
        }

    def import_vault(self, data: dict, pin: str) -> list[dict]:
        """
        Decrypt an exported vault dict.

        Returns a list of entry dicts with a ``password_plain`` key.
        Raises ``ValueError`` if decryption fails (wrong PIN).
        """
        salt = base64.b64decode(data["salt"])
        key = self.derive_key(pin, salt)

        entries = []
        for entry in data.get("entries", []):
            e = dict(entry)
            try:
                e["password_plain"] = self.decrypt_password(e["password"], key)
            except Exception as exc:
                raise ValueError("Invalid PIN or corrupted vault data.") from exc
            entries.append(e)
        return entries


# Singleton instance
encryption_service = EncryptionService()
