#!/usr/bin/env bash
# Local runner — works without system install.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export FOCUSGUARD_CONFIG="${FOCUSGUARD_CONFIG:-$ROOT/config}"
export FOCUSGUARD_DATA="${FOCUSGUARD_DATA:-$ROOT/.data}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$FOCUSGUARD_DATA"
exec /usr/bin/python3 -m focusguard "$@"
