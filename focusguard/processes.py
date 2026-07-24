from __future__ import annotations

import os
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


def _argv0(cmdline: str) -> str:
    if not cmdline:
        return ""
    return cmdline.split(None, 1)[0]


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1].lower()


def _is_allowed(name: str, argv0: str, allowed: list[str]) -> bool:
    """Allowlist only checks process name / executable — not full argv."""
    hay = f"{name} {argv0}".lower()
    for a in allowed:
        a = a.lower().strip()
        if a and a in hay:
            return True
    return False


def _matches_exact_name(name: str, exact: list[str]) -> bool:
    n = name.lower().strip()
    return any(n == e.lower().strip() for e in exact if e)


def _matches_pattern(name: str, cmdline: str, patterns: list[str]) -> bool:
    """Strict match: process name or executable basename/path only.

    Never scan the full cmdline — that false-positives on flags like
    --num-raster-threads and Cursor shellIntegration paths.
    """
    name_l = name.lower()
    argv0 = _argv0(cmdline)
    base = _basename(argv0)
    argv0_l = argv0.lower()

    for pat in patterns:
        p = pat.lower().strip()
        if not p:
            continue

        # process name (comm)
        if name_l == p or name_l.startswith(p + "-") or name_l.startswith(p + "."):
            return True

        # executable basename: discord, Cursor-3.12.17-x86_64.AppImage, steam
        if (
            base == p
            or base.startswith(p + "-")
            or base.startswith(p + ".")
            or base.startswith(p + "_")
        ):
            return True

        # path segment for the binary itself / its app dir:
        # .../cursor/cursor, .../Discord/Discord, .../cursor/chrome_crashpad_handler
        # only inspect argv0 — never later arguments (avoids --num-raster-threads etc.)
        parts = [seg for seg in argv0_l.split("/") if seg]
        if parts:
            if parts[-1] == p:
                return True
            # binary living inside an app folder named like the pattern
            if len(parts) >= 2 and parts[-2] == p:
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
        argv0 = _argv0(cmd)
        if _is_allowed(name, argv0, allowed):
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
