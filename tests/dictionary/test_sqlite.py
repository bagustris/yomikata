"""Tests for yomikata.dictionary.sqlite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from yomikata.dictionary.backend import DictionaryEntry, KanjiEntry, Sense
from yomikata.dictionary.sqlite import (
    SqliteDictionaryBackend,
    create_schema,
    insert_entries,
    insert_kanji_entries,
)

CAT_KANJI_ENTRY = KanjiEntry(
    character="猫",
    onyomi=("ビョウ",),
    kunyomi=("ねこ",),
    meanings=("cat",),
    grade=None,
    stroke_count=11,
    jlpt=1,
)

CAT_ENTRY = DictionaryEntry(
    entry_id=1,
    kanji_forms=("猫",),
    readings=("ねこ",),
    senses=(Sense(parts_of_speech=("noun",), glosses=("cat", "feline")),),
)

MULTI_SENSE_ENTRY = DictionaryEntry(
    entry_id=2,
    kanji_forms=("彼処", "彼所"),
    readings=("あそこ", "あすこ"),
    senses=(
        Sense(parts_of_speech=("pronoun",), glosses=("there", "over there")),
        Sense(parts_of_speech=("noun",), glosses=("genitals",)),
    ),
)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "dictionary.sqlite3"
    connection = sqlite3.connect(path)
    try:
        create_schema(connection)
        insert_entries(connection, [CAT_ENTRY, MULTI_SENSE_ENTRY])
    finally:
        connection.close()
    return path


def test_lookup_by_kanji_form(database_path: Path) -> None:
    with SqliteDictionaryBackend(database_path) as backend:
        results = backend.lookup("猫")

    assert results == [CAT_ENTRY]


def test_lookup_by_reading(database_path: Path) -> None:
    with SqliteDictionaryBackend(database_path) as backend:
        results = backend.lookup("ねこ")

    assert results == [CAT_ENTRY]


def test_lookup_preserves_multiple_kanji_forms_readings_and_senses(database_path: Path) -> None:
    with SqliteDictionaryBackend(database_path) as backend:
        results = backend.lookup("あそこ")

    assert results == [MULTI_SENSE_ENTRY]


def test_lookup_with_no_match_returns_empty_list(database_path: Path) -> None:
    with SqliteDictionaryBackend(database_path) as backend:
        results = backend.lookup("存在しない言葉")

    assert results == []


def test_lookup_on_a_backend_pointed_at_a_missing_database_returns_empty_list(
    tmp_path: Path,
) -> None:
    backend = SqliteDictionaryBackend(tmp_path / "does_not_exist.sqlite3")

    try:
        assert backend.lookup("猫") == []
    finally:
        backend.close()


def test_insert_entries_returns_the_number_inserted(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "count.sqlite3")
    try:
        create_schema(connection)
        count = insert_entries(connection, [CAT_ENTRY, MULTI_SENSE_ENTRY])
    finally:
        connection.close()

    assert count == 2


def test_create_schema_is_idempotent(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "idempotent.sqlite3")
    try:
        create_schema(connection)
        create_schema(connection)
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("kanji_forms", "text"),
        ("kanji_forms", "entry_id"),
        ("readings", "text"),
        ("readings", "entry_id"),
        ("senses", "entry_id"),
        ("glosses", "sense_id"),
        ("kanji_on_readings", "character"),
        ("kanji_kun_readings", "character"),
        ("kanji_meanings", "character"),
    ],
)
def test_schema_indexes_every_column_used_in_a_where_clause(
    tmp_path: Path, table: str, column: str
) -> None:
    """Every WHERE-clause column must be indexed, or lookups degrade to a
    full table scan once the dictionary is populated with real JMdict data
    (~200k rows) -- the small fixtures elsewhere in this file are too tiny
    for a missing index to show up as a test failure on its own.
    """
    connection = sqlite3.connect(tmp_path / "index_check.sqlite3")
    try:
        create_schema(connection)
        indexed_columns = {
            info_row[2]
            for index_row in connection.execute(f"PRAGMA index_list({table})")
            for info_row in connection.execute(f"PRAGMA index_info({index_row[1]})")
        }
    finally:
        connection.close()

    assert column in indexed_columns, f"{table}.{column} is queried but not indexed"


@pytest.fixture
def kanji_database_path(tmp_path: Path) -> Path:
    path = tmp_path / "kanji.sqlite3"
    connection = sqlite3.connect(path)
    try:
        create_schema(connection)
        insert_kanji_entries(connection, [CAT_KANJI_ENTRY])
    finally:
        connection.close()
    return path


def test_lookup_kanji_returns_full_entry(kanji_database_path: Path) -> None:
    with SqliteDictionaryBackend(kanji_database_path) as backend:
        result = backend.lookup_kanji("猫")

    assert result == CAT_KANJI_ENTRY


def test_lookup_kanji_with_no_match_returns_none(kanji_database_path: Path) -> None:
    with SqliteDictionaryBackend(kanji_database_path) as backend:
        assert backend.lookup_kanji("犬") is None


def test_lookup_kanji_on_missing_database_returns_none(tmp_path: Path) -> None:
    backend = SqliteDictionaryBackend(tmp_path / "does_not_exist.sqlite3")

    try:
        assert backend.lookup_kanji("猫") is None
    finally:
        backend.close()


def test_insert_kanji_entries_returns_the_number_inserted(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "kanji_count.sqlite3")
    try:
        create_schema(connection)
        count = insert_kanji_entries(connection, [CAT_KANJI_ENTRY])
    finally:
        connection.close()

    assert count == 1
