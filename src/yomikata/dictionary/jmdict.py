"""Parsing and importing the JMdict dictionary file.

JMdict is distributed as a large XML file (one ``<entry>`` per word). This
module streams it with :func:`xml.etree.ElementTree.iterparse` rather than
loading the whole document, since the uncompressed file is tens of
megabytes, and turns each entry into a storage-independent
:class:`~yomikata.dictionary.backend.DictionaryEntry`.
"""

from __future__ import annotations

import logging
import sqlite3
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterator
from pathlib import Path

from yomikata.dictionary.backend import DictionaryEntry, Sense
from yomikata.dictionary.sqlite import create_schema, insert_entries

logger = logging.getLogger(__name__)

_ENGLISH_GLOSS_LANG_ATTRIBUTE = "{http://www.w3.org/XML/1998/namespace}lang"


def parse_jmdict(path: Path) -> Iterator[DictionaryEntry]:
    """Stream-parse a JMdict XML file into dictionary entries.

    Args:
        path: Path to the (decompressed) JMdict XML file.

    Yields:
        One :class:`DictionaryEntry` per ``<entry>`` element, in file order.
    """
    for _event, element in ElementTree.iterparse(str(path), events=("end",)):
        if element.tag != "entry":
            continue
        entry = _parse_entry(element)
        element.clear()
        yield entry


def _parse_entry(entry_element: ElementTree.Element) -> DictionaryEntry:
    entry_id = int(_require_text(entry_element, "ent_seq"))

    kanji_forms = tuple(_require_text(k_ele, "keb") for k_ele in entry_element.findall("k_ele"))
    readings = tuple(_require_text(r_ele, "reb") for r_ele in entry_element.findall("r_ele"))
    senses = tuple(_parse_sense(sense_element) for sense_element in entry_element.findall("sense"))

    return DictionaryEntry(
        entry_id=entry_id, kanji_forms=kanji_forms, readings=readings, senses=senses
    )


def _parse_sense(sense_element: ElementTree.Element) -> Sense:
    parts_of_speech = tuple(
        pos.text for pos in sense_element.findall("pos") if pos.text is not None
    )
    glosses = tuple(
        gloss.text
        for gloss in sense_element.findall("gloss")
        if gloss.text is not None and _is_english_gloss(gloss)
    )
    return Sense(parts_of_speech=parts_of_speech, glosses=glosses)


def _is_english_gloss(gloss_element: ElementTree.Element) -> bool:
    lang = gloss_element.get(_ENGLISH_GLOSS_LANG_ATTRIBUTE)
    return lang is None or lang == "eng"


def _require_text(parent: ElementTree.Element, tag: str) -> str:
    text = parent.findtext(tag)
    if text is None:
        raise ValueError(f"Missing required <{tag}> element")
    return text


def build_dictionary_database(jmdict_path: Path, database_path: Path) -> int:
    """Build a SQLite dictionary database from a JMdict XML file.

    Args:
        jmdict_path: Path to the (decompressed) JMdict XML file.
        database_path: Path to write the SQLite database to. Overwritten if
            it already exists.

    Returns:
        The number of entries imported.
    """
    database_path.unlink(missing_ok=True)

    connection = sqlite3.connect(database_path)
    try:
        create_schema(connection)
        count = insert_entries(connection, parse_jmdict(jmdict_path))
        logger.info("Imported %d JMdict entries into %s", count, database_path)
        return count
    finally:
        connection.close()
