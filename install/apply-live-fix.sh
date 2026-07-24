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
cp -a "$ROOT/install/"*.sh "$ROOT/install/"*.service "$ROOT/install/"*.timer \
  /usr/local/share/focusguard/install/ 2>/dev/null || true
cp -a "$ROOT/install/"* /usr/local/share/focusguard/install/ 2>/dev/null || true

install -m 755 "$ROOT/install/focusguard-wrapper.sh" /usr/local/lib/focusguard/focusguard-wrapper.sh
install -m 755 "$ROOT/install/focusguard-watchdog.sh" /usr/local/lib/focusguard/focusguard-watchdog.sh

# Refresh refuse-stop + watchdog while lock is active
export FOCUSGUARD_CONFIG=/usr/local/share/focusguard/config
export FOCUSGUARD_DATA=/var/lib/focusguard
export PYTHONPATH=/usr/local/share/focusguard
python3 - <<'PY'
from focusguard import protect, session
if session.is_locked():
    protect.protect_lock_files(False)
    protect.write_refuse_manual_stop()
    protect.protect_lock_files(True)
    print("Lock active: refuse-stop + watchdog refreshed")
else:
    print("No active lock")
PY

systemctl daemon-reload
systemctl enable --now focusguard-watchdog.timer
# Revive daemon if lock active
if [[ -f /var/lib/focusguard/lock.json ]]; then
  systemctl reset-failed focusguard.service 2>/dev/null || true
  # Temporarily clear refuse to allow start after failed state, then re-apply
  chattr -i /etc/systemd/system/focusguard.service.d/lock.conf 2>/dev/null || true
  systemctl start focusguard.service || true
fi

echo
echo "Done. Check:"
echo "  focusguard status"
echo "  systemctl status focusguard --no-pager"
echo "  systemctl stop focusguard   # should refuse / come back via watchdog"
