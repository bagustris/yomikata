"""Wires the hover pipeline stages together.

Connects hover -> AT-SPI -> sentence -> tokenizer -> dictionary -> popup.
Each stage remains independently testable and replaceable; this module's
only job is to call them in order and handle each stage returning nothing
to show (never a crash).
"""

from __future__ import annotations

import logging
from typing import Protocol

from yomikata.atspi.extractor import AccessibilityExtractor
from yomikata.dictionary.backend import DictionaryBackend
from yomikata.hover.monitor import HoverEvent
from yomikata.popup.renderer import PopupContent
from yomikata.resolution.resolver import resolve_hovered_token
from yomikata.sentence.extractor import extract_sentence
from yomikata.tokenizer.conjugation import describe_conjugation
from yomikata.tokenizer.sudachi import SudachiTokenizer

logger = logging.getLogger(__name__)


class PopupDisplay(Protocol):
    """The subset of :class:`~yomikata.popup.window.PopupWindow` the
    pipeline needs. Lets tests use a lightweight fake instead of a real
    GTK4/X11 window."""

    def show_at(self, x: int, y: int, content: PopupContent) -> None:
        """Render content and show the popup positioned near (x, y)."""
        ...

    def hide(self) -> None:
        """Hide the popup."""
        ...

    def close(self) -> None:
        """Release resources held by the popup."""
        ...


class HoverPipeline:
    """Turns a hover event into a populated, positioned popup (or hides it)."""

    def __init__(
        self,
        accessibility_extractor: AccessibilityExtractor,
        tokenizer: SudachiTokenizer,
        dictionary_backend: DictionaryBackend,
        popup: PopupDisplay,
    ) -> None:
        """Initialize the pipeline.

        Args:
            accessibility_extractor: Reads accessible text under the cursor.
            tokenizer: Splits the surrounding sentence into tokens.
            dictionary_backend: Looks up word and kanji reference data.
            popup: Displays (or hides) the result.
        """
        self._accessibility_extractor = accessibility_extractor
        self._tokenizer = tokenizer
        self._dictionary_backend = dictionary_backend
        self._popup = popup

    def on_hover(self, event: HoverEvent) -> None:
        """Handle a single hover event.

        Runs the full pipeline for the hovered screen position. Any stage
        that finds nothing hides the popup and stops; this method never
        raises, matching the rest of the application's "never crash on a
        single hover" contract.

        Args:
            event: The hover event to handle.
        """
        try:
            self._handle(event)
        except Exception:
            logger.warning("Hover pipeline failed unexpectedly", exc_info=True)
            self._popup.hide()

    def close(self) -> None:
        """Release resources held by the pipeline's stages."""
        self._dictionary_backend.close()
        self._popup.close()

    def _handle(self, event: HoverEvent) -> None:
        text_info = self._accessibility_extractor.extract(event.x, event.y)
        if text_info is None:
            self._popup.hide()
            return

        sentence_result = extract_sentence(text_info.text, text_info.offset)
        if not sentence_result.sentence:
            self._popup.hide()
            return

        tokens = self._tokenizer.tokenize(sentence_result.sentence)
        local_offset = text_info.offset - sentence_result.start_offset
        token = resolve_hovered_token(tokens, local_offset)
        if token is None:
            self._popup.hide()
            return

        # Only describe the surface as a conjugation when the entries shown
        # actually came from the dictionary-form fallback (or nothing was
        # found at all). When the surface itself is a headword (e.g. 行き
        # as the noun "bound for"), the entries describe the surface, and
        # a "form of 行く" note would mislabel them.
        entries = self._dictionary_backend.lookup(token.surface)
        conjugation_note = None
        if not entries:
            conjugation_note = describe_conjugation(token)
            if token.dictionary_form != token.surface:
                entries = self._dictionary_backend.lookup(token.dictionary_form)

        kanji_entries = tuple(
            kanji_entry
            for character in dict.fromkeys(token.surface)
            if (kanji_entry := self._dictionary_backend.lookup_kanji(character)) is not None
        )

        content = PopupContent(
            surface=token.surface,
            reading=token.reading,
            entries=tuple(entries),
            kanji=kanji_entries,
            conjugation_note=conjugation_note,
        )
        self._popup.show_at(event.x, event.y, content)
