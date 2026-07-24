from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from . import hosts, session
from .paths import settings

WARNING = "Açıldıktan sonra birdaha durdurulamaz"
CSS = """
window {
  background: #0c1118;
  color: #e8eef6;
}
.brand {
  font-family: "JetBrains Mono", "IBM Plex Mono", "Source Code Pro", monospace;
  font-weight: 800;
  font-size: 42px;
  letter-spacing: -1px;
  color: #f4f7fb;
}
.tagline {
  font-size: 15px;
  color: #8fa3b8;
}
.linux-badge {
  background: #143047;
  color: #7dd3fc;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}
.warn-box {
  background: #2a1212;
  border: 2px solid #ef4444;
  border-radius: 14px;
  padding: 18px 20px;
}
.warn-title {
  color: #fecaca;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.warn-text {
  color: #fff1f2;
  font-size: 22px;
  font-weight: 800;
}
.status-card {
  background: #121a24;
  border: 1px solid #243041;
  border-radius: 16px;
  padding: 16px 18px;
}
.status-label {
  color: #8fa3b8;
  font-size: 12px;
  letter-spacing: 0.08em;
}
.status-value {
  font-size: 18px;
  font-weight: 700;
}
.locked { color: #fb7185; }
.idle { color: #86efac; }
.btn-lock {
  background: #e11d48;
  color: white;
  font-weight: 800;
  font-size: 16px;
  padding: 14px 18px;
  border-radius: 12px;
}
.btn-lock:hover { background: #be123c; }
.btn-lock:disabled { background: #3f1d2a; color: #9ca3af; }
.hint {
  color: #6b7c8f;
  font-size: 12px;
}
"""


class FocusGuardWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="FocusGuard")
        self.set_default_size(520, 640)
        self.set_resizable(False)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_top(28)
        root.set_margin_bottom(28)
        root.set_margin_start(28)
        root.set_margin_end(28)
        self.set_content(root)

        badge = Gtk.Label(label="LINUX ONLY")
        badge.add_css_class("linux-badge")
        badge.set_halign(Gtk.Align.START)
        root.append(badge)

        brand = Gtk.Label(label="FocusGuard")
        brand.add_css_class("brand")
        brand.set_halign(Gtk.Align.START)
        root.append(brand)

        tag = Gtk.Label(label="Sosyal medya, oyun ve yapay zeka kilidi.")
        tag.add_css_class("tagline")
        tag.set_halign(Gtk.Align.START)
        root.append(tag)

        warn = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        warn.add_css_class("warn-box")
        wtitle = Gtk.Label(label="UYARI")
        wtitle.add_css_class("warn-title")
        wtitle.set_halign(Gtk.Align.START)
        wtext = Gtk.Label(label=WARNING)
        wtext.add_css_class("warn-text")
        wtext.set_halign(Gtk.Align.START)
        wtext.set_wrap(True)
        warn.append(wtitle)
        warn.append(wtext)
        root.append(warn)

        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        status_box.add_css_class("status-card")
        sl = Gtk.Label(label="DURUM")
        sl.add_css_class("status-label")
        sl.set_halign(Gtk.Align.START)
        self.status_value = Gtk.Label(label="…")
        self.status_value.add_css_class("status-value")
        self.status_value.set_halign(Gtk.Align.START)
        self.remain_value = Gtk.Label(label="")
        self.remain_value.add_css_class("tagline")
        self.remain_value.set_halign(Gtk.Align.START)
        status_box.append(sl)
        status_box.append(self.status_value)
        status_box.append(self.remain_value)
        root.append(status_box)

        days_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        days_label = Gtk.Label(label="Süre (gün)")
        days_label.set_halign(Gtk.Align.START)
        days_label.set_hexpand(True)
        self.days_spin = Gtk.SpinButton.new_with_range(1, 365, 1)
        self.days_spin.set_value(float(settings().get("lock_days", 30)))
        days_row.append(days_label)
        days_row.append(self.days_spin)
        root.append(days_row)

        self.lock_btn = Gtk.Button(label="Kilidi Başlat")
        self.lock_btn.add_css_class("btn-lock")
        self.lock_btn.connect("clicked", self._on_lock)
        root.append(self.lock_btn)

        hint = Gtk.Label(
            label="Müzik serbest · kod forumları serbest · Threads/sosyal/AI/oyun yasak"
        )
        hint.add_css_class("hint")
        hint.set_wrap(True)
        hint.set_halign(Gtk.Align.START)
        root.append(hint)

        self._refresh_status()
        GLib.timeout_add_seconds(2, self._tick)

    def _tick(self) -> bool:
        self._refresh_status()
        return True

    def _refresh_status(self) -> None:
        sess = session.load_session()
        active = bool(sess and sess.active)
        if active:
            self.status_value.set_text("KİLİTLİ")
            self.status_value.remove_css_class("idle")
            self.status_value.add_css_class("locked")
            self.remain_value.set_text(f"Kalan: {sess.remaining_human()}")
            self.lock_btn.set_sensitive(False)
            self.lock_btn.set_label("Kilit aktif — durdurulamaz")
            self.days_spin.set_sensitive(False)
        else:
            self.status_value.set_text("Kapalı")
            self.status_value.remove_css_class("locked")
            self.status_value.add_css_class("idle")
            hosts_txt = "hosts aktif" if hosts.hosts_intact() else "hazır"
            self.remain_value.set_text(hosts_txt)
            self.lock_btn.set_sensitive(True)
            self.lock_btn.set_label("Kilidi Başlat")
            self.days_spin.set_sensitive(True)

    def _on_lock(self, _btn: Gtk.Button) -> None:
        days = int(self.days_spin.get_value())
        dialog = Adw.AlertDialog(
            heading="Emin misin?",
            body=f"{days} günlük kilit başlatılacak.\n\n{WARNING}",
        )
        dialog.add_response("cancel", "Vazgeç")
        dialog.add_response("go", "Kilitle")
        dialog.set_response_appearance("go", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._confirm_lock, days)
        dialog.present(self)

    def _confirm_lock(self, _dialog: Adw.AlertDialog, response: str, days: int) -> None:
        if response != "go":
            return
        self.lock_btn.set_sensitive(False)
        self.lock_btn.set_label("Başlatılıyor…")

        def worker() -> None:
            cmd = self._start_command(days)
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True)
                ok = proc.returncode == 0
                msg = (proc.stdout or proc.stderr or "").strip()
            except Exception as exc:  # noqa: BLE001
                ok = False
                msg = str(exc)
            GLib.idle_add(self._after_start, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _start_command(self, days: int) -> list[str]:
        focusguard = shutil.which("focusguard") or "focusguard"
        inner = [focusguard, "start", "--days", str(days)]
        if os.geteuid() == 0:
            return inner
        if shutil.which("pkexec"):
            return ["pkexec", *inner]
        return ["sudo", *inner]

    def _after_start(self, ok: bool, msg: str) -> None:
        self._refresh_status()
        if not ok:
            self.lock_btn.set_sensitive(True)
            self.lock_btn.set_label("Kilidi Başlat")
            err = Adw.AlertDialog(heading="Başlatılamadı", body=msg or "Bilinmeyen hata")
            err.add_response("ok", "Tamam")
            err.present(self)
        return False


class FocusGuardApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="dev.focusguard.app")

    def do_activate(self) -> None:  # noqa: N802
        win = FocusGuardWindow(self)
        win.present()


def main() -> None:
    if sys.platform != "linux":
        print("FocusGuard arayüzü yalnızca Linux içindir.", file=sys.stderr)
        sys.exit(1)
    app = FocusGuardApp()
    app.run(None)


if __name__ == "__main__":
    main()
