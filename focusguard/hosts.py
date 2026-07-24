from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from .paths import (
    HOSTS_MARKER_BEGIN,
    HOSTS_MARKER_END,
    HOSTS_PATH,
    SINKHOLE_IP,
    domains_config,
)

BACKUP_PATH = Path("/var/lib/focusguard/hosts.backup")


def _immutable(path: Path, enable: bool) -> None:
    if not path.exists():
        return
    flag = "+i" if enable else "-i"
    try:
        subprocess.run(["chattr", flag, str(path)], check=False, capture_output=True)
    except FileNotFoundError:
        pass


def _strip_focusguard_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if HOSTS_MARKER_BEGIN in line:
            skipping = True
            continue
        if HOSTS_MARKER_END in line:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "".join(out)


def _build_block(domains: list[str]) -> str:
    unique = sorted({d.strip().lower() for d in domains if d and d.strip()})
    rows = [f"{SINKHOLE_IP} {d}" for d in unique]
    # also www-less / with-www variants already listed in config; keep as given
    body = "\n".join(rows)
    return f"{HOSTS_MARKER_BEGIN}\n{body}\n{HOSTS_MARKER_END}\n"


def apply_hosts() -> None:
    domains = list(domains_config().get("blocked_domains") or [])
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not BACKUP_PATH.exists() and HOSTS_PATH.exists():
        shutil.copy2(HOSTS_PATH, BACKUP_PATH)

    _immutable(HOSTS_PATH, False)
    current = HOSTS_PATH.read_text(encoding="utf-8") if HOSTS_PATH.exists() else ""
    cleaned = _strip_focusguard_block(current)
    if cleaned and not cleaned.endswith("\n"):
        cleaned += "\n"
    new_text = cleaned + "\n" + _build_block(domains)
    HOSTS_PATH.write_text(new_text, encoding="utf-8")
    _immutable(HOSTS_PATH, True)


def remove_hosts() -> None:
    if not HOSTS_PATH.exists():
        return
    _immutable(HOSTS_PATH, False)
    current = HOSTS_PATH.read_text(encoding="utf-8")
    cleaned = _strip_focusguard_block(current)
    HOSTS_PATH.write_text(cleaned, encoding="utf-8")


def hosts_intact() -> bool:
    if not HOSTS_PATH.exists():
        return False
    text = HOSTS_PATH.read_text(encoding="utf-8")
    return HOSTS_MARKER_BEGIN in text and HOSTS_MARKER_END in text


def ensure_hosts(last_apply: float, interval: float) -> float:
    now = time.time()
    if now - last_apply >= interval or not hosts_intact():
        apply_hosts()
        return now
    return last_apply
