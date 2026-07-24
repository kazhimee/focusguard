#!/usr/bin/env bash
# If a lock is active but the daemon is not running, start it again.
set -euo pipefail

LOCK="${FOCUSGUARD_DATA:-/var/lib/focusguard}/lock.json"
ALLOW="${FOCUSGUARD_DATA:-/var/lib/focusguard}/ALLOW_EXIT"

if [[ -f "$ALLOW" ]]; then
  exit 0
fi

if [[ ! -f "$LOCK" ]]; then
  exit 0
fi

# Active if ends_at is still in the future
python3 - <<'PY' || exit 0
import json, time, sys
from pathlib import Path
p = Path("/var/lib/focusguard/lock.json")
data = json.loads(p.read_text())
sys.exit(0 if time.time() < float(data.get("ends_at", 0)) else 1)
PY

# RefuseManualStop may block stop, but SIGKILL / crashes still happen — revive.
systemctl start focusguard.service >/dev/null 2>&1 || true
exit 0
