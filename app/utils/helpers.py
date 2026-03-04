"""
General utilities: password generation, strength scoring, clipboard helpers.
"""

import random
import re
import string
import secrets


# --------------------------------------------------------------------------- #
#  Password Generator                                                          #
# --------------------------------------------------------------------------- #

UPPERCASE = string.ascii_uppercase
LOWERCASE = string.ascii_lowercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?"


def generate_password(
    length: int = 16,
    use_upper: bool = True,
    use_lower: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
) -> str:
    """Generate a cryptographically random password."""
    charset = ""
    required: list[str] = []

    if use_upper:
        charset += UPPERCASE
        required.append(secrets.choice(UPPERCASE))
    if use_lower:
        charset += LOWERCASE
        required.append(secrets.choice(LOWERCASE))
    if use_digits:
        charset += DIGITS
        required.append(secrets.choice(DIGITS))
    if use_symbols:
        charset += SYMBOLS
        required.append(secrets.choice(SYMBOLS))

    if not charset:
        charset = LOWERCASE
        required = [secrets.choice(LOWERCASE)]

    # Fill remaining length with random chars
    remaining = [secrets.choice(charset) for _ in range(max(0, length - len(required)))]
    password_chars = required + remaining
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


# --------------------------------------------------------------------------- #
#  Password Strength                                                           #
# --------------------------------------------------------------------------- #

def password_strength(password: str) -> tuple[int, str]:
    """
    Score password strength on a 0-4 scale.

    Returns
    -------
    score : int
        0 = very weak, 1 = weak, 2 = fair, 3 = strong, 4 = very strong
    label : str
        Human-readable label.
    """
    if not password:
        return 0, "Very Weak"

    score = 0

    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[A-Z]", password) and re.search(r"[a-z]", password):
        score += 1
    if re.search(r"\d", password):
        score += 1
    if re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]", password):
        score += 1

    score = min(score, 4)

    labels = {0: "Very Weak", 1: "Weak", 2: "Fair", 3: "Strong", 4: "Very Strong"}
    return score, labels[score]


STRENGTH_COLORS = {
    0: "#e74c3c",  # red
    1: "#e67e22",  # orange
    2: "#f1c40f",  # yellow
    3: "#2ecc71",  # green
    4: "#27ae60",  # dark green
}


# --------------------------------------------------------------------------- #
#  Validation helpers                                                          #
# --------------------------------------------------------------------------- #

def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def is_valid_pin(pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 6


def is_valid_url(url: str) -> bool:
    if not url:
        return True  # URL is optional
    return url.startswith("http://") or url.startswith("https://")
