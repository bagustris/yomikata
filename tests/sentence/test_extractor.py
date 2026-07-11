"""Tests for yomikata.sentence.extractor."""

from __future__ import annotations

import pytest

from yomikata.sentence.extractor import SentenceExtractionResult, extract_sentence


def test_empty_text_returns_empty_sentence() -> None:
    assert extract_sentence("", 0) == SentenceExtractionResult(sentence="", start_offset=0)


def test_single_sentence_with_no_delimiter_returns_whole_text() -> None:
    text = "これは文です"

    result = extract_sentence(text, 3)

    assert result == SentenceExtractionResult(sentence=text, start_offset=0)


def test_returns_first_sentence_when_offset_is_within_it() -> None:
    text = "これは文です。次の文です。"

    result = extract_sentence(text, 2)

    assert result == SentenceExtractionResult(sentence="これは文です。", start_offset=0)


def test_returns_second_sentence_when_offset_is_within_it() -> None:
    text = "これは文です。次の文です。"
    second_sentence_start = text.index("次")

    result = extract_sentence(text, second_sentence_start + 1)

    assert result == SentenceExtractionResult(
        sentence="次の文です。", start_offset=second_sentence_start
    )


@pytest.mark.parametrize("delimiter", ["。", "！", "？", "\n"])
def test_each_supported_delimiter_ends_a_sentence(delimiter: str) -> None:
    text = f"文一つ目{delimiter}文二つ目"

    result = extract_sentence(text, 0)

    assert result == SentenceExtractionResult(sentence=f"文一つ目{delimiter}", start_offset=0)


def test_offset_exactly_on_delimiter_resolves_to_the_closed_sentence() -> None:
    text = "これは文です。次の文です。"
    delimiter_offset = text.index("。")

    result = extract_sentence(text, delimiter_offset)

    assert result == SentenceExtractionResult(sentence="これは文です。", start_offset=0)


def test_ascii_punctuation_does_not_count_as_a_boundary() -> None:
    text = "これはURLです: http://example.com/a.b?c=1 続きます。"

    result = extract_sentence(text, 0)

    assert result.sentence == text
    assert result.start_offset == 0


def test_negative_offset_is_clamped_to_start() -> None:
    text = "これは文です。"

    result = extract_sentence(text, -5)

    assert result == SentenceExtractionResult(sentence="これは文です。", start_offset=0)


def test_offset_past_end_is_clamped_to_last_character() -> None:
    text = "これは文です。次の文です。"
    second_sentence_start = text.index("次")

    result = extract_sentence(text, len(text) + 10)

    assert result == SentenceExtractionResult(
        sentence="次の文です。", start_offset=second_sentence_start
    )


def test_consecutive_delimiters_produce_an_empty_middle_sentence() -> None:
    text = "文一。！文二"

    result = extract_sentence(text, text.index("！"))

    assert result == SentenceExtractionResult(sentence="！", start_offset=text.index("！"))
