#!/usr/bin/env bash
# Apply repo fix to the live install while a lock is active.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run: sudo $0" >&2
  exit 1
fi

echo "==> Deploying FocusGuard fix"
mkdir -p /usr/local/share/focusguard /usr/local/lib/focusguard /var/lib/focusguard

rm -rf /usr/local/share/focusguard/focusguard /usr/local/share/focusguard/config
cp -a "$ROOT/focusguard" "$ROOT/config" /usr/local/share/focusguard/
mkdir -p /usr/local/share/focusguard/install
cp -a "$ROOT/install/." /usr/local/share/focusguard/install/

install -m 755 "$ROOT/install/focusguard-wrapper.sh" /usr/local/lib/focusguard/focusguard-wrapper.sh
install -m 755 "$ROOT/install/focusguard-watchdog.sh" /usr/local/lib/focusguard/focusguard-watchdog.sh

export FOCUSGUARD_CONFIG=/usr/local/share/focusguard/config
export FOCUSGUARD_DATA=/var/lib/focusguard
export PYTHONPATH=/usr/local/share/focusguard

python3 - <<'PY'
from focusguard import emergency, hosts, protect, session

# Create emergency code for already-running locks
code = emergency.ensure_emergency_code()
print(f"EMERGENCY CODE: {code}")
print(f"  Unlock early (10x): sudo focusguard emergency {code}")

# Rewrite hosts without invalid entries (bing.com/chat etc.)
chattr_off = True
hosts.apply_hosts()
print("Hosts rewritten (sanitized).")

if session.is_locked():
    protect.protect_lock_files(False)
    protect.write_refuse_manual_stop()
    protect.protect_lock_files(True)
    print("Lock active: refuse-stop + watchdog refreshed")
else:
    print("No active lock")
PY

systemctl daemon-reload
systemctl enable --now focusguard-watchdog.timer 2>/dev/null || true

if [[ -f /var/lib/focusguard/lock.json ]]; then
  systemctl reset-failed focusguard.service 2>/dev/null || true
  chattr -i /etc/systemd/system/focusguard.service.d/lock.conf 2>/dev/null || true
  systemctl start focusguard.service || true
fi

echo
echo "Done."
echo "  focusguard status"
echo "  Emergency (10x): sudo focusguard emergency FG-EXIT-9K"
echo "  (or the code printed above if different)"
