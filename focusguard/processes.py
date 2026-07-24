from __future__ import annotations

import os
import re
import signal
import time
from pathlib import Path

from .paths import apps_config


def _cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (FileNotFoundError, PermissionError):
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()


def _comm(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError):
        return ""


def _is_allowed(name: str, cmdline: str, allowed: list[str]) -> bool:
    hay = f"{name} {cmdline}".lower()
    for a in allowed:
        a = a.lower().strip()
        if a and a in hay:
            return True
    return False


def _matches_exact_name(name: str, exact: list[str]) -> bool:
    n = name.lower().strip()
    for e in exact:
        if n == e.lower().strip():
            return True
    return False


def _matches_pattern(name: str, cmdline: str, patterns: list[str]) -> bool:
    name_l = name.lower()
    cmd_l = cmdline.lower()
    for pat in patterns:
        p = pat.lower().strip()
        if not p:
            continue
        # Prefer process-name hits; also match path segments for app binaries
        if name_l == p or name_l.startswith(p + ".") or name_l.startswith(p + "-"):
            return True
        # Binary path: .../cursor, .../Discord, Cursor.AppImage
        if re.search(rf"(^|/)({re.escape(p)})([.\s-]|$)", cmd_l):
            return True
        # Longer names can safely match as substring in name/cmdline
        if len(p) >= 5 and (p in name_l or p in cmd_l):
            return True
    return False


def iter_blocked_pids() -> list[tuple[int, str]]:
    cfg = apps_config()
    patterns = list(cfg.get("blocked_processes") or [])
    exact = list(cfg.get("blocked_process_names_exact") or [])
    allowed = list(cfg.get("allowed_processes") or [])
    if not patterns and not exact:
        return []

    self_pid = os.getpid()
    found: list[tuple[int, str]] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == self_pid:
            continue
        name = _comm(pid)
        cmd = _cmdline(pid)
        if _is_allowed(name, cmd, allowed):
            continue
        if _matches_exact_name(name, exact) or _matches_pattern(name, cmd, patterns):
            found.append((pid, name or cmd[:40]))
    return found


def _kill_pid(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        try:
            os.kill(pid, signal.SIGKILL)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    time.sleep(0.35)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def kill_pids(pids: list[tuple[int, str]], cooldown: dict[int, float], cooldown_sec: float = 3.0) -> list[str]:
    killed: list[str] = []
    now = time.time()
    for pid, name in pids:
        last = cooldown.get(pid, 0.0)
        if now - last < cooldown_sec:
            continue
        if _kill_pid(pid):
            cooldown[pid] = now
            killed.append(name)
    for pid in list(cooldown):
        if now - cooldown[pid] > 60:
            cooldown.pop(pid, None)
    return killed


def kill_blocked(cooldown: dict[int, float], cooldown_sec: float = 3.0) -> list[str]:
    return kill_pids(iter_blocked_pids(), cooldown, cooldown_sec=cooldown_sec)
