# FocusGuard

> **Açıldıktan sonra birdaha durdurulamaz.**  
> Yalnızca **Linux**.

Sosyal medya (Threads dahil), oyun ve yapay zeka uygulamalarını/sitelerini kilitler. Spotify / Apple Music ve kodlama forumları serbest kalır.

## Kurulum

```bash
git clone https://github.com/kazhimee/focusguard.git
cd focusguard
sudo pacman -S --needed python-yaml python-gobject libadwaita gtk4 wmctrl
sudo ./install/install.sh
```

## Kullanım

```bash
# Arayüz
focusguard gui

# veya CLI
sudo focusguard start          # varsayılan 30 gün
sudo focusguard start --days 7
focusguard status
```

## Ne engellenir / ne serbest?

| Engelli | Serbest |
|--------|---------|
| Instagram, X, TikTok, **Threads**, Discord, YouTube… | Spotify, Apple Music |
| ChatGPT, Claude, Gemini, Cursor… | w3schools, Coddy, Duolingo, GitHub… |
| Steam, Heroic, Lutris, oyunlar | Editörler (Cursor hariç) |

Listeler: `config/domains.yaml`, `config/apps.yaml`

## Nasıl çalışır?

1. systemd servisi (`Restart=always`, `RefuseManualStop`)
2. `/etc/hosts` sinkhole
3. Yasaklı process öldürme
4. Pencere başlığı / class tarama

## Site

GitHub Pages: proje `docs/` klasöründen yayınlanır.

## Lisans

MIT
