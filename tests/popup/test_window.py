"""Tests for yomikata.popup.window.

Only the pure positioning math is unit tested here. Everything else in
this module (GTK window creation, X11 override-redirect setup, fade
animation) is windowing-system glue that is best verified by actually
running the popup on a live display, not by mocking GTK/Xlib internals.
"""

from __future__ import annotations

from yomikata.popup.window import compute_popup_position


def test_places_popup_below_and_right_of_cursor_by_default() -> None:
    x, y = compute_popup_position(
        cursor_x=100,
        cursor_y=100,
        popup_width=200,
        popup_height=80,
        screen_width=1920,
        screen_height=1080,
        offset_x=16,
        offset_y=16,
    )

    assert x == 116
    assert y == 116


def test_flips_horizontally_when_it_would_overflow_the_right_edge() -> None:
    x, _y = compute_popup_position(
        cursor_x=1850,
        cursor_y=100,
        popup_width=200,
        popup_height=80,
        screen_width=1920,
        screen_height=1080,
        offset_x=16,
        offset_y=16,
    )

    assert x == 1850 - 16 - 200
    assert x + 200 <= 1920


def test_flips_vertically_when_it_would_overflow_the_bottom_edge() -> None:
    _x, y = compute_popup_position(
        cursor_x=100,
        cursor_y=1050,
        popup_width=200,
        popup_height=80,
        screen_width=1920,
        screen_height=1080,
        offset_x=16,
        offset_y=16,
    )

    assert y == 1050 - 16 - 80
    assert y + 80 <= 1080


def test_clamps_to_screen_when_popup_is_wider_than_available_space() -> None:
    x, y = compute_popup_position(
        cursor_x=10,
        cursor_y=10,
        popup_width=2000,
        popup_height=80,
        screen_width=1920,
        screen_height=1080,
    )

    assert x == 0
    assert y >= 0


def test_never_places_popup_at_negative_coordinates() -> None:
    x, y = compute_popup_position(
        cursor_x=0,
        cursor_y=0,
        popup_width=200,
        popup_height=80,
        screen_width=1920,
        screen_height=1080,
        offset_x=16,
        offset_y=16,
    )

    assert x >= 0
    assert y >= 0
