from __future__ import annotations

import subprocess
from pathlib import Path

from .paths import DATA_DIR, LOCK_FILE

DROP_IN_DIR = Path("/etc/systemd/system/focusguard.service.d")
DROP_IN_FILE = DROP_IN_DIR / "lock.conf"


def set_immutable(path: Path, enable: bool) -> None:
    if not path.exists():
        return
    flag = "+i" if enable else "-i"
    try:
        subprocess.run(["chattr", flag, str(path)], check=False, capture_output=True)
    except FileNotFoundError:
        pass


def protect_lock_files(enable: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    set_immutable(LOCK_FILE, enable)
    set_immutable(DATA_DIR / "hosts.backup", enable)


def write_refuse_manual_stop() -> None:
    DROP_IN_DIR.mkdir(parents=True, exist_ok=True)
    DROP_IN_FILE.write_text(
        "[Unit]\n"
        "# FocusGuard lock active — manual stop refused until unlock timer fires.\n"
        "\n"
        "[Service]\n"
        "RefuseManualStop=yes\n",
        encoding="utf-8",
    )
    subprocess.run(["systemctl", "daemon-reload"], check=False, capture_output=True)


def clear_refuse_manual_stop() -> None:
    if DROP_IN_FILE.exists():
        set_immutable(DROP_IN_FILE, False)
        DROP_IN_FILE.unlink()
    subprocess.run(["systemctl", "daemon-reload"], check=False, capture_output=True)


def schedule_unlock_timer(ends_at_epoch: float) -> None:
    """Create a systemd oneshot timer that unlocks shortly after ends_at."""
    from datetime import datetime, timezone

    # +45s buffer so daemon primary unlock wins; timer is backup
    fire_at = ends_at_epoch + 45
    when = datetime.fromtimestamp(ends_at_epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    timer = Path("/etc/systemd/system/focusguard-unlock.timer")
    service = Path("/etc/systemd/system/focusguard-unlock.service")

    share = "/usr/local/share/focusguard"
    service.write_text(
        "[Unit]\n"
        "Description=FocusGuard unlock after lock period\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"Environment=FOCUSGUARD_CONFIG={share}/config\n"
        f"Environment=FOCUSGUARD_DATA=/var/lib/focusguard\n"
        f"Environment=PYTHONPATH={share}\n"
        "ExecStart=/usr/bin/python3 -m focusguard.expire\n",
        encoding="utf-8",
    )
    timer.write_text(
        "[Unit]\n"
        "Description=FocusGuard unlock timer\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={_systemd_oncalendar(fire_at)}\n"
        "Persistent=true\n"
        "Unit=focusguard-unlock.service\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n",
        encoding="utf-8",
    )
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "enable", "--now", "focusguard-unlock.timer"], check=False)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "unlock_at.txt").write_text(when + "\n", encoding="utf-8")


def _systemd_oncalendar(epoch: float) -> str:
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    # systemd OnCalendar: YYYY-MM-DD HH:MM:SS UTC
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def remove_unlock_timer() -> None:
    subprocess.run(["systemctl", "disable", "--now", "focusguard-unlock.timer"], check=False, capture_output=True)
    for p in (
        Path("/etc/systemd/system/focusguard-unlock.timer"),
        Path("/etc/systemd/system/focusguard-unlock.service"),
    ):
        if p.exists():
            p.unlink()
    subprocess.run(["systemctl", "daemon-reload"], check=False, capture_output=True)
