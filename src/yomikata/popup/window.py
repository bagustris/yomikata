"""A lightweight, always-on-top, non-focus-stealing popup window.

Positioning a window at an arbitrary global screen coordinate is not
possible through GTK4's native Wayland backend -- Wayland toplevels can
only be placed by the compositor, never the client. Forcing the X11
backend (served via XWayland on a Wayland session) restores the classic
X11 model, where an "override-redirect" window bypasses window-manager
placement and focus handling entirely and can be positioned with a raw
XConfigureWindow call. This is the same technique traditional X11
tooltip/OSD tools use. See PLAN.md's note on asking rather than assuming
about accessibility/windowing APIs -- this was verified empirically
against the real desktop session, not assumed from documentation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkX11", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402
from Xlib import X  # noqa: E402
from Xlib import display as xlib_display  # noqa: E402

from yomikata.popup.renderer import PopupContent, render_popup_content  # noqa: E402

logger = logging.getLogger(__name__)

_FADE_DURATION_MS = 150
_FADE_STEP_MS = 16
_CURSOR_OFFSET_X = 16
_CURSOR_OFFSET_Y = 16
_MAX_LAYOUT_WAIT_ITERATIONS = 50


def compute_popup_position(
    cursor_x: int,
    cursor_y: int,
    popup_width: int,
    popup_height: int,
    screen_width: int,
    screen_height: int,
    offset_x: int = _CURSOR_OFFSET_X,
    offset_y: int = _CURSOR_OFFSET_Y,
) -> tuple[int, int]:
    """Compute where to place a popup near the cursor without it leaving the screen.

    Prefers placing the popup below and to the right of the cursor (so it
    does not cover the text being hovered); flips to the opposite side of
    the cursor along each axis where it would otherwise overflow, then
    clamps to the screen as a last resort.

    Args:
        cursor_x: Cursor X position, in screen pixels.
        cursor_y: Cursor Y position, in screen pixels.
        popup_width: Width of the popup, in pixels.
        popup_height: Height of the popup, in pixels.
        screen_width: Width of the screen (or monitor) in pixels.
        screen_height: Height of the screen (or monitor) in pixels.
        offset_x: Horizontal gap to leave between the cursor and popup.
        offset_y: Vertical gap to leave between the cursor and popup.

    Returns:
        The (x, y) top-left position to place the popup at.
    """
    x = cursor_x + offset_x
    y = cursor_y + offset_y

    if x + popup_width > screen_width:
        x = cursor_x - offset_x - popup_width
    if y + popup_height > screen_height:
        y = cursor_y - offset_y - popup_height

    x = max(0, min(x, max(0, screen_width - popup_width)))
    y = max(0, min(y, max(0, screen_height - popup_height)))

    return x, y


class PopupWindow:
    """A hover popup: always on top, never focused, follows the cursor."""

    def __init__(
        self, content_renderer: Callable[[PopupContent], Gtk.Widget] = render_popup_content
    ) -> None:
        """Initialize the popup window (not shown until :meth:`show_at`).

        Args:
            content_renderer: Builds the widget tree for a
                :class:`~yomikata.popup.renderer.PopupContent`. Defaults to
                :func:`~yomikata.popup.renderer.render_popup_content`.
        """
        self._content_renderer = content_renderer

        self._window = Gtk.Window()
        self._window.set_decorated(False)
        self._window.set_resizable(False)
        self._window.set_focus_on_click(False)
        self._window.add_css_class("yomikata-popup-window")
        self._window.set_opacity(0.0)

        self._xlib_display = xlib_display.Display()
        self._x11_window: Any | None = None
        self._fade_source_id: int | None = None

        self._window.connect("realize", self._on_realize)

    def show_at(self, x: int, y: int, content: PopupContent) -> None:
        """Render content and show the popup positioned near (x, y).

        Args:
            x: Cursor X position to anchor the popup near, in screen pixels.
            y: Cursor Y position to anchor the popup near, in screen pixels.
            content: The data to render inside the popup.
        """
        self._window.set_child(self._content_renderer(content))

        if not self._window.get_realized():
            self._window.realize()

        self._window.present()
        popup_width, popup_height = self._measure()
        screen_width, screen_height = self._screen_size()
        target_x, target_y = compute_popup_position(
            x, y, popup_width, popup_height, screen_width, screen_height
        )
        self._move_to(target_x, target_y)
        self._fade_to(1.0)

    def hide(self) -> None:
        """Fade out and hide the popup."""
        self._fade_to(0.0, on_complete=lambda: self._window.set_visible(False))

    def close(self) -> None:
        """Destroy the popup window and release its resources."""
        if self._fade_source_id is not None:
            GLib.source_remove(self._fade_source_id)
            self._fade_source_id = None
        self._window.destroy()
        self._xlib_display.close()

    def _on_realize(self, _window: Gtk.Window) -> None:
        try:
            surface = self._window.get_surface()
            xid = surface.get_xid()
            x11_window = self._xlib_display.create_resource_object("window", xid)
            x11_window.change_attributes(override_redirect=1)
            self._xlib_display.sync()
            self._x11_window = x11_window
        except Exception:
            logger.warning(
                "Failed to configure popup as an override-redirect window", exc_info=True
            )

    def _measure(self) -> tuple[int, int]:
        context = GLib.MainContext.default()
        for _ in range(_MAX_LAYOUT_WAIT_ITERATIONS):
            width, height = self._window.get_width(), self._window.get_height()
            if width > 0 and height > 0:
                return width, height
            context.iteration(False)
        logger.debug("Popup size never became available; falling back to a default size")
        return 240, 120

    def _screen_size(self) -> tuple[int, int]:
        display = self._window.get_display()
        monitors = display.get_monitors()
        if monitors.get_n_items() == 0:
            return 1920, 1080
        geometry = monitors.get_item(0).get_geometry()
        return geometry.width, geometry.height

    def _move_to(self, x: int, y: int) -> None:
        if self._x11_window is None:
            logger.warning("Cannot position popup before its X11 window is realized")
            return
        self._x11_window.configure(x=x, y=y, stack_mode=X.Above)
        self._xlib_display.sync()

    def _fade_to(
        self, target_opacity: float, on_complete: Callable[[], None] | None = None
    ) -> None:
        if self._fade_source_id is not None:
            GLib.source_remove(self._fade_source_id)
            self._fade_source_id = None

        start_opacity = self._window.get_opacity()
        total_steps = max(1, _FADE_DURATION_MS // _FADE_STEP_MS)
        delta = (target_opacity - start_opacity) / total_steps
        step_count = 0

        def tick() -> bool:
            nonlocal step_count
            step_count += 1
            if step_count >= total_steps:
                self._window.set_opacity(target_opacity)
                self._fade_source_id = None
                if on_complete is not None:
                    on_complete()
                return False
            self._window.set_opacity(start_opacity + delta * step_count)
            return True

        self._fade_source_id = GLib.timeout_add(_FADE_STEP_MS, tick)
