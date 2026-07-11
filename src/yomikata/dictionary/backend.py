"""Dictionary lookup abstraction.

Defines the storage-independent shape of dictionary data and the interface
callers use to look it up. Concrete storage (SQLite today, potentially
something else later) lives in sibling modules and must never leak through
this abstraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Sense:
    """A single meaning of a dictionary entry.

    Attributes:
        parts_of_speech: Part-of-speech labels for this sense, e.g.
            ``("noun (common) (futsuumeishi)",)``.
        glosses: Meanings/translations for this sense, in priority order.
    """

    parts_of_speech: tuple[str, ...]
    glosses: tuple[str, ...]


@dataclass(frozen=True)
class DictionaryEntry:
    """A single dictionary entry.

    Attributes:
        entry_id: Unique identifier for the entry (JMdict's ``ent_seq``).
        kanji_forms: Kanji/orthographic spellings of the word, if any.
        readings: Kana readings of the word.
        senses: Meanings, in priority order.
    """

    entry_id: int
    kanji_forms: tuple[str, ...]
    readings: tuple[str, ...]
    senses: tuple[Sense, ...]


@dataclass(frozen=True)
class KanjiEntry:
    """Reference information for a single kanji character, from KANJIDIC2.

    Attributes:
        character: The kanji character itself.
        onyomi: On (Chinese-derived) readings.
        kunyomi: Kun (native Japanese) readings.
        meanings: English meanings.
        grade: Kyouiku/Jouyou school grade level, or None if the kanji is
            not taught at a specific grade.
        stroke_count: Number of strokes.
        jlpt: Former JLPT level (1-4), or None if unranked.
    """

    character: str
    onyomi: tuple[str, ...]
    kunyomi: tuple[str, ...]
    meanings: tuple[str, ...]
    grade: int | None
    stroke_count: int | None
    jlpt: int | None


class DictionaryBackend(Protocol):
    """Looks up word entries and kanji reference data."""

    def lookup(self, headword: str) -> list[DictionaryEntry]:
        """Return all entries whose kanji form or reading is ``headword``.

        Args:
            headword: Exact kanji spelling or kana reading to look up.

        Returns:
            Matching entries, or an empty list if none are found.
        """
        ...

    def lookup_kanji(self, character: str) -> KanjiEntry | None:
        """Return reference data for a single kanji character.

        Args:
            character: A single kanji character.

        Returns:
            The kanji's reference data, or None if it is not in KANJIDIC2.
        """
        ...

    def close(self) -> None:
        """Release any resources held by the backend."""
        ...
