"""Optional on-screen HUD — text only, no floating orb.

Designed for a second monitor. On Wayland/Linux, screen capture may still include
this window unless your compositor supports exclude-from-capture. Prefer the
companion web UI on your phone for guaranteed stealth during screen sharing.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interview_assistent.events import EventBus

logger = logging.getLogger(__name__)


class StealthHud:
    """Minimal GTK4 text panel that updates from the event bus."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._thread: threading.Thread | None = None
        self._answer_label = None
        self._status_label = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._thread = threading.Thread(target=self._run_gtk, daemon=True)
        self._thread.start()

    def _run_gtk(self) -> None:
        try:
            import gi

            gi.require_version("Gtk", "4.0")
            from gi.repository import GLib, Gtk
        except Exception as exc:
            logger.warning("GTK4 HUD unavailable: %s", exc)
            return

        class HudWindow(Gtk.ApplicationWindow):
            def __init__(self, app, hud: StealthHud) -> None:
                super().__init__(application=app, title="")
                self.hud = hud
                self.set_default_size(420, 280)
                self.set_opacity(0.92)

                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                box.set_margin_top(12)
                box.set_margin_bottom(12)
                box.set_margin_start(12)
                box.set_margin_end(12)

                hud._status_label = Gtk.Label(label="Idle")
                hud._status_label.set_halign(Gtk.Align.START)
                hud._status_label.add_css_class("dim-label")

                hud._answer_label = Gtk.Label(label="Suggested answers appear here.")
                hud._answer_label.set_wrap(True)
                hud._answer_label.set_halign(Gtk.Align.START)
                hud._answer_label.set_valign(Gtk.Align.START)

                scroll = Gtk.ScrolledWindow()
                scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scroll.set_child(hud._answer_label)

                hint = Gtk.Label(
                    label="No orb. Use phone companion when screen sharing."
                )
                hint.add_css_class("dim-label")
                hint.set_wrap(True)

                box.append(hud._status_label)
                box.append(scroll)
                box.append(hint)
                self.set_child(box)

        class HudApp(Gtk.Application):
            def __init__(self, hud: StealthHud) -> None:
                super().__init__(application_id="com.interview.assistant.hud")
                self.hud = hud

            def do_activate(self) -> None:
                self.window = HudWindow(self, self.hud)
                self.window.present()

        app = HudApp(self)
        asyncio.run_coroutine_threadsafe(self._listen_events(), self._loop)
        app.run()

    async def _listen_events(self) -> None:
        queue = await self.bus.subscribe()
        while True:
            message = await queue.get()
            if message.get("type") == "status":
                self._set_status(message.get("state", ""), message.get("detail", ""))
            elif message.get("type") == "answer":
                self._set_answer(message.get("question", ""), message.get("answer", ""))

    def _set_status(self, state: str, detail: str) -> None:
        if not self._status_label:
            return

        def update() -> None:
            text = f"{state}: {detail}" if detail else state
            self._status_label.set_text(text)

        self._glib_idle(update)

    def _set_answer(self, question: str, answer: str) -> None:
        if not self._answer_label:
            return

        def update() -> None:
            self._answer_label.set_text(f"Q: {question}\n\n{answer}")

        self._glib_idle(update)

    def _glib_idle(self, callback) -> None:
        try:
            import gi

            gi.require_version("Gtk", "4.0")
            from gi.repository import GLib

            GLib.idle_add(callback)
        except Exception:
            pass