#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${PREFIX:-/usr/local}"
SHARE="$PREFIX/share/focusguard"
BIN="$PREFIX/bin/focusguard"
USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
USER_UID="$(id -u "$USER_NAME")"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "install.sh root ile çalışmalı: sudo ./install/install.sh" >&2
  exit 1
fi

echo "==> FocusGuard kuruluyor ($SHARE)"
mkdir -p "$SHARE" /var/lib/focusguard "$PREFIX/lib/focusguard"

rm -rf "$SHARE/focusguard" "$SHARE/config" "$SHARE/assets"
mkdir -p "$SHARE"
cp -a "$ROOT/focusguard" "$ROOT/config" "$SHARE/"
if [[ -d "$ROOT/assets" ]]; then
  cp -a "$ROOT/assets" "$SHARE/"
fi
find "$SHARE" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$SHARE" -type f -name '*.pyc' -delete 2>/dev/null || true

install -m 755 "$ROOT/install/focusguard-wrapper.sh" "$PREFIX/lib/focusguard/focusguard-wrapper.sh"

if python3 -c "import yaml" 2>/dev/null; then
  echo "==> PyYAML hazır"
elif command -v pacman >/dev/null 2>&1; then
  echo "==> PyYAML yok — pacman ile kuruluyor"
  pacman -S --needed --noconfirm python-yaml
elif python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip install --break-system-packages -q PyYAML || python3 -m pip install -q PyYAML
else
  echo "PyYAML bulunamadı. Kur: sudo pacman -S python-yaml" >&2
  exit 1
fi

# GUI deps hint
if ! python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw" 2>/dev/null; then
  echo "Uyarı: GUI için libadwaita + gtk4 python bağları lazım:"
  echo "  sudo pacman -S python-gobject libadwaita gtk4"
fi

cat > "$BIN" <<EOF
#!/usr/bin/env bash
export FOCUSGUARD_CONFIG="$SHARE/config"
export FOCUSGUARD_DATA="/var/lib/focusguard"
export PYTHONPATH="$SHARE\${PYTHONPATH:+:\$PYTHONPATH}"
exec /usr/bin/python3 -m focusguard "\$@"
EOF
chmod 755 "$BIN"

# Desktop entry for app menu
install -d /usr/local/share/applications
install -m 644 "$ROOT/install/focusguard.desktop" /usr/local/share/applications/focusguard.desktop
# refresh desktop db if available
update-desktop-database /usr/local/share/applications >/dev/null 2>&1 || true

UNIT="/etc/systemd/system/focusguard.service"
cat > "$UNIT" <<EOF
[Unit]
Description=FocusGuard focus lock daemon
After=network.target

[Service]
Type=simple
ExecStart=$PREFIX/lib/focusguard/focusguard-wrapper.sh
Restart=always
RestartSec=1
KillMode=control-group
TimeoutStopSec=5
Environment=FOCUSGUARD_CONFIG=$SHARE/config
Environment=FOCUSGUARD_DATA=/var/lib/focusguard
Environment=PYTHONPATH=$SHARE
Environment=DISPLAY=:0
Environment=XAUTHORITY=$USER_HOME/.Xauthority
Environment=WAYLAND_DISPLAY=wayland-0
Environment=XDG_RUNTIME_DIR=/run/user/$USER_UID
Environment=SUDO_USER=$USER_NAME
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo
echo "Kurulum tamam: $BIN"
echo "  Arayüz : focusguard gui"
echo "  Başlat : sudo focusguard start"
echo "  Durum  : focusguard status"
echo
echo "Önerilen: sudo pacman -S --needed wmctrl python-gobject libadwaita gtk4"
echo "UYARI: Açıldıktan sonra birdaha durdurulamaz."
