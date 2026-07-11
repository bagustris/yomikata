"""Hover token resolution.

Responsible only for determining which token, if any, a sentence-local
character offset falls within. Knows nothing about accessibility,
tokenization internals, or dictionaries.
"""

from __future__ import annotations

from collections.abc import Sequence

from yomikata.tokenizer.sudachi import Token


def resolve_hovered_token(tokens: Sequence[Token], offset: int) -> Token | None:
    """Find the token containing a sentence-local character offset.

    Args:
        tokens: Tokens produced from the sentence, in order, with offsets
            relative to that sentence.
        offset: Sentence-local character offset to resolve.

    Returns:
        The token whose [start_offset, end_offset) range contains
        ``offset``, or None if no token contains it.
    """
    for token in tokens:
        if token.start_offset <= offset < token.end_offset:
            return token
    return None
