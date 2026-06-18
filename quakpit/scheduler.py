"""Polls the calendar and fires a flight a few minutes before each meeting.

Mirrors the original: refresh the upcoming-events window every minute, check
trigger times every 15s, and fire within a 90s window after the trigger so a
sleeping/he busy machine still shows the reminder. Each (event, lead) pair fires
at most once, tracked in ``_fired``.
"""

from __future__ import annotations

import time
from typing import Callable

from PySide6.QtCore import QObject, QTimer

from . import config, google_calendar
from .google_calendar import UpcomingEvent

POLL_MS = 60_000  # refresh the event window every minute
TICK_MS = 15_000  # check trigger times every 15s
FIRE_WINDOW_MS = 90_000  # fire within 90s after the trigger time

# A flight payload: {"message": str, "duration_ms": int, "sound": bool}
FlightFn = Callable[[dict], None]


class Scheduler(QObject):
    def __init__(self, fly: FlightFn, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fly = fly
        self._upcoming: list[UpcomingEvent] = []
        self._fired: set[str] = set()
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._refresh)
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)

    def start(self) -> None:
        self.stop()
        self._refresh()
        self._poll.start(POLL_MS)
        self._tick.start(TICK_MS)

    def stop(self) -> None:
        self._poll.stop()
        self._tick.stop()

    def upcoming(self) -> list[UpcomingEvent]:
        return list(self._upcoming)

    # --- internals ---
    def _refresh(self) -> None:
        try:
            self._upcoming = google_calendar.list_upcoming(60)
        except Exception:
            return  # offline / not connected — keep the last known list
        # Forget fired markers for events that are no longer upcoming.
        ids = [e.id for e in self._upcoming]
        for key in list(self._fired):
            if not any(key.startswith(f"{i}:") for i in ids):
                self._fired.discard(key)

    def _on_tick(self) -> None:
        prefs = config.get_prefs()
        now = time.time() * 1000.0
        lead = prefs["lead_minutes"] * 60_000
        duration = int(prefs.get("duration_ms", 9000))

        for ev in self._upcoming:
            # 1) The lead-time reminder ("Call with Jack in 5 minutes").
            trigger_at = ev.start - lead
            lead_key = f"{ev.id}:{prefs['lead_minutes']}"
            lead_due = trigger_at <= now < trigger_at + FIRE_WINDOW_MS
            if lead_due and ev.start > now and lead_key not in self._fired:
                self._fired.add(lead_key)
                minutes = max(1, round((ev.start - now) / 60_000))
                message = (
                    prefs["message_template"]
                    .replace("{title}", ev.title)
                    .replace("{minutes}", str(minutes))
                )
                self._fly({"message": message, "duration_ms": duration, "sound": prefs["sound_enabled"]})

            # 2) Optional second fly-by right at the start time.
            if prefs.get("fly_at_start"):
                start_key = f"{ev.id}:start"
                start_due = ev.start <= now < ev.start + FIRE_WINDOW_MS
                if start_due and start_key not in self._fired:
                    self._fired.add(start_key)
                    self._fly(
                        {
                            "message": f"{ev.title} starting now",
                            "duration_ms": duration,
                            "sound": prefs["sound_enabled"],
                        }
                    )
