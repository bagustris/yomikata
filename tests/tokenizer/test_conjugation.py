"""Tests for yomikata.tokenizer.conjugation."""

from __future__ import annotations

from yomikata.tokenizer.conjugation import describe_conjugation
from yomikata.tokenizer.sudachi import Token


def _token(surface: str, dictionary_form: str, part_of_speech: tuple[str, ...]) -> Token:
    return Token(
        surface=surface,
        reading="",
        dictionary_form=dictionary_form,
        part_of_speech=part_of_speech,
        start_offset=0,
        end_offset=len(surface),
    )


def test_describes_a_continuative_form() -> None:
    token = _token("行き", "行く", ("動詞", "非自立可能", "*", "*", "五段-カ行", "連用形-一般"))

    assert describe_conjugation(token) == "continuative form of 行く"


def test_describes_a_sound_changed_continuative_form() -> None:
    token = _token("美しかっ", "美しい", ("形容詞", "一般", "*", "*", "形容詞", "連用形-促音便"))

    assert describe_conjugation(token) == "continuative form (sound change) of 美しい"


def test_none_when_surface_matches_dictionary_form() -> None:
    token = _token("猫", "猫", ("名詞", "普通名詞", "一般", "*", "*", "*"))

    assert describe_conjugation(token) is None


def test_none_when_the_conjugated_form_tag_is_unrecognized() -> None:
    token = _token("た", "た", ("助動詞", "*", "*", "*", "助動詞-タ", "some-unmapped-tag"))

    assert describe_conjugation(token) is None


def test_none_when_part_of_speech_is_too_short() -> None:
    token = _token("た", "た", ("助動詞",))

    assert describe_conjugation(token) is None
