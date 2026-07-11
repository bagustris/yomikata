"""Tests for yomikata.pipeline.

Uses a real AccessibilityExtractor (with a fake backend, per Milestone 3's
own test pattern) and a real SudachiTokenizer (real dictionary, per
Milestone 5's rationale: it's a pinned, deterministic dependency worth
exercising for real). The dictionary backend and popup are faked, since
those represent expensive-to-construct externals (a SQLite file, a live
GTK4/X11 window) that this module's own tests already cover in isolation.
"""

from __future__ import annotations

import pytest

from yomikata.atspi.extractor import AccessibilityExtractor, AccessibleTextInfo
from yomikata.dictionary.backend import DictionaryEntry, KanjiEntry, Sense
from yomikata.hover.monitor import HoverEvent
from yomikata.pipeline import HoverPipeline
from yomikata.popup.renderer import PopupContent
from yomikata.tokenizer.sudachi import SudachiTokenizer


class FakeAccessibilityBackend:
    def __init__(self, result: AccessibleTextInfo | None) -> None:
        self._result = result

    def get_text_at_point(self, x: int, y: int) -> AccessibleTextInfo | None:
        return self._result


class FakeDictionaryBackend:
    def __init__(
        self,
        entries_by_headword: dict[str, list[DictionaryEntry]] | None = None,
        kanji_by_character: dict[str, KanjiEntry] | None = None,
        raise_on_lookup: bool = False,
    ) -> None:
        self._entries_by_headword = entries_by_headword or {}
        self._kanji_by_character = kanji_by_character or {}
        self._raise_on_lookup = raise_on_lookup
        self.lookup_calls: list[str] = []
        self.kanji_lookup_calls: list[str] = []
        self.closed = False

    def lookup(self, headword: str) -> list[DictionaryEntry]:
        if self._raise_on_lookup:
            raise RuntimeError("simulated dictionary failure")
        self.lookup_calls.append(headword)
        return self._entries_by_headword.get(headword, [])

    def lookup_kanji(self, character: str) -> KanjiEntry | None:
        self.kanji_lookup_calls.append(character)
        return self._kanji_by_character.get(character)

    def close(self) -> None:
        self.closed = True


class FakePopup:
    def __init__(self) -> None:
        self.shown: list[tuple[int, int, PopupContent]] = []
        self.hide_count = 0
        self.closed = False

    def show_at(self, x: int, y: int, content: PopupContent) -> None:
        self.shown.append((x, y, content))

    def hide(self) -> None:
        self.hide_count += 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture(scope="module")
def tokenizer() -> SudachiTokenizer:
    return SudachiTokenizer()


CAT_ENTRY = DictionaryEntry(
    entry_id=1,
    kanji_forms=("猫",),
    readings=("ねこ",),
    senses=(Sense(parts_of_speech=("noun",), glosses=("cat",)),),
)

GO_ENTRY = DictionaryEntry(
    entry_id=2,
    kanji_forms=("行く",),
    readings=("いく",),
    senses=(Sense(parts_of_speech=("verb",), glosses=("to go",)),),
)


def make_pipeline(
    tokenizer: SudachiTokenizer,
    accessible_text: AccessibleTextInfo | None,
    dictionary_backend: FakeDictionaryBackend | None = None,
    popup: FakePopup | None = None,
) -> tuple[HoverPipeline, FakeDictionaryBackend, FakePopup]:
    extractor = AccessibilityExtractor(backend=FakeAccessibilityBackend(accessible_text))
    dictionary_backend = dictionary_backend or FakeDictionaryBackend()
    popup = popup or FakePopup()
    pipeline = HoverPipeline(
        accessibility_extractor=extractor,
        tokenizer=tokenizer,
        dictionary_backend=dictionary_backend,
        popup=popup,
    )
    return pipeline, dictionary_backend, popup


def test_full_pipeline_shows_popup_with_resolved_entry(tokenizer: SudachiTokenizer) -> None:
    text_info = AccessibleTextInfo(text="猫がいます。", offset=0)
    dictionary_backend = FakeDictionaryBackend(entries_by_headword={"猫": [CAT_ENTRY]})
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info, dictionary_backend)

    pipeline.on_hover(HoverEvent(x=100, y=200, timestamp=0.0))

    assert len(popup.shown) == 1
    x, y, content = popup.shown[0]
    assert (x, y) == (100, 200)
    assert content.surface == "猫"
    assert content.entries == (CAT_ENTRY,)


def test_falls_back_to_dictionary_form_for_inflected_verbs(tokenizer: SudachiTokenizer) -> None:
    text_info = AccessibleTextInfo(text="東京に行きました。", offset=3)
    dictionary_backend = FakeDictionaryBackend(entries_by_headword={"行く": [GO_ENTRY]})
    pipeline, backend, popup = make_pipeline(tokenizer, text_info, dictionary_backend)

    pipeline.on_hover(HoverEvent(x=1, y=1, timestamp=0.0))

    assert popup.shown[0][2].entries == (GO_ENTRY,)
    assert "行き" in backend.lookup_calls  # surface tried first
    assert "行く" in backend.lookup_calls  # then the dictionary form


def test_conjugation_note_is_attached_for_an_inflected_verb(tokenizer: SudachiTokenizer) -> None:
    text_info = AccessibleTextInfo(text="東京に行きました。", offset=3)
    dictionary_backend = FakeDictionaryBackend(entries_by_headword={"行く": [GO_ENTRY]})
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info, dictionary_backend)

    pipeline.on_hover(HoverEvent(x=1, y=1, timestamp=0.0))

    assert popup.shown[0][2].conjugation_note == "continuative form of 行く"


def test_conjugation_note_is_suppressed_when_the_surface_itself_is_a_headword(
    tokenizer: SudachiTokenizer,
) -> None:
    # 行き is a real JMdict headword (the noun "bound for"); when the
    # surface lookup succeeds, the entries describe the surface form, so a
    # "form of 行く" note would mislabel them.
    going_entry = DictionaryEntry(
        entry_id=3,
        kanji_forms=("行き",),
        readings=("いき",),
        senses=(Sense(parts_of_speech=("noun",), glosses=("bound for",)),),
    )
    text_info = AccessibleTextInfo(text="東京に行きました。", offset=3)
    dictionary_backend = FakeDictionaryBackend(entries_by_headword={"行き": [going_entry]})
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info, dictionary_backend)

    pipeline.on_hover(HoverEvent(x=1, y=1, timestamp=0.0))

    assert popup.shown[0][2].entries == (going_entry,)
    assert popup.shown[0][2].conjugation_note is None


def test_conjugation_note_is_absent_for_an_uninflected_word(tokenizer: SudachiTokenizer) -> None:
    text_info = AccessibleTextInfo(text="猫がいます。", offset=0)
    dictionary_backend = FakeDictionaryBackend(entries_by_headword={"猫": [CAT_ENTRY]})
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info, dictionary_backend)

    pipeline.on_hover(HoverEvent(x=0, y=0, timestamp=0.0))

    assert popup.shown[0][2].conjugation_note is None


def test_hides_popup_when_no_accessible_text(tokenizer: SudachiTokenizer) -> None:
    pipeline, _backend, popup = make_pipeline(tokenizer, accessible_text=None)

    pipeline.on_hover(HoverEvent(x=0, y=0, timestamp=0.0))

    assert popup.hide_count == 1
    assert popup.shown == []


def test_hides_popup_when_sentence_extraction_yields_nothing(tokenizer: SudachiTokenizer) -> None:
    text_info = AccessibleTextInfo(text="", offset=0)
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info)

    pipeline.on_hover(HoverEvent(x=0, y=0, timestamp=0.0))

    assert popup.hide_count == 1


def test_hides_popup_when_offset_does_not_land_on_a_token(tokenizer: SudachiTokenizer) -> None:
    text_info = AccessibleTextInfo(text="猫", offset=50)
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info)

    pipeline.on_hover(HoverEvent(x=0, y=0, timestamp=0.0))

    assert popup.hide_count == 1


def test_shows_popup_with_no_results_placeholder_when_dictionary_has_no_match(
    tokenizer: SudachiTokenizer,
) -> None:
    text_info = AccessibleTextInfo(text="犬がいます。", offset=0)
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info)

    pipeline.on_hover(HoverEvent(x=5, y=5, timestamp=0.0))

    assert len(popup.shown) == 1
    assert popup.shown[0][2].entries == ()


def test_kanji_lookup_is_deduplicated_for_repeated_characters(tokenizer: SudachiTokenizer) -> None:
    # "ススキ" (pampas grass) tokenizes as a single token whose surface
    # literally repeats the character "ス" -- a real duplicate, unlike
    # words using the "々" iteration mark, which is a distinct character.
    text_info = AccessibleTextInfo(text="ススキです。", offset=0)
    dictionary_backend = FakeDictionaryBackend()
    pipeline, backend, popup = make_pipeline(tokenizer, text_info, dictionary_backend)

    pipeline.on_hover(HoverEvent(x=0, y=0, timestamp=0.0))

    assert popup.shown[0][2].surface == "ススキ"
    assert backend.kanji_lookup_calls.count("ス") == 1


def test_unexpected_exception_is_caught_and_hides_popup(tokenizer: SudachiTokenizer) -> None:
    text_info = AccessibleTextInfo(text="猫がいます。", offset=0)
    dictionary_backend = FakeDictionaryBackend(raise_on_lookup=True)
    pipeline, _backend, popup = make_pipeline(tokenizer, text_info, dictionary_backend)

    pipeline.on_hover(HoverEvent(x=0, y=0, timestamp=0.0))

    assert popup.shown == []
    assert popup.hide_count == 1


def test_close_releases_dictionary_backend_and_popup(tokenizer: SudachiTokenizer) -> None:
    pipeline, backend, popup = make_pipeline(tokenizer, accessible_text=None)

    pipeline.close()

    assert backend.closed is True
    assert popup.closed is True
