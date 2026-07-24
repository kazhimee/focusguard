from __future__ import annotations

import logging
import subprocess
import sys

from . import hosts, protect, session
from .paths import DATA_DIR

log = logging.getLogger("focusguard.expire")


def expire_unlock() -> None:
    """Unlock only when the lock period has ended."""
    sess = session.load_session()
    if sess and sess.active:
        print("FocusGuard: kilit hâlâ aktif, expire reddedildi.", file=sys.stderr)
        raise SystemExit(2)

    protect.protect_lock_files(False)
    hosts.remove_hosts()
    protect.clear_refuse_manual_stop()
    protect.remove_unlock_timer()
    session.clear_session()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "ALLOW_EXIT").write_text("1\n", encoding="utf-8")

    subprocess.run(["systemctl", "disable", "--now", "focusguard.service"], check=False)
    log.info("FocusGuard expired and unlocked")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    expire_unlock()


if __name__ == "__main__":
    main()
