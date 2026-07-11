"""Parsing and importing the KANJIDIC2 dictionary file.

Mirrors :mod:`yomikata.dictionary.jmdict`: streams the XML rather than
loading it whole, and turns each ``<character>`` into a storage-independent
:class:`~yomikata.dictionary.backend.KanjiEntry`.
"""

from __future__ import annotations

import logging
import sqlite3
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterator
from pathlib import Path

from yomikata.dictionary.backend import KanjiEntry
from yomikata.dictionary.sqlite import create_schema, insert_kanji_entries

logger = logging.getLogger(__name__)

_ON_READING_TYPE = "ja_on"
_KUN_READING_TYPE = "ja_kun"


def parse_kanjidic(path: Path) -> Iterator[KanjiEntry]:
    """Stream-parse a KANJIDIC2 XML file into kanji entries.

    Args:
        path: Path to the (decompressed) KANJIDIC2 XML file.

    Yields:
        One :class:`KanjiEntry` per ``<character>`` element, in file order.
    """
    for _event, element in ElementTree.iterparse(str(path), events=("end",)):
        if element.tag != "character":
            continue
        entry = _parse_character(element)
        element.clear()
        yield entry


def _parse_character(character_element: ElementTree.Element) -> KanjiEntry:
    literal = character_element.findtext("literal")
    if literal is None:
        raise ValueError("Missing required <literal> element")

    misc = character_element.find("misc")
    grade = _optional_int(misc, "grade")
    stroke_count = _optional_int(misc, "stroke_count")
    jlpt = _optional_int(misc, "jlpt")

    onyomi, kunyomi, meanings = _parse_readings_and_meanings(character_element)

    return KanjiEntry(
        character=literal,
        onyomi=onyomi,
        kunyomi=kunyomi,
        meanings=meanings,
        grade=grade,
        stroke_count=stroke_count,
        jlpt=jlpt,
    )


def _parse_readings_and_meanings(
    character_element: ElementTree.Element,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    onyomi: list[str] = []
    kunyomi: list[str] = []
    meanings: list[str] = []

    reading_meaning = character_element.find("reading_meaning")
    if reading_meaning is None:
        return (), (), ()

    for rmgroup in reading_meaning.findall("rmgroup"):
        for reading in rmgroup.findall("reading"):
            if reading.text is None:
                continue
            if reading.get("r_type") == _ON_READING_TYPE:
                onyomi.append(reading.text)
            elif reading.get("r_type") == _KUN_READING_TYPE:
                kunyomi.append(reading.text)

        for meaning in rmgroup.findall("meaning"):
            if meaning.text is not None and meaning.get("m_lang") is None:
                meanings.append(meaning.text)

    return tuple(onyomi), tuple(kunyomi), tuple(meanings)


def _optional_int(parent: ElementTree.Element | None, tag: str) -> int | None:
    if parent is None:
        return None
    text = parent.findtext(tag)
    return int(text) if text is not None else None


def build_kanji_database(kanjidic_path: Path, database_path: Path) -> int:
    """Add KANJIDIC2 data to a SQLite dictionary database.

    Unlike :func:`~yomikata.dictionary.jmdict.build_dictionary_database`,
    this does not delete an existing database first, so it can be used to
    add kanji data alongside JMdict data already imported into the same
    file.

    Args:
        kanjidic_path: Path to the (decompressed) KANJIDIC2 XML file.
        database_path: Path to the SQLite database to write into. Created
            if it does not already exist.

    Returns:
        The number of kanji imported.
    """
    connection = sqlite3.connect(database_path)
    try:
        create_schema(connection)
        count = insert_kanji_entries(connection, parse_kanjidic(kanjidic_path))
        logger.info("Imported %d KANJIDIC2 entries into %s", count, database_path)
        return count
    finally:
        connection.close()
