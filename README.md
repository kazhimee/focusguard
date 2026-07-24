# FocusGuard

> **Once started, it cannot be stopped.**  
> **Linux only.**

Locks social media (including Threads), games, and AI apps/sites. Spotify / Apple Music and coding forums stay allowed.

## Install

```bash
git clone https://github.com/kazhimee/focusguard.git
cd focusguard
sudo pacman -S --needed python-yaml python-gobject libadwaita gtk4 wmctrl
sudo ./install/install.sh
```

## Usage

```bash
# GUI
focusguard gui

# or CLI
sudo focusguard start          # default 30 days
sudo focusguard start --days 7
focusguard status
```

## Blocked / allowed

| Blocked | Allowed |
|--------|---------|
| Instagram, X, TikTok, **Threads**, Discord, YouTube… | Spotify, Apple Music |
| ChatGPT, Claude, Gemini, Cursor… | w3schools, Coddy, Duolingo, GitHub… |
| Steam, Heroic, Lutris, games | Editors (except Cursor) |

Lists: `config/domains.yaml`, `config/apps.yaml`

## How it works

1. systemd service (`Restart=always`, `RefuseManualStop`)
2. `/etc/hosts` sinkhole
3. Blocked process killer
4. Window title / class scanner

## Site

GitHub Pages: https://kazhimee.github.io/focusguard/

## License

MIT
