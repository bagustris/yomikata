"""Tests for yomikata.dictionary.jmdict."""

from __future__ import annotations

from pathlib import Path

import pytest

from yomikata.dictionary.backend import DictionaryEntry, Sense
from yomikata.dictionary.jmdict import build_dictionary_database, parse_jmdict
from yomikata.dictionary.sqlite import SqliteDictionaryBackend

_SAMPLE_JMDICT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE JMdict [
<!ENTITY n "noun (common) (futsuumeishi)">
<!ENTITY v5r "Godan verb with 'ru' ending">
]>
<JMdict>
<entry>
<ent_seq>1000000</ent_seq>
<k_ele>
<keb>猫</keb>
</k_ele>
<r_ele>
<reb>ねこ</reb>
</r_ele>
<sense>
<pos>&n;</pos>
<gloss xml:lang="eng">cat</gloss>
<gloss xml:lang="eng">feline</gloss>
</sense>
</entry>
<entry>
<ent_seq>1000001</ent_seq>
<r_ele>
<reb>あそこ</reb>
</r_ele>
<sense>
<pos>&n;</pos>
<gloss xml:lang="fre">chat</gloss>
</sense>
<sense>
<pos>&v5r;</pos>
<gloss xml:lang="eng">over there</gloss>
</sense>
</entry>
</JMdict>
"""


@pytest.fixture
def sample_jmdict_path(tmp_path: Path) -> Path:
    path = tmp_path / "sample_jmdict.xml"
    path.write_text(_SAMPLE_JMDICT_XML, encoding="utf-8")
    return path


def test_parses_all_entries_in_document_order(sample_jmdict_path: Path) -> None:
    entries = list(parse_jmdict(sample_jmdict_path))

    assert [entry.entry_id for entry in entries] == [1000000, 1000001]


def test_parses_kanji_readings_pos_and_glosses(sample_jmdict_path: Path) -> None:
    entries = list(parse_jmdict(sample_jmdict_path))

    assert entries[0] == DictionaryEntry(
        entry_id=1000000,
        kanji_forms=("猫",),
        readings=("ねこ",),
        senses=(
            Sense(
                parts_of_speech=("noun (common) (futsuumeishi)",),
                glosses=("cat", "feline"),
            ),
        ),
    )


def test_entry_without_kanji_form_has_empty_kanji_forms(sample_jmdict_path: Path) -> None:
    entries = list(parse_jmdict(sample_jmdict_path))

    assert entries[1].kanji_forms == ()
    assert entries[1].readings == ("あそこ",)


def test_non_english_glosses_are_excluded(sample_jmdict_path: Path) -> None:
    entries = list(parse_jmdict(sample_jmdict_path))

    first_sense = entries[1].senses[0]
    assert first_sense.glosses == ()


def test_multiple_senses_are_preserved_in_order(sample_jmdict_path: Path) -> None:
    entries = list(parse_jmdict(sample_jmdict_path))

    assert len(entries[1].senses) == 2
    assert entries[1].senses[1] == Sense(
        parts_of_speech=("Godan verb with 'ru' ending",), glosses=("over there",)
    )


def test_build_dictionary_database_returns_entry_count_and_is_queryable(
    sample_jmdict_path: Path, tmp_path: Path
) -> None:
    database_path = tmp_path / "dictionary.sqlite3"

    count = build_dictionary_database(sample_jmdict_path, database_path)

    assert count == 2

    with SqliteDictionaryBackend(database_path) as backend:
        results = backend.lookup("猫")

    assert len(results) == 1
    assert results[0].entry_id == 1000000


def test_build_dictionary_database_overwrites_an_existing_file(
    sample_jmdict_path: Path, tmp_path: Path
) -> None:
    database_path = tmp_path / "dictionary.sqlite3"
    database_path.write_text("not a real database")

    count = build_dictionary_database(sample_jmdict_path, database_path)

    assert count == 2
