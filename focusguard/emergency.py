from __future__ import annotations

import hashlib
import json
import secrets
import string
from pathlib import Path

from .paths import DATA_DIR, settings

CODE_FILE = DATA_DIR / "emergency.code"
STREAK_FILE = DATA_DIR / "emergency.streak"
NEEDED = 10


def _load_settings_code() -> str | None:
    raw = settings().get("emergency_code")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def ensure_emergency_code() -> str:
    """Return the emergency code, creating one if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    configured = _load_settings_code()
    if configured:
        CODE_FILE.write_text(configured + "\n", encoding="utf-8")
        try:
            CODE_FILE.chmod(0o600)
        except OSError:
            pass
        return configured

    if CODE_FILE.exists():
        existing = CODE_FILE.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    alphabet = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    CODE_FILE.write_text(code + "\n", encoding="utf-8")
    try:
        CODE_FILE.chmod(0o600)
    except OSError:
        pass
    return code


def get_emergency_code() -> str | None:
    if CODE_FILE.exists():
        code = CODE_FILE.read_text(encoding="utf-8").strip()
        return code or None
    return _load_settings_code()


def _read_streak() -> dict:
    if not STREAK_FILE.exists():
        return {"count": 0, "last_hash": ""}
    try:
        return json.loads(STREAK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"count": 0, "last_hash": ""}


def _write_streak(count: int, last_hash: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STREAK_FILE.write_text(
        json.dumps({"count": count, "last_hash": last_hash}) + "\n",
        encoding="utf-8",
    )


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def submit_emergency_code(attempt: str) -> tuple[bool, int, str]:
    """Submit one emergency attempt.

    Returns (unlocked, streak, message).
    Wrong code resets streak to 0.
    Correct code increments; at 10 consecutive unlocks.
    """
    expected = get_emergency_code() or ensure_emergency_code()
    got = (attempt or "").strip()
    if not got:
        return False, 0, "Empty code."

    if got != expected:
        _write_streak(0, "")
        return False, 0, "Wrong code. Streak reset to 0/10."

    streak = _read_streak()
    count = int(streak.get("count") or 0) + 1
    _write_streak(count, _hash(got))

    if count >= NEEDED:
        from .expire import force_unlock

        force_unlock()
        _write_streak(0, "")
        return True, count, "Emergency unlock successful. FocusGuard is off."

    left = NEEDED - count
    return False, count, f"Correct ({count}/{NEEDED}). Enter {left} more time(s) in a row."
