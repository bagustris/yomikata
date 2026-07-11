"""Concrete pointer position source, backed by X11 (via XWayland).

Native Wayland gives clients no way to query the global pointer position,
by design (see popup/window.py for the same restriction applied to window
positioning). Querying via the X11 protocol through XWayland is the
practical workaround; this was verified empirically against the real
desktop session (an XWarpPointer/query_pointer round-trip), not assumed.
"""

from __future__ import annotations

import logging

from Xlib import X
from Xlib import display as xlib_display

logger = logging.getLogger(__name__)

#: Names accepted for the YOMIKATA_HOVER_MODIFIER environment variable,
#: mapped to the X11 modifier mask bit each corresponds to.
MODIFIER_MASKS: dict[str, int] = {
    "ctrl": X.ControlMask,
    "alt": X.Mod1Mask,
    "shift": X.ShiftMask,
}


class XlibPointerSource:
    """Reads the global pointer position via the X11 protocol."""

    def __init__(self) -> None:
        """Open a connection to the X server."""
        self._display = xlib_display.Display()
        self._root = self._display.screen().root

    def get_position(self) -> tuple[int, int] | None:
        """Return the current global pointer position, or None on failure."""
        try:
            pointer = self._root.query_pointer()
        except Exception:
            logger.warning("Failed to query pointer position", exc_info=True)
            return None
        return pointer.root_x, pointer.root_y

    def close(self) -> None:
        """Close the connection to the X server."""
        self._display.close()


class XlibModifierKeySource:
    """Reports whether a given X11 modifier mask is currently held.

    Uses its own display connection rather than sharing one with
    :class:`XlibPointerSource`, keeping the two independently constructible
    and testable, at the cost of a second XQueryPointer round-trip per poll
    -- negligible next to the accessibility and dictionary work a hover
    already triggers.
    """

    def __init__(self, modifier_mask: int) -> None:
        """Open a connection to the X server.

        Args:
            modifier_mask: The X11 modifier bit to watch for, e.g.
                ``X.ControlMask``. See :data:`MODIFIER_MASKS`.
        """
        self._display = xlib_display.Display()
        self._root = self._display.screen().root
        self._modifier_mask = modifier_mask

    def is_active(self) -> bool:
        """Return True if the configured modifier key is currently held."""
        try:
            pointer = self._root.query_pointer()
        except Exception:
            logger.warning("Failed to query modifier key state", exc_info=True)
            return False
        return bool(pointer.mask & self._modifier_mask)

    def close(self) -> None:
        """Close the connection to the X server."""
        self._display.close()
