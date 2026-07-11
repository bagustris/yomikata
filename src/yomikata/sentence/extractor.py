"""Sentence extraction around a character offset.

Responsible only for finding the sentence surrounding a given offset in a
block of text. Knows nothing about accessibility, tokenization, or
dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass

_SENTENCE_BOUNDARIES = frozenset("。！？\n")


@dataclass(frozen=True)
class SentenceExtractionResult:
    """A sentence found around a character offset.

    Attributes:
        sentence: The extracted sentence, including its terminating
            delimiter (if any).
        start_offset: Index into the original text where ``sentence``
            begins.
    """

    sentence: str
    start_offset: int


def extract_sentence(text: str, offset: int) -> SentenceExtractionResult:
    """Extract the sentence surrounding a character offset.

    The sentence boundary is any of ``。``, ``！``, ``？``, or a newline. A
    boundary character is considered part of the sentence it closes, so an
    offset that lands exactly on one still resolves to the preceding
    sentence rather than the following one.

    Args:
        text: The text to search within.
        offset: Character offset to find the surrounding sentence for. Out
            of range values are clamped rather than raising.

    Returns:
        The surrounding sentence and its start offset within ``text``.
    """
    if not text:
        return SentenceExtractionResult(sentence="", start_offset=0)

    clamped_offset = max(0, min(offset, len(text) - 1))

    start = clamped_offset
    while start > 0 and text[start - 1] not in _SENTENCE_BOUNDARIES:
        start -= 1

    end = clamped_offset
    while end < len(text) and text[end] not in _SENTENCE_BOUNDARIES:
        end += 1
    if end < len(text):
        end += 1  # include the boundary character itself

    return SentenceExtractionResult(sentence=text[start:end], start_offset=start)
