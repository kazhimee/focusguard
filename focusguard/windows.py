from __future__ import annotations

import shutil
import subprocess

from .paths import domains_config


def _run(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=5)
        return out.stdout or ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def list_windows() -> list[tuple[str, str, str]]:
    """Return list of (window_id, title, class_name)."""
    windows: list[tuple[str, str, str]] = []

    if shutil.which("hyprctl"):
        out = _run(["hyprctl", "clients", "-j"])
        try:
            import json

            clients = json.loads(out or "[]")
            for c in clients:
                wid = str(c.get("address") or "")
                title = str(c.get("title") or "")
                cls = str(c.get("class") or c.get("initialClass") or "")
                if wid:
                    windows.append((wid, title, cls))
        except Exception:
            pass
        if windows:
            return windows

    if shutil.which("wmctrl"):
        out = _run(["wmctrl", "-lx"])
        for line in out.splitlines():
            # id desktop class host title
            parts = line.split(None, 4)
            if len(parts) >= 5:
                windows.append((parts[0], parts[4], parts[2]))
            elif len(parts) >= 3:
                windows.append((parts[0], parts[-1], parts[2] if len(parts) > 2 else ""))
        return windows

    return windows


def close_window(window_id: str) -> None:
    if shutil.which("hyprctl") and window_id:
        subprocess.run(
            ["hyprctl", "dispatch", "closewindow", f"address:{window_id}"],
            check=False,
            capture_output=True,
        )
        return
    if shutil.which("wmctrl") and window_id.startswith("0x"):
        subprocess.run(["wmctrl", "-i", "-c", window_id], check=False, capture_output=True)


def _is_allowed(title: str, cls: str, allowed_kw: list[str], allowed_cls: list[str]) -> bool:
    t = title.lower()
    c = cls.lower()
    if any(a in t for a in allowed_kw if a):
        return True
    if any(a.lower() in c or c == a.lower() for a in allowed_cls if a):
        return True
    if "music.apple" in t or "music.apple" in c:
        return True
    if "apple music" in t:
        return True
    return False


def _keyword_hit(blob: str, keyword: str) -> bool:
    """Prefer whole-word style hits to avoid flag/title false positives."""
    k = keyword.lower().strip()
    if not k:
        return False
    if len(k) <= 6:
        # word-ish boundaries
        import re

        return re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", blob) is not None
    return k in blob


def list_blocked_windows() -> list[tuple[str, str]]:
    cfg = domains_config()
    blocked = [k.lower() for k in (cfg.get("blocked_window_keywords") or [])]
    allowed = [k.lower() for k in (cfg.get("allowed_window_keywords") or [])]
    allowed_cls = list(cfg.get("allowed_window_classes") or [])
    found: list[tuple[str, str]] = []

    for wid, title, cls in list_windows():
        if _is_allowed(title, cls, allowed, allowed_cls):
            continue
        blob = f"{title} {cls}".lower()
        if any(_keyword_hit(blob, b) for b in blocked):
            found.append((wid, title or cls))
    return found


def close_windows(targets: list[tuple[str, str]]) -> list[str]:
    closed: list[str] = []
    for wid, title in targets:
        close_window(wid)
        closed.append(title)
    return closed


def scan_and_close() -> list[str]:
    return close_windows(list_blocked_windows())
