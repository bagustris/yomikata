"""Mouse hover monitoring.

This module is responsible only for monitoring pointer movement, detecting
when it has settled ("hover"), and notifying listeners. It must never know
about accessibility objects, dictionary lookups, or popup rendering -- those
are the responsibilities of later pipeline stages.

Where the pointer position actually comes from is injected via
:class:`PointerSource`, so this module has no dependency on any particular
windowing system or accessibility API.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from yomikata.hover.debounce import Debouncer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HoverEvent:
    """A single detected hover.

    Attributes:
        x: Pointer X coordinate, in pixels, at the time of the hover.
        y: Pointer Y coordinate, in pixels, at the time of the hover.
        timestamp: Time of the hover, in seconds, from a monotonic clock.
    """

    x: int
    y: int
    timestamp: float


class PointerSource(Protocol):
    """Supplies the current pointer position.

    Implementations may read this from AT-SPI device events, a windowing
    toolkit, or a fake, without :class:`HoverMonitor` knowing the
    difference.
    """

    def get_position(self) -> tuple[int, int] | None:
        """Return the current pointer position, or None if unavailable."""
        ...


class Clock(Protocol):
    """Supplies time and sleep primitives, so tests can avoid real waiting."""

    def now(self) -> float:
        """Return the current time in seconds from a monotonic clock."""
        ...

    def sleep(self, seconds: float) -> None:
        """Block for approximately the given number of seconds."""
        ...


class ModifierKeySource(Protocol):
    """Reports whether a configured modifier key is currently held.

    When a :class:`HoverMonitor` is given one of these, hovers are only
    reported while it reports active -- letting a user require e.g. Ctrl
    held down before a popup appears, instead of triggering on every dwell.
    """

    def is_active(self) -> bool:
        """Return True if the configured modifier is currently held."""
        ...


class SystemClock:
    """Real wall-clock time, backed by the standard library."""

    def now(self) -> float:
        """Return the current time in seconds from a monotonic clock."""
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        """Block for approximately the given number of seconds."""
        time.sleep(seconds)


HoverListener = Callable[[HoverEvent], None]
HoverEndListener = Callable[[], None]


class HoverMonitor:
    """Polls a pointer source and reports settled hover positions."""

    def __init__(
        self,
        pointer_source: PointerSource,
        clock: Clock,
        debouncer: Debouncer | None = None,
        poll_interval_seconds: float = 0.03,
        modifier_source: ModifierKeySource | None = None,
    ) -> None:
        """Initialize the hover monitor.

        Args:
            pointer_source: Supplies the current pointer position.
            clock: Supplies time and sleep primitives.
            debouncer: Decides when a pointer position counts as "settled".
                Defaults to a new :class:`Debouncer` with default tuning.
            poll_interval_seconds: Delay between polls in :meth:`run_forever`.
            modifier_source: If given, hovers are only reported while it
                reports the configured modifier key as held. Defaults to
                None, which reports hovers unconditionally.
        """
        self._pointer_source = pointer_source
        self._clock = clock
        self._debouncer = debouncer or Debouncer()
        self._poll_interval_seconds = poll_interval_seconds
        self._modifier_source = modifier_source
        self._listeners: list[HoverListener] = []
        self._end_listeners: list[HoverEndListener] = []
        self._running = False
        self._modifier_was_active = True

    def add_listener(self, listener: HoverListener) -> None:
        """Register a callback to be invoked for each detected hover."""
        self._listeners.append(listener)

    def remove_listener(self, listener: HoverListener) -> None:
        """Unregister a previously registered callback."""
        self._listeners.remove(listener)

    def add_end_listener(self, listener: HoverEndListener) -> None:
        """Register a callback invoked once when a held modifier is released.

        Lets callers (e.g. hide a popup left showing) react to tracking
        stopping, since no further :class:`HoverEvent` will be reported
        until the modifier is held again. No-op when no modifier source
        was configured, since hovering never stops in that case.
        """
        self._end_listeners.append(listener)

    def remove_end_listener(self, listener: HoverEndListener) -> None:
        """Unregister a previously registered end listener."""
        self._end_listeners.remove(listener)

    def poll_once(self) -> HoverEvent | None:
        """Read the pointer position once and report a hover if settled.

        If a modifier source was configured and does not currently report
        the modifier as held, the debouncer is reset (so a stale dwell
        doesn't fire instantly once the modifier is next pressed) and no
        hover is reported. The first such poll after the modifier was held
        also notifies end listeners, so a popup left showing gets hidden.

        Returns:
            The :class:`HoverEvent` that was reported to listeners, or None
            if no hover was detected on this poll.
        """
        if self._modifier_source is not None and not self._is_modifier_active():
            self._debouncer.reset()
            if self._modifier_was_active:
                self._modifier_was_active = False
                self._notify_end()
            return None
        self._modifier_was_active = True

        try:
            position = self._pointer_source.get_position()
        except Exception:
            logger.warning("Pointer source failed to report a position", exc_info=True)
            return None

        if position is None:
            return None

        x, y = position
        now = self._clock.now()
        if not self._debouncer.update(x, y, now):
            return None

        event = HoverEvent(x=x, y=y, timestamp=now)
        self._notify(event)
        return event

    def run_forever(self) -> None:
        """Poll continuously until :meth:`stop` is called.

        This is a blocking call; callers that need concurrency are
        responsible for running it on a dedicated thread.
        """
        self._running = True
        while self._running:
            self.poll_once()
            self._clock.sleep(self._poll_interval_seconds)

    def stop(self) -> None:
        """Stop a running :meth:`run_forever` loop."""
        self._running = False

    def _is_modifier_active(self) -> bool:
        assert self._modifier_source is not None
        try:
            return self._modifier_source.is_active()
        except Exception:
            logger.warning("Modifier key source failed to report state", exc_info=True)
            return False

    def _notify(self, event: HoverEvent) -> None:
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.warning("Hover listener raised an exception", exc_info=True)

    def _notify_end(self) -> None:
        for listener in self._end_listeners:
            try:
                listener()
            except Exception:
                logger.warning("Hover end listener raised an exception", exc_info=True)
