"""Tests for yomikata.settings.window.

Only the pure/logical parts are unit tested here. The GTK/Adwaita widget
construction and application main loop are windowing-system glue that is
best verified by actually running the settings window on a live display,
not by mocking GTK/Adwaita internals.
"""

from __future__ import annotations

from yomikata.hover.pointer_source import MODIFIER_MASKS
from yomikata.util.config import HOVER_MODIFIER_NAMES, VALID_HOVER_MODIFIERS


def test_modifier_names_cover_every_mask_plus_none() -> None:
    assert set(HOVER_MODIFIER_NAMES) == set(MODIFIER_MASKS) | {"none"}


def test_valid_modifiers_match_the_display_names() -> None:
    assert frozenset(HOVER_MODIFIER_NAMES) == VALID_HOVER_MODIFIERS


def test_names_have_no_duplicates() -> None:
    assert len(HOVER_MODIFIER_NAMES) == len(set(HOVER_MODIFIER_NAMES))
