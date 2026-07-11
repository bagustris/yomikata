"""Tests for yomikata.util.session."""

from __future__ import annotations

from yomikata.util.session import is_wayland_session


def test_true_for_a_wayland_session() -> None:
    assert is_wayland_session({"XDG_SESSION_TYPE": "wayland"})


def test_normalizes_case_and_whitespace() -> None:
    assert is_wayland_session({"XDG_SESSION_TYPE": " Wayland "})


def test_false_for_an_x11_session() -> None:
    assert not is_wayland_session({"XDG_SESSION_TYPE": "x11"})


def test_false_when_the_variable_is_unset() -> None:
    assert not is_wayland_session({})
