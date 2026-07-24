from __future__ import annotations

import argparse
import os
import subprocess
import sys

from . import emergency, hosts, protect, session
from .paths import settings


def _root_required() -> None:
    if os.geteuid() != 0:
        print("This command requires root. Try: sudo focusguard ...", file=sys.stderr)
        sys.exit(1)


def cmd_start(args: argparse.Namespace) -> int:
    _root_required()
    existing = session.load_session()
    if existing and existing.active:
        print(f"Already locked. Left: {existing.remaining_human()}")
        print(f"Ends: {existing.to_dict()['ends_iso']}")
        code = emergency.get_emergency_code() or emergency.ensure_emergency_code()
        print(f"Emergency code: {code}  (enter 10 times: sudo focusguard emergency {code})")
        return 0

    from .paths import DATA_DIR

    allow = DATA_DIR / "ALLOW_EXIT"
    if allow.exists():
        allow.unlink()

    days = args.days if args.days is not None else int(settings().get("lock_days", 30))
    code = emergency.ensure_emergency_code()
    sess = session.create_session(lock_days=days)
    hosts.apply_hosts()
    protect.protect_lock_files(True)
    protect.write_refuse_manual_stop()
    protect.schedule_unlock_timer(sess.ends_at)

    subprocess.run(["systemctl", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "enable", "--now", "focusguard.service"], check=True)

    print("FocusGuard STARTED")
    print(f"  Days : {days}")
    print(f"  Ends : {sess.to_dict()['ends_iso']}")
    print(f"  Left : {sess.remaining_human()}")
    print("Once started, it cannot be stopped.")
    print()
    print(f"EMERGENCY CODE: {code}")
    print(f"  Enter 10 times in a row to unlock early:")
    print(f"  sudo focusguard emergency {code}")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    sess = session.load_session()
    active = bool(sess and sess.active)
    print(f"Status : {'LOCKED' if active else 'off'}")
    if sess:
        print(f"Started : {sess.to_dict()['started_iso']}")
        print(f"Ends    : {sess.to_dict()['ends_iso']}")
        print(f"Left    : {sess.remaining_human()}")
    r = subprocess.run(
        ["systemctl", "is-active", "focusguard.service"],
        capture_output=True,
        text=True,
    )
    svc = (r.stdout or "").strip()
    if r.returncode != 0 and not svc:
        err = (r.stderr or "").strip()
        svc = "n/a" if "not been booted" in err or "Host is down" in err else (err.splitlines()[-1] if err else "unknown")
    print(f"Service: {svc}")
    print(f"Hosts  : {'applied' if hosts.hosts_intact() else 'none/broken'}")
    if active:
        print("Emergency: sudo focusguard emergency <CODE>   (10x in a row)")
    return 0


def cmd_stop(_args: argparse.Namespace) -> int:
    _root_required()
    sess = session.load_session()
    if sess and sess.active:
        print("Once started, it cannot be stopped.")
        print("Use emergency code 10 times: sudo focusguard emergency <CODE>")
        print(f"Left: {sess.remaining_human()}")
        return 2
    from .expire import force_unlock

    force_unlock()
    print("FocusGuard stopped.")
    return 0


def cmd_unlock(_args: argparse.Namespace) -> int:
    _root_required()
    sess = session.load_session()
    if sess and sess.active:
        print("Once started, it cannot be stopped.")
        print("Use: sudo focusguard emergency <CODE>  (10 times)")
        return 2
    from .expire import force_unlock

    force_unlock()
    print("FocusGuard unlocked.")
    return 0


def cmd_emergency(args: argparse.Namespace) -> int:
    _root_required()
    sess = session.load_session()
    if not sess or not sess.active:
        print("No active lock.")
        return 0

    code = args.code
    if not code:
        code = input("Emergency code: ").strip()

    # Ensure a code exists for already-running locks started before this feature
    emergency.ensure_emergency_code()
    unlocked, streak, msg = emergency.submit_emergency_code(code)
    print(msg)
    if unlocked:
        return 0
    if streak == 0 and "Wrong" in msg:
        return 1
    return 0


def cmd_gui(_args: argparse.Namespace) -> int:
    from .gui import main as gui_main

    gui_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="focusguard", description="FocusGuard — Linux focus lock")
    sub = p.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start", help="Start lock (default 30 days)")
    start.add_argument("--days", type=int, default=None, help="Lock duration in days")
    start.set_defaults(func=cmd_start)

    st = sub.add_parser("status", help="Show status")
    st.set_defaults(func=cmd_status)

    stop = sub.add_parser("stop", help="Stop (only after lock expires)")
    stop.set_defaults(func=cmd_stop)

    unlock = sub.add_parser("unlock", help="Unlock (only after lock expires / timer)")
    unlock.set_defaults(func=cmd_unlock)

    em = sub.add_parser("emergency", help="Emergency unlock (enter code 10 times in a row)")
    em.add_argument("code", nargs="?", help="Emergency code")
    em.set_defaults(func=cmd_emergency)

    gui = sub.add_parser("gui", help="Open Linux GUI")
    gui.set_defaults(func=cmd_gui)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
