"""Tests for yomikata.dictionary.kanjidic."""

from __future__ import annotations

from pathlib import Path

import pytest

from yomikata.dictionary.backend import KanjiEntry
from yomikata.dictionary.jmdict import build_dictionary_database
from yomikata.dictionary.kanjidic import build_kanji_database, parse_kanjidic
from yomikata.dictionary.sqlite import SqliteDictionaryBackend

_SAMPLE_KANJIDIC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<kanjidic2>
<character>
<literal>亜</literal>
<misc>
<grade>8</grade>
<stroke_count>7</stroke_count>
<stroke_count>8</stroke_count>
<jlpt>1</jlpt>
</misc>
<reading_meaning>
<rmgroup>
<reading r_type="pinyin">ya4</reading>
<reading r_type="ja_on">ア</reading>
<reading r_type="ja_kun">つ.ぐ</reading>
<meaning>Asia</meaning>
<meaning>rank next</meaning>
<meaning m_lang="fr">Asie</meaning>
</rmgroup>
</reading_meaning>
</character>
<character>
<literal>唖</literal>
<misc>
<stroke_count>11</stroke_count>
</misc>
<reading_meaning>
<rmgroup>
<reading r_type="ja_on">ア</reading>
</rmgroup>
</reading_meaning>
</character>
<character>
<literal>凜</literal>
<misc>
<stroke_count>15</stroke_count>
</misc>
</character>
</kanjidic2>
"""


@pytest.fixture
def sample_kanjidic_path(tmp_path: Path) -> Path:
    path = tmp_path / "sample_kanjidic2.xml"
    path.write_text(_SAMPLE_KANJIDIC_XML, encoding="utf-8")
    return path


def test_parses_all_characters_in_document_order(sample_kanjidic_path: Path) -> None:
    entries = list(parse_kanjidic(sample_kanjidic_path))

    assert [entry.character for entry in entries] == ["亜", "唖", "凜"]


def test_parses_readings_meanings_grade_strokes_and_jlpt(sample_kanjidic_path: Path) -> None:
    entries = list(parse_kanjidic(sample_kanjidic_path))

    assert entries[0] == KanjiEntry(
        character="亜",
        onyomi=("ア",),
        kunyomi=("つ.ぐ",),
        meanings=("Asia", "rank next"),
        grade=8,
        stroke_count=7,
        jlpt=1,
    )


def test_uses_first_stroke_count_when_multiple_are_present(sample_kanjidic_path: Path) -> None:
    entries = list(parse_kanjidic(sample_kanjidic_path))

    assert entries[0].stroke_count == 7


def test_non_english_meanings_are_excluded(sample_kanjidic_path: Path) -> None:
    entries = list(parse_kanjidic(sample_kanjidic_path))

    assert "Asie" not in entries[0].meanings


def test_missing_grade_and_jlpt_are_none(sample_kanjidic_path: Path) -> None:
    entries = list(parse_kanjidic(sample_kanjidic_path))

    assert entries[1] == KanjiEntry(
        character="唖",
        onyomi=("ア",),
        kunyomi=(),
        meanings=(),
        grade=None,
        stroke_count=11,
        jlpt=None,
    )


def test_character_without_reading_meaning_element_has_empty_readings(
    sample_kanjidic_path: Path,
) -> None:
    entries = list(parse_kanjidic(sample_kanjidic_path))

    assert entries[2] == KanjiEntry(
        character="凜",
        onyomi=(),
        kunyomi=(),
        meanings=(),
        grade=None,
        stroke_count=15,
        jlpt=None,
    )


def test_build_kanji_database_returns_count_and_is_queryable(
    sample_kanjidic_path: Path, tmp_path: Path
) -> None:
    database_path = tmp_path / "dictionary.sqlite3"

    count = build_kanji_database(sample_kanjidic_path, database_path)

    assert count == 3
    with SqliteDictionaryBackend(database_path) as backend:
        result = backend.lookup_kanji("亜")

    assert result is not None
    assert result.meanings == ("Asia", "rank next")


def test_build_kanji_database_does_not_delete_existing_jmdict_data(
    sample_kanjidic_path: Path, tmp_path: Path
) -> None:
    database_path = tmp_path / "dictionary.sqlite3"
    jmdict_path = tmp_path / "empty_jmdict.xml"
    jmdict_path.write_text(
        '<?xml version="1.0"?><JMdict></JMdict>',
        encoding="utf-8",
    )
    build_dictionary_database(jmdict_path, database_path)

    build_kanji_database(sample_kanjidic_path, database_path)

    with SqliteDictionaryBackend(database_path) as backend:
        result = backend.lookup_kanji("亜")

    assert result is not None
