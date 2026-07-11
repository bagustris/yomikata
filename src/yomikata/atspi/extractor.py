"""Accessible text extraction at a screen coordinate.

Responsible only for locating the accessible object under a point and
reading its text and the character offset at that point. Must never raise:
accessibility being unavailable, an object vanishing mid-query, or a widget
having no text are all expected, common conditions on a live desktop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from yomikata.atspi.cursor import AccessibleLike, ComponentLike, locate_accessible_at_point
from yomikata.util.session import is_wayland_session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccessibleTextInfo:
    """Text content and offset read from an accessible object.

    Attributes:
        text: The accessible's full text content.
        offset: Character offset into ``text`` corresponding to the queried
            screen point.
    """

    text: str
    offset: int


class AccessibilityBackend(Protocol):
    """Supplies accessible text at a screen coordinate."""

    def get_text_at_point(self, x: int, y: int) -> AccessibleTextInfo | None:
        """Return text and offset at (x, y), or None if unavailable."""
        ...


class AccessibilityExtractor:
    """Public entry point for reading accessible text under the pointer."""

    def __init__(self, backend: AccessibilityBackend | None = None) -> None:
        """Initialize the extractor.

        Args:
            backend: Supplies accessible text. Defaults to a new
                :class:`AtspiAccessibilityBackend`.
        """
        self._backend = backend or AtspiAccessibilityBackend()

    def extract(self, x: int, y: int) -> AccessibleTextInfo | None:
        """Read accessible text and offset at a screen coordinate.

        Args:
            x: Screen X coordinate, in pixels.
            y: Screen Y coordinate, in pixels.

        Returns:
            The text and offset at that point, or None if no accessible
            text could be read there.
        """
        try:
            return self._backend.get_text_at_point(x, y)
        except Exception:
            logger.warning("Accessibility backend failed to extract text", exc_info=True)
            return None


class AtspiAccessibilityBackend:
    """Reads accessible text via the AT-SPI D-Bus service (gi.repository.Atspi)."""

    def __init__(
        self, atspi_module: Any | None = None, wayland_session: bool | None = None
    ) -> None:
        """Initialize the backend.

        Args:
            atspi_module: The ``Atspi`` GI module to use. Defaults to the
                real ``gi.repository.Atspi``; injectable so tests can
                supply a fake without a running AT-SPI bus.
            wayland_session: Whether the desktop session is Wayland, which
                enables the native-Wayland-client diagnostic emitted when
                extraction fails. Defaults to detecting it from the
                environment; injectable so tests are deterministic.
        """
        if atspi_module is None:
            import gi

            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi

            atspi_module = Atspi

        self._atspi = atspi_module
        self._wayland_session = is_wayland_session() if wayland_session is None else wayland_session
        self._warned_wayland_frames: set[str] = set()
        init_result = atspi_module.init()
        if init_result != 0:
            logger.warning("Atspi.init() returned non-zero status: %s", init_result)

    #: Bounds for the descendant probe in :meth:`get_text_at_point`, so a
    #: document with a huge accessibility subtree (e.g. one page object per
    #: PDF page) can't turn a single hover into hundreds of D-Bus calls.
    _PROBE_MAX_NODES = 32
    _PROBE_MAX_DEPTH = 4

    def get_text_at_point(self, x: int, y: int) -> AccessibleTextInfo | None:
        atspi = self._atspi

        active_frame = self._find_active_frame()
        if active_frame is None:
            return None

        root = _AtspiAccessibleAdapter(active_frame, atspi.CoordType.SCREEN, atspi)
        hit = locate_accessible_at_point(root, x, y)

        info: AccessibleTextInfo | None = None
        if isinstance(hit, _AtspiAccessibleAdapter):
            info = self._read_text(hit.accessible, x, y)
            if info is None:
                info = self._probe_descendants_for_text(hit.accessible, x, y)

        if info is None:
            self._warn_if_frame_hides_its_position(active_frame)
        return info

    def _warn_if_frame_hides_its_position(self, frame: Any) -> None:
        """Diagnose the native-Wayland silent failure mode after a missed hit.

        A native Wayland client never learns where the compositor placed
        its window, so it reports AT-SPI extents relative to its own
        surface: the frame claims to sit at (0, 0) regardless of its real
        screen position (verified empirically against Wayland Evince), and
        hit-testing it against the global pointer position can never line
        up. To the rest of the pipeline that is indistinguishable from
        "no text under the pointer", which makes the app silently do
        nothing -- so name the likely culprit and the fix once per frame,
        rather than staying quiet or re-logging on every poll.
        """
        if not self._wayland_session:
            return

        try:
            component = frame.get_component_iface()
            if component is None:
                return
            extents = self._atspi.Component.get_extents(component, self._atspi.CoordType.SCREEN)
            if extents.x != 0 or extents.y != 0:
                return
            frame_name = str(frame.get_name() or "")
        except Exception:
            logger.debug("Failed to inspect the active frame's extents", exc_info=True)
            return

        if frame_name in self._warned_wayland_frames:
            return
        self._warned_wayland_frames.add(frame_name)
        logger.warning(
            "Active window %r reports its screen position as (0, 0); on a Wayland "
            "session this usually means it runs as a native Wayland client, whose "
            "real window position is hidden from accessibility clients, so hovered "
            "text cannot be located. Relaunch it under XWayland instead, e.g. "
            "GDK_BACKEND=x11 evince file.pdf. See README.md's Wayland section.",
            frame_name,
        )

    def _probe_descendants_for_text(
        self, accessible: Any, x: int, y: int
    ) -> AccessibleTextInfo | None:
        """Look below a hit-test dead end for a text object at the point.

        Some applications report unusable Component extents on the objects
        that actually hold text -- Evince's page objects, for example,
        report page-unit sizes rather than screen pixels -- so the
        contains()-based descent in ``locate_accessible_at_point`` stops one
        level short of them. Their ``Text.get_offset_at_point`` still
        answers correctly in screen coordinates, so probe a bounded number
        of descendants and let that call (via ``_read_text``'s ``offset >=
        0`` check) decide whether the point is inside one of them.
        """
        visited = 0
        queue: list[tuple[Any, int]] = [(accessible, 0)]
        while queue and visited < self._PROBE_MAX_NODES:
            node, depth = queue.pop(0)
            visited += 1
            if node is not accessible:
                info = self._read_text(node, x, y)
                if info is not None:
                    return info
            if depth >= self._PROBE_MAX_DEPTH:
                continue
            try:
                child_count = node.get_child_count()
            except Exception:
                continue
            for index in range(child_count):
                try:
                    child = node.get_child_at_index(index)
                except Exception:
                    continue
                if child is not None:
                    queue.append((child, depth + 1))
        return None

    def _find_active_frame(self) -> Any | None:
        """Find the frame the user is currently focused on.

        The desktop can contain many open applications whose remembered
        window bounds happen to overlap the hover point (minimized
        windows, background windows, stacked windows) -- restricting the
        search to the active frame avoids extracting text from whatever
        application happens to be enumerated first, and also matches user
        intent: hovering should only ever act on the window being looked
        at. Empirically, AT-SPI's Component "layer"/"z-order" properties
        are not populated meaningfully by common toolkits in this
        environment, so STATE_ACTIVE is used instead.
        """
        atspi = self._atspi

        try:
            desktop = atspi.get_desktop(0)
        except Exception:
            logger.debug("Failed to fetch the AT-SPI desktop", exc_info=True)
            return None

        if desktop is None:
            return None

        try:
            app_count = desktop.get_child_count()
        except Exception:
            logger.debug("Failed to enumerate AT-SPI applications", exc_info=True)
            return None

        for app_index in range(app_count):
            try:
                app = desktop.get_child_at_index(app_index)
            except Exception:
                continue
            if app is None:
                continue

            try:
                frame_count = app.get_child_count()
            except Exception:
                continue

            for frame_index in range(frame_count):
                try:
                    frame = app.get_child_at_index(frame_index)
                    if frame is None:
                        continue
                    if frame.get_state_set().contains(atspi.StateType.ACTIVE):
                        return frame
                except Exception:
                    continue

        return None

    def _read_text(self, accessible: Any, x: int, y: int) -> AccessibleTextInfo | None:
        atspi = self._atspi

        try:
            if accessible.get_text_iface() is None:
                return None

            character_count = atspi.Text.get_character_count(accessible)
            if character_count <= 0:
                return None

            content = atspi.Text.get_text(accessible, 0, character_count)
            if not content:
                return None

            offset = atspi.Text.get_offset_at_point(accessible, x, y, atspi.CoordType.SCREEN)
            if offset < 0:
                return None

            return AccessibleTextInfo(text=content, offset=offset)
        except Exception:
            logger.debug("Failed to read accessible text", exc_info=True)
            return None


class _AtspiComponentAdapter:
    """Adapts an AT-SPI Component's unbound-function calling convention to
    the :class:`~yomikata.atspi.cursor.ComponentLike` protocol."""

    def __init__(self, component: Any, coord_type: Any, atspi_module: Any) -> None:
        self._component = component
        self._coord_type = coord_type
        self._atspi = atspi_module

    def contains(self, x: int, y: int) -> bool:
        return bool(self._atspi.Component.contains(self._component, x, y, self._coord_type))


class _AtspiAccessibleAdapter:
    """Adapts an AT-SPI Accessible to the
    :class:`~yomikata.atspi.cursor.AccessibleLike` protocol."""

    def __init__(self, accessible: Any, coord_type: Any, atspi_module: Any) -> None:
        self.accessible = accessible
        self._coord_type = coord_type
        self._atspi = atspi_module

    def get_component(self) -> ComponentLike | None:
        component = self.accessible.get_component_iface()
        if component is None:
            return None
        return _AtspiComponentAdapter(component, self._coord_type, self._atspi)

    def get_child_count(self) -> int:
        return int(self.accessible.get_child_count())

    def get_child_at_index(self, index: int) -> AccessibleLike | None:
        child = self.accessible.get_child_at_index(index)
        if child is None:
            return None
        return _AtspiAccessibleAdapter(child, self._coord_type, self._atspi)
