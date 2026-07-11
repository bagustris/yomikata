"""SQLite-backed dictionary storage.

This is the only module allowed to know SQLite is involved. Everything
outside the ``dictionary`` package talks to
:class:`~yomikata.dictionary.backend.DictionaryBackend` instead.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from yomikata.dictionary.backend import DictionaryEntry, KanjiEntry, Sense

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS kanji_forms (
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kanji_forms_text ON kanji_forms(text);
CREATE INDEX IF NOT EXISTS idx_kanji_forms_entry_id ON kanji_forms(entry_id);

CREATE TABLE IF NOT EXISTS readings (
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_text ON readings(text);
CREATE INDEX IF NOT EXISTS idx_readings_entry_id ON readings(entry_id);

CREATE TABLE IF NOT EXISTS senses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    sense_order INTEGER NOT NULL,
    parts_of_speech TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_senses_entry_id ON senses(entry_id);

CREATE TABLE IF NOT EXISTS glosses (
    sense_id INTEGER NOT NULL REFERENCES senses(id),
    gloss_order INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_glosses_sense_id ON glosses(sense_id);

CREATE TABLE IF NOT EXISTS kanji (
    character TEXT PRIMARY KEY,
    grade INTEGER,
    stroke_count INTEGER,
    jlpt INTEGER
);

CREATE TABLE IF NOT EXISTS kanji_on_readings (
    character TEXT NOT NULL REFERENCES kanji(character),
    reading_order INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kanji_on_readings_character ON kanji_on_readings(character);

CREATE TABLE IF NOT EXISTS kanji_kun_readings (
    character TEXT NOT NULL REFERENCES kanji(character),
    reading_order INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kanji_kun_readings_character ON kanji_kun_readings(character);

CREATE TABLE IF NOT EXISTS kanji_meanings (
    character TEXT NOT NULL REFERENCES kanji(character),
    meaning_order INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kanji_meanings_character ON kanji_meanings(character);
"""


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the dictionary schema if it does not already exist."""
    connection.executescript(_SCHEMA_SQL)


def insert_entries(connection: sqlite3.Connection, entries: Iterable[DictionaryEntry]) -> int:
    """Insert entries into an already-schema'd database.

    All inserts happen in a single transaction for import speed.

    Args:
        connection: An open connection with the schema already created.
        entries: Entries to insert.

    Returns:
        The number of entries inserted.
    """
    count = 0
    with connection:
        for entry in entries:
            _insert_entry(connection, entry)
            count += 1
    return count


def _insert_entry(connection: sqlite3.Connection, entry: DictionaryEntry) -> None:
    connection.execute("INSERT INTO entries (id) VALUES (?)", (entry.entry_id,))

    connection.executemany(
        "INSERT INTO kanji_forms (entry_id, text) VALUES (?, ?)",
        [(entry.entry_id, kanji) for kanji in entry.kanji_forms],
    )
    connection.executemany(
        "INSERT INTO readings (entry_id, text) VALUES (?, ?)",
        [(entry.entry_id, reading) for reading in entry.readings],
    )

    for sense_order, sense in enumerate(entry.senses):
        cursor = connection.execute(
            "INSERT INTO senses (entry_id, sense_order, parts_of_speech) VALUES (?, ?, ?)",
            (entry.entry_id, sense_order, json.dumps(sense.parts_of_speech)),
        )
        sense_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO glosses (sense_id, gloss_order, text) VALUES (?, ?, ?)",
            [(sense_id, gloss_order, gloss) for gloss_order, gloss in enumerate(sense.glosses)],
        )


def insert_kanji_entries(connection: sqlite3.Connection, entries: Iterable[KanjiEntry]) -> int:
    """Insert kanji entries into an already-schema'd database.

    All inserts happen in a single transaction for import speed.

    Args:
        connection: An open connection with the schema already created.
        entries: Kanji entries to insert.

    Returns:
        The number of kanji inserted.
    """
    count = 0
    with connection:
        for entry in entries:
            _insert_kanji_entry(connection, entry)
            count += 1
    return count


def _insert_kanji_entry(connection: sqlite3.Connection, entry: KanjiEntry) -> None:
    connection.execute(
        "INSERT INTO kanji (character, grade, stroke_count, jlpt) VALUES (?, ?, ?, ?)",
        (entry.character, entry.grade, entry.stroke_count, entry.jlpt),
    )
    connection.executemany(
        "INSERT INTO kanji_on_readings (character, reading_order, text) VALUES (?, ?, ?)",
        [(entry.character, order, reading) for order, reading in enumerate(entry.onyomi)],
    )
    connection.executemany(
        "INSERT INTO kanji_kun_readings (character, reading_order, text) VALUES (?, ?, ?)",
        [(entry.character, order, reading) for order, reading in enumerate(entry.kunyomi)],
    )
    connection.executemany(
        "INSERT INTO kanji_meanings (character, meaning_order, text) VALUES (?, ?, ?)",
        [(entry.character, order, meaning) for order, meaning in enumerate(entry.meanings)],
    )


class SqliteDictionaryBackend:
    """Looks up word entries and kanji reference data in a SQLite database
    built by :mod:`jmdict` and :mod:`kanjidic`."""

    def __init__(self, database_path: Path) -> None:
        """Open a dictionary database.

        Args:
            database_path: Path to a SQLite database built with
                :func:`~yomikata.dictionary.jmdict.build_dictionary_database`
                and/or
                :func:`~yomikata.dictionary.kanjidic.build_kanji_database`.
        """
        self._connection = sqlite3.connect(database_path)

    def lookup(self, headword: str) -> list[DictionaryEntry]:
        """Return all entries whose kanji form or reading is ``headword``."""
        try:
            entry_ids = self._find_matching_entry_ids(headword)
            if not entry_ids:
                return []
            return self._fetch_entries(entry_ids)
        except sqlite3.Error:
            logger.warning("Dictionary lookup failed for %r", headword, exc_info=True)
            return []

    def lookup_kanji(self, character: str) -> KanjiEntry | None:
        """Return reference data for a single kanji character."""
        try:
            row = self._connection.execute(
                "SELECT grade, stroke_count, jlpt FROM kanji WHERE character = ?",
                (character,),
            ).fetchone()
            if row is None:
                return None

            grade, stroke_count, jlpt = row
            return KanjiEntry(
                character=character,
                onyomi=tuple(
                    self._fetch_ordered_texts(
                        "SELECT text FROM kanji_on_readings "
                        "WHERE character = ? ORDER BY reading_order",
                        character,
                    )
                ),
                kunyomi=tuple(
                    self._fetch_ordered_texts(
                        "SELECT text FROM kanji_kun_readings "
                        "WHERE character = ? ORDER BY reading_order",
                        character,
                    )
                ),
                meanings=tuple(
                    self._fetch_ordered_texts(
                        "SELECT text FROM kanji_meanings "
                        "WHERE character = ? ORDER BY meaning_order",
                        character,
                    )
                ),
                grade=grade,
                stroke_count=stroke_count,
                jlpt=jlpt,
            )
        except sqlite3.Error:
            logger.warning("Kanji lookup failed for %r", character, exc_info=True)
            return None

    def _fetch_ordered_texts(self, query: str, character: str) -> list[str]:
        return [row[0] for row in self._connection.execute(query, (character,))]

    def close(self) -> None:
        """Close the underlying database connection."""
        self._connection.close()

    def __enter__(self) -> SqliteDictionaryBackend:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def _find_matching_entry_ids(self, headword: str) -> list[int]:
        cursor = self._connection.execute(
            "SELECT entry_id FROM kanji_forms WHERE text = ? "
            "UNION SELECT entry_id FROM readings WHERE text = ?",
            (headword, headword),
        )
        return [row[0] for row in cursor.fetchall()]

    def _fetch_entries(self, entry_ids: Sequence[int]) -> list[DictionaryEntry]:
        kanji_by_entry = self._select_grouped(
            "SELECT entry_id, text FROM kanji_forms WHERE entry_id IN ({placeholders})",
            entry_ids,
        )
        readings_by_entry = self._select_grouped(
            "SELECT entry_id, text FROM readings WHERE entry_id IN ({placeholders})",
            entry_ids,
        )
        senses_by_entry = self._fetch_senses(entry_ids)

        return [
            DictionaryEntry(
                entry_id=entry_id,
                kanji_forms=tuple(kanji_by_entry.get(entry_id, [])),
                readings=tuple(readings_by_entry.get(entry_id, [])),
                senses=tuple(senses_by_entry.get(entry_id, [])),
            )
            for entry_id in entry_ids
        ]

    def _fetch_senses(self, entry_ids: Sequence[int]) -> dict[int, list[Sense]]:
        placeholders = ",".join("?" * len(entry_ids))
        sense_rows = self._connection.execute(
            "SELECT id, entry_id, parts_of_speech FROM senses "
            f"WHERE entry_id IN ({placeholders}) ORDER BY entry_id, sense_order",
            list(entry_ids),
        ).fetchall()

        sense_ids = [row[0] for row in sense_rows]
        glosses_by_sense = self._select_grouped(
            "SELECT sense_id, text FROM glosses WHERE sense_id IN ({placeholders})",
            sense_ids,
        )

        senses_by_entry: dict[int, list[Sense]] = defaultdict(list)
        for sense_id, entry_id, parts_of_speech_json in sense_rows:
            senses_by_entry[entry_id].append(
                Sense(
                    parts_of_speech=tuple(json.loads(parts_of_speech_json)),
                    glosses=tuple(glosses_by_sense.get(sense_id, [])),
                )
            )
        return senses_by_entry

    def _select_grouped(self, query_template: str, ids: Sequence[int]) -> dict[int, list[str]]:
        """Run a "SELECT key, text ... WHERE key IN (...)"-shaped query, grouped by key.

        ``query_template`` must be a trusted, hardcoded literal (it is
        formatted with only a placeholder count, never external input).
        """
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        query = query_template.format(placeholders=placeholders)
        result: dict[int, list[str]] = defaultdict(list)
        for key, text in self._connection.execute(query, list(ids)):
            result[key].append(text)
        return result
