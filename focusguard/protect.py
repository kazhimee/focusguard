from __future__ import annotations

import subprocess
from pathlib import Path

from .paths import DATA_DIR, LOCK_FILE, ROOT

DROP_IN_DIR = Path("/etc/systemd/system/focusguard.service.d")
DROP_IN_FILE = DROP_IN_DIR / "lock.conf"
WATCHDOG_SERVICE = Path("/etc/systemd/system/focusguard-watchdog.service")
WATCHDOG_TIMER = Path("/etc/systemd/system/focusguard-watchdog.timer")
LIB_DIR = Path("/usr/local/lib/focusguard")


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
    set_immutable(DROP_IN_FILE, False)
    DROP_IN_FILE.write_text(
        "[Service]\n"
        "# FocusGuard lock active — manual stop refused; watchdog restarts if killed.\n"
        "RefuseManualStop=yes\n"
        "Restart=always\n"
        "RestartSec=1\n"
        "TimeoutStopSec=3\n",
        encoding="utf-8",
    )
    set_immutable(DROP_IN_FILE, True)
    _install_watchdog()
    subprocess.run(["systemctl", "daemon-reload"], check=False, capture_output=True)


def clear_refuse_manual_stop() -> None:
    set_immutable(DROP_IN_FILE, False)
    if DROP_IN_FILE.exists():
        DROP_IN_FILE.unlink()
    _remove_watchdog()
    subprocess.run(["systemctl", "daemon-reload"], check=False, capture_output=True)


def _watchdog_script_source() -> Path | None:
    candidates = [
        LIB_DIR / "focusguard-watchdog.sh",
        Path("/usr/local/share/focusguard/install/focusguard-watchdog.sh"),
        ROOT / "install" / "focusguard-watchdog.sh",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _install_watchdog() -> None:
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    src = _watchdog_script_source()
    installed = LIB_DIR / "focusguard-watchdog.sh"
    if src is not None:
        installed.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        installed.chmod(0o755)

    WATCHDOG_SERVICE.write_text(
        "[Unit]\n"
        "Description=FocusGuard watchdog (restart lock daemon if killed)\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "ExecStart=/usr/local/lib/focusguard/focusguard-watchdog.sh\n"
        "Environment=FOCUSGUARD_DATA=/var/lib/focusguard\n",
        encoding="utf-8",
    )
    WATCHDOG_TIMER.write_text(
        "[Unit]\n"
        "Description=FocusGuard watchdog timer\n"
        "\n"
        "[Timer]\n"
        "OnBootSec=15s\n"
        "OnUnitActiveSec=10s\n"
        "AccuracySec=1s\n"
        "Persistent=true\n"
        "Unit=focusguard-watchdog.service\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n",
        encoding="utf-8",
    )
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "enable", "--now", "focusguard-watchdog.timer"], check=False)


def _remove_watchdog() -> None:
    subprocess.run(
        ["systemctl", "disable", "--now", "focusguard-watchdog.timer"],
        check=False,
        capture_output=True,
    )
    for p in (WATCHDOG_TIMER, WATCHDOG_SERVICE):
        if p.exists():
            set_immutable(p, False)
            p.unlink()


def schedule_unlock_timer(ends_at_epoch: float) -> None:
    from datetime import datetime, timezone

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
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def remove_unlock_timer() -> None:
    subprocess.run(
        ["systemctl", "disable", "--now", "focusguard-unlock.timer"],
        check=False,
        capture_output=True,
    )
    for p in (
        Path("/etc/systemd/system/focusguard-unlock.timer"),
        Path("/etc/systemd/system/focusguard-unlock.service"),
    ):
        if p.exists():
            p.unlink()
    subprocess.run(["systemctl", "daemon-reload"], check=False, capture_output=True)
