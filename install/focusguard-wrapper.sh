#!/usr/bin/env bash
# Restarts the daemon forever until ALLOW_EXIT is written (lock expired).
set -euo pipefail

DATA="${FOCUSGUARD_DATA:-/var/lib/focusguard}"
mkdir -p "$DATA"

while [[ ! -f "$DATA/ALLOW_EXIT" ]]; do
  /usr/bin/python3 -m focusguard.daemon || true
  if [[ -f "$DATA/ALLOW_EXIT" ]]; then
    break
  fi
  sleep 1
done

rm -f "$DATA/ALLOW_EXIT"
exit 0
