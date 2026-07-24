from __future__ import annotations

import logging
import signal
import sys
import time

from . import hosts, processes, protect, session, windows
from .expire import expire_unlock
from .paths import settings

log = logging.getLogger("focusguard")


class Daemon:
    def __init__(self) -> None:
        self._stop = False
        self._kill_cooldown: dict[int, float] = {}
        self._last_hosts = 0.0

    def request_stop(self, *_args) -> None:
        if session.is_locked():
            log.warning("Stop ignored — lock still active (%s remaining)", self._remaining())
            return
        self._stop = True

    def _remaining(self) -> str:
        s = session.load_session()
        return s.remaining_human() if s else "?"

    def _enforce(self, do_proc: bool, do_win: bool) -> None:
        """Close blocked windows and kill blocked apps."""
        found_procs = processes.iter_blocked_pids() if do_proc else []
        found_wins = windows.list_blocked_windows() if do_win else []
        if not found_procs and not found_wins:
            return

        names = [n for _, n in found_procs] + [t for _, t in found_wins]
        log.info("Blocked activity: %s", " | ".join(names[:8]))

        if found_wins:
            closed = windows.close_windows(found_wins)
            if closed:
                log.info("Closed windows: %s", " | ".join(closed[:5]))

        if do_proc:
            killed = processes.kill_blocked(self._kill_cooldown, cooldown_sec=0)
            if killed:
                log.info("Killed apps: %s", ", ".join(killed))
            elif found_procs:
                killed = processes.kill_pids(found_procs, self._kill_cooldown, cooldown_sec=0)
                if killed:
                    log.info("Killed apps: %s", ", ".join(killed))

        time.sleep(0.5)
        if found_wins:
            windows.close_windows(windows.list_blocked_windows())
        if do_proc:
            processes.kill_blocked(self._kill_cooldown, cooldown_sec=0)

    def run(self) -> int:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
        cfg = settings()
        poll = float(cfg.get("poll_interval_seconds", 2))
        hosts_every = float(cfg.get("hosts_reapply_seconds", 15))
        do_proc = bool(cfg.get("process_scan", True))
        do_win = bool(cfg.get("window_scan", True))

        sess = session.load_session()
        if not sess or not sess.active:
            log.error("No active lock session. Start with: focusguard start")
            return 1

        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

        protect.protect_lock_files(True)
        hosts.apply_hosts()
        self._last_hosts = time.time()
        log.info(
            "FocusGuard active until %s (%s remaining)",
            sess.to_dict()["ends_iso"],
            sess.remaining_human(),
        )

        while not self._stop:
            sess = session.load_session()
            if not sess or not sess.active:
                log.info("Lock expired — unlocking")
                expire_unlock()
                return 0

            self._last_hosts = hosts.ensure_hosts(self._last_hosts, hosts_every)
            self._enforce(do_proc, do_win)
            time.sleep(poll)

        return 0


def main() -> None:
    sys.exit(Daemon().run())


if __name__ == "__main__":
    main()
