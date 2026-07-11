"""Tests for yomikata.tokenizer.sudachi."""

from __future__ import annotations

from itertools import pairwise

import pytest
from sudachipy import SplitMode

from yomikata.tokenizer.sudachi import SudachiTokenizer, Token


@pytest.fixture(scope="module")
def tokenizer() -> SudachiTokenizer:
    return SudachiTokenizer()


class RaisingRawTokenizer:
    def tokenize(self, text: str, split_mode: SplitMode) -> list[object]:
        raise RuntimeError("dictionary unavailable")


def test_empty_text_returns_no_tokens(tokenizer: SudachiTokenizer) -> None:
    assert tokenizer.tokenize("") == []


def test_tokenizes_a_simple_sentence(tokenizer: SudachiTokenizer) -> None:
    tokens = tokenizer.tokenize("東京に行きました。")

    surfaces = [token.surface for token in tokens]
    assert surfaces == ["東京", "に", "行き", "まし", "た", "。"]


def test_returns_reading_dictionary_form_and_pos(tokenizer: SudachiTokenizer) -> None:
    tokens = tokenizer.tokenize("東京に行きました。")
    first = tokens[0]

    assert first == Token(
        surface="東京",
        reading="トウキョウ",
        dictionary_form="東京",
        part_of_speech=("名詞", "固有名詞", "地名", "一般", "*", "*"),
        start_offset=0,
        end_offset=2,
    )


@pytest.mark.parametrize(
    "text",
    [
        "東京に行きました。",
        "これは日本語のテストです",
        "国立国会図書館で本を読む。",
        "吾輩は猫である。名前はまだ無い。",
    ],
)
def test_token_offsets_exactly_reconstruct_the_original_text(
    tokenizer: SudachiTokenizer, text: str
) -> None:
    tokens = tokenizer.tokenize(text)

    reconstructed = "".join(text[token.start_offset : token.end_offset] for token in tokens)
    assert reconstructed == text

    for token in tokens:
        assert text[token.start_offset : token.end_offset] == token.surface


def test_tokens_are_contiguous_and_ordered(tokenizer: SudachiTokenizer) -> None:
    tokens = tokenizer.tokenize("国立国会図書館で本を読む。")

    for previous, current in pairwise(tokens):
        assert current.start_offset == previous.end_offset


def test_split_mode_c_groups_compounds_more_coarsely_than_mode_a() -> None:
    text = "国立国会図書館"
    fine_tokenizer = SudachiTokenizer(split_mode=SplitMode.A)
    coarse_tokenizer = SudachiTokenizer(split_mode=SplitMode.C)

    fine_tokens = fine_tokenizer.tokenize(text)
    coarse_tokens = coarse_tokenizer.tokenize(text)

    assert len(coarse_tokens) < len(fine_tokens)


def test_raw_tokenizer_failure_returns_empty_list_without_raising() -> None:
    tokenizer = SudachiTokenizer(raw_tokenizer=RaisingRawTokenizer())  # type: ignore[arg-type]

    assert tokenizer.tokenize("何か") == []
