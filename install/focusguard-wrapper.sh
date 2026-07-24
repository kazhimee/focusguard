#!/usr/bin/env bash
# Restarts the daemon forever until ALLOW_EXIT is written (lock expired).
# Ignores SIGTERM so systemctl stop cannot quietly end the lock loop.
set -uo pipefail

DATA="${FOCUSGUARD_DATA:-/var/lib/focusguard}"
mkdir -p "$DATA"

trap '' TERM INT HUP

while [[ ! -f "$DATA/ALLOW_EXIT" ]]; do
  /usr/bin/python3 -m focusguard.daemon || true
  if [[ -f "$DATA/ALLOW_EXIT" ]]; then
    break
  fi
  sleep 1
done

rm -f "$DATA/ALLOW_EXIT"
exit 0
