"""Dwell-based debounce logic for hover detection.

The debouncer decides *when* a settled pointer position should be reported
as a hover, given a stream of raw (x, y, timestamp) samples. It contains no
I/O and no knowledge of AT-SPI, dictionaries, or rendering, so it can be
tested with synthetic input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DebounceConfig:
    """Tuning parameters for :class:`Debouncer`.

    Attributes:
        dwell_seconds: How long the pointer must stay within
            ``movement_threshold_px`` of an anchor point before a hover is
            reported.
        movement_threshold_px: Maximum distance, in pixels, the pointer may
            drift from its anchor and still be considered "stationary".
    """

    dwell_seconds: float = 0.15
    movement_threshold_px: float = 4.0


class Debouncer:
    """Tracks pointer movement and reports when it has settled.

    A settled position is reported at most once per "dwell" -- the pointer
    must move away and resettle before another hover is reported for the
    same location.
    """

    def __init__(self, config: DebounceConfig | None = None) -> None:
        """Initialize the debouncer.

        Args:
            config: Tuning parameters. Defaults to :class:`DebounceConfig`.
        """
        self._config = config or DebounceConfig()
        self._anchor: tuple[int, int] | None = None
        self._anchor_time: float | None = None
        self._reported_for_anchor = False

    def update(self, x: int, y: int, now: float) -> bool:
        """Feed a new pointer sample into the debouncer.

        Args:
            x: Pointer X coordinate, in pixels.
            y: Pointer Y coordinate, in pixels.
            now: Current time, in seconds, from a monotonic clock.

        Returns:
            True if this sample causes a hover to be reported, False
            otherwise.
        """
        moved_beyond_threshold = (
            self._anchor is not None
            and self._distance_from_anchor(x, y) > self._config.movement_threshold_px
        )
        if self._anchor is None or moved_beyond_threshold:
            self._anchor = (x, y)
            self._anchor_time = now
            self._reported_for_anchor = False
            return False

        if self._reported_for_anchor:
            return False

        assert self._anchor_time is not None
        if now - self._anchor_time < self._config.dwell_seconds:
            return False

        self._reported_for_anchor = True
        return True

    def reset(self) -> None:
        """Clear all tracked state, as if no samples had been seen yet."""
        self._anchor = None
        self._anchor_time = None
        self._reported_for_anchor = False

    def _distance_from_anchor(self, x: int, y: int) -> float:
        assert self._anchor is not None
        anchor_x, anchor_y = self._anchor
        return math.hypot(x - anchor_x, y - anchor_y)
