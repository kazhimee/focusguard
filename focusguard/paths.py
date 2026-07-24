from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.environ.get("FOCUSGUARD_CONFIG", ROOT / "config"))
DATA_DIR = Path(os.environ.get("FOCUSGUARD_DATA", "/var/lib/focusguard"))
LOCK_FILE = DATA_DIR / "lock.json"
HOSTS_MARKER_BEGIN = "# BEGIN FOCUSGUARD"
HOSTS_MARKER_END = "# END FOCUSGUARD"
HOSTS_PATH = Path("/etc/hosts")
SINKHOLE_IP = "127.0.0.1"


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def settings() -> dict:
    return load_yaml("settings.yaml")


def domains_config() -> dict:
    return load_yaml("domains.yaml")


def apps_config() -> dict:
    return load_yaml("apps.yaml")

