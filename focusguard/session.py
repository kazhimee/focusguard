from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .paths import DATA_DIR, LOCK_FILE, settings


@dataclass
class LockSession:
    started_at: float
    ends_at: float
    lock_days: int

    @property
    def active(self) -> bool:
        return time.time() < self.ends_at

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.ends_at - time.time())

    def remaining_human(self) -> str:
        secs = int(self.remaining_seconds)
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours or days:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "ends_at": self.ends_at,
            "lock_days": self.lock_days,
            "started_iso": datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat(),
            "ends_iso": datetime.fromtimestamp(self.ends_at, tz=timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LockSession":
        return cls(
            started_at=float(data["started_at"]),
            ends_at=float(data["ends_at"]),
            lock_days=int(data.get("lock_days", 30)),
        )


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_session() -> LockSession | None:
    if not LOCK_FILE.exists():
        return None
    with LOCK_FILE.open(encoding="utf-8") as f:
        return LockSession.from_dict(json.load(f))


def create_session(lock_days: int | None = None) -> LockSession:
    ensure_data_dir()
    days = lock_days if lock_days is not None else int(settings().get("lock_days", 30))
    now = time.time()
    session = LockSession(
        started_at=now,
        ends_at=now + timedelta(days=days).total_seconds(),
        lock_days=days,
    )
    _write_lock(session)
    return session


def _write_lock(session: LockSession) -> None:
    ensure_data_dir()
    tmp = LOCK_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, indent=2)
        f.write("\n")
    os.replace(tmp, LOCK_FILE)


def clear_session() -> None:
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


def is_locked() -> bool:
    session = load_session()
    return bool(session and session.active)
