from __future__ import annotations

import re
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

# Valid hostname labels only — paths like bing.com/chat break /etc/hosts parsers.
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]+(\.[a-z0-9-]+)+$"
)

# Never sinkhole these (browsing breaks otherwise).
_NEVER_BLOCK = {
    "localhost",
    "localhost.localdomain",
    "google.com",
    "www.google.com",
    "google.com.tr",
    "www.google.com.tr",
    "googleapis.com",
    "gstatic.com",
    "googleusercontent.com",
    "gvt1.com",
    "gvt2.com",
    "brave.com",
    "www.brave.com",
    "search.brave.com",
    "laptop-updates.brave.com",
    "variations.brave.com",
    "cloudflare.com",
    "www.cloudflare.com",
    "dns.google",
    "one.one.one.one",
}


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


def sanitize_domain(raw: str) -> str | None:
    d = (raw or "").strip().lower()
    if not d or "/" in d or ":" in d or " " in d:
        return None
    # strip accidental scheme
    if d.startswith("http://"):
        d = d[7:]
    if d.startswith("https://"):
        d = d[8:]
    d = d.split("/", 1)[0]
    if d in _NEVER_BLOCK:
        return None
    # Never block bare google / brave search infrastructure
    if d.endswith(".gstatic.com") or d.endswith(".googleapis.com"):
        return None
    if d.endswith(".googleusercontent.com"):
        return None
    if not _HOST_RE.match(d):
        return None
    return d


def _normalize_domains(domains: list[str]) -> list[str]:
    out: set[str] = set()
    for raw in domains:
        d = sanitize_domain(raw)
        if d:
            out.add(d)
    out -= _NEVER_BLOCK
    return sorted(out)


def _build_block(domains: list[str]) -> str:
    unique = _normalize_domains(domains)
    rows = [f"{SINKHOLE_IP} {d}" for d in unique]
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
    # flush resolved cache so bad entries disappear immediately
    subprocess.run(["resolvectl", "flush-caches"], check=False, capture_output=True)


def remove_hosts() -> None:
    if not HOSTS_PATH.exists():
        return
    _immutable(HOSTS_PATH, False)
    current = HOSTS_PATH.read_text(encoding="utf-8")
    cleaned = _strip_focusguard_block(current)
    HOSTS_PATH.write_text(cleaned, encoding="utf-8")
    subprocess.run(["resolvectl", "flush-caches"], check=False, capture_output=True)


def hosts_intact() -> bool:
    if not HOSTS_PATH.exists():
        return False
    text = HOSTS_PATH.read_text(encoding="utf-8")
    if HOSTS_MARKER_BEGIN not in text or HOSTS_MARKER_END not in text:
        return False
    # consider broken if invalid hostnames present inside the block
    block = text.split(HOSTS_MARKER_BEGIN, 1)[1].split(HOSTS_MARKER_END, 1)[0]
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            return False
        if sanitize_domain(parts[1]) is None and parts[1].lower() not in _NEVER_BLOCK:
            # invalid entry inside our block
            return False
    return True


def ensure_hosts(last_apply: float, interval: float) -> float:
    now = time.time()
    if now - last_apply >= interval or not hosts_intact():
        apply_hosts()
        return now
    return last_apply
