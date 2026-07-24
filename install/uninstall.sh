#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "sudo ./install/uninstall.sh" >&2
  exit 1
fi

FORCE="${1:-}"
if [[ -f /var/lib/focusguard/lock.json ]] && [[ "$FORCE" != "--force" ]]; then
  if ! python3 - <<'PY'
import json, time, sys
from pathlib import Path
p = Path("/var/lib/focusguard/lock.json")
if not p.exists():
    sys.exit(0)
data = json.loads(p.read_text())
sys.exit(0 if time.time() >= float(data.get("ends_at", 0)) else 1)
PY
  then
    echo "Kilit hâlâ aktif — uninstall engellendi. Süre bitince dene." >&2
    exit 2
  fi
fi

export FOCUSGUARD_CONFIG=/usr/local/share/focusguard/config
export FOCUSGUARD_DATA=/var/lib/focusguard
export PYTHONPATH=/usr/local/share/focusguard

# Clear refuse-stop so systemd can halt the unit
rm -rf /etc/systemd/system/focusguard.service.d
systemctl daemon-reload

# Allow wrapper to exit
mkdir -p /var/lib/focusguard
echo 1 > /var/lib/focusguard/ALLOW_EXIT

if [[ -x /usr/local/bin/focusguard ]]; then
  # Only if expired (or --force path already checked)
  chattr -i /var/lib/focusguard/lock.json 2>/dev/null || true
  chattr -i /etc/hosts 2>/dev/null || true
  python3 - <<'PY'
from focusguard import hosts, session, protect
protect.protect_lock_files(False)
hosts.remove_hosts()
protect.clear_refuse_manual_stop()
protect.remove_unlock_timer()
session.clear_session()
PY
fi

systemctl disable --now focusguard.service 2>/dev/null || true
systemctl disable --now focusguard-unlock.timer 2>/dev/null || true
rm -f /etc/systemd/system/focusguard.service
rm -f /etc/systemd/system/focusguard-unlock.service
rm -f /etc/systemd/system/focusguard-unlock.timer
rm -rf /etc/systemd/system/focusguard.service.d
rm -rf /usr/local/share/focusguard
rm -f /usr/local/bin/focusguard
rm -f /usr/local/lib/focusguard/focusguard-wrapper.sh
rmdir /usr/local/lib/focusguard 2>/dev/null || true
systemctl daemon-reload
echo "FocusGuard kaldırıldı."
