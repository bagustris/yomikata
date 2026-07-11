"""Japanese tokenization via SudachiPy.

Responsible only for splitting a sentence into tokens. Knows nothing about
hover resolution, dictionaries, or rendering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sudachipy import Dictionary, SplitMode
from sudachipy import Tokenizer as SudachiRawTokenizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Token:
    """A single tokenized unit of Japanese text.

    Attributes:
        surface: The token exactly as it appears in the source text.
        reading: Katakana reading of the token.
        dictionary_form: The token's dictionary (lemma) form.
        part_of_speech: Sudachi's part-of-speech tags, most general first.
        start_offset: Character offset where the token begins in the
            original text.
        end_offset: Character offset where the token ends (exclusive).
    """

    surface: str
    reading: str
    dictionary_form: str
    part_of_speech: tuple[str, ...]
    start_offset: int
    end_offset: int


class SudachiTokenizer:
    """Tokenizes Japanese text into :class:`Token` objects using Sudachi."""

    def __init__(
        self,
        split_mode: SplitMode = SplitMode.C,
        raw_tokenizer: SudachiRawTokenizer | None = None,
    ) -> None:
        """Initialize the tokenizer.

        Args:
            split_mode: Sudachi segmentation granularity. Mode C (the
                coarsest) groups compounds like proper nouns and inflected
                verbs into single tokens, which best matches hovering over
                a whole perceived "word". Mode A gives finer, morpheme-level
                splits for grammar-focused use cases.
            raw_tokenizer: The underlying SudachiPy tokenizer. Defaults to
                one built from the bundled core dictionary; injectable for
                testing failure handling.
        """
        self._split_mode = split_mode
        self._raw_tokenizer = raw_tokenizer or Dictionary().create()

    def tokenize(self, text: str) -> list[Token]:
        """Tokenize a sentence.

        Args:
            text: The sentence to tokenize.

        Returns:
            Tokens in order, or an empty list if tokenization fails.
        """
        if not text:
            return []

        try:
            morphemes = self._raw_tokenizer.tokenize(text, self._split_mode)
        except Exception:
            logger.warning("Sudachi failed to tokenize text", exc_info=True)
            return []

        return [
            Token(
                surface=morpheme.surface(),
                reading=morpheme.reading_form(),
                dictionary_form=morpheme.dictionary_form(),
                part_of_speech=tuple(morpheme.part_of_speech()),
                start_offset=morpheme.begin(),
                end_offset=morpheme.end(),
            )
            for morpheme in morphemes
        ]
