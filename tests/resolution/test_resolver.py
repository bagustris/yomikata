"""Tests for yomikata.resolution.resolver."""

from __future__ import annotations

from yomikata.resolution.resolver import resolve_hovered_token
from yomikata.tokenizer.sudachi import Token


def make_token(surface: str, start_offset: int, end_offset: int) -> Token:
    return Token(
        surface=surface,
        reading=surface,
        dictionary_form=surface,
        part_of_speech=("*",),
        start_offset=start_offset,
        end_offset=end_offset,
    )


TOKENS = [
    make_token("東京", 0, 2),
    make_token("に", 2, 3),
    make_token("行く", 3, 5),
]


def test_resolves_offset_at_start_of_a_token() -> None:
    assert resolve_hovered_token(TOKENS, 0) == TOKENS[0]


def test_resolves_offset_in_the_middle_of_a_token() -> None:
    assert resolve_hovered_token(TOKENS, 4) == TOKENS[2]


def test_offset_at_token_boundary_resolves_to_the_following_token() -> None:
    assert resolve_hovered_token(TOKENS, 2) == TOKENS[1]


def test_offset_past_the_last_token_returns_none() -> None:
    assert resolve_hovered_token(TOKENS, 5) is None


def test_negative_offset_returns_none() -> None:
    assert resolve_hovered_token(TOKENS, -1) is None


def test_empty_token_list_returns_none() -> None:
    assert resolve_hovered_token([], 0) is None


def test_gap_between_non_contiguous_tokens_returns_none() -> None:
    tokens = [make_token("文", 0, 1), make_token("字", 5, 6)]

    assert resolve_hovered_token(tokens, 3) is None
