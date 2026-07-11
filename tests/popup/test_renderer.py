"""Tests for yomikata.popup.renderer."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from yomikata.dictionary.backend import DictionaryEntry, KanjiEntry, Sense  # noqa: E402
from yomikata.popup.renderer import PopupContent, render_popup_content  # noqa: E402

CAT_ENTRY = DictionaryEntry(
    entry_id=1,
    kanji_forms=("猫",),
    readings=("ねこ",),
    senses=(
        Sense(parts_of_speech=("noun",), glosses=("cat", "feline")),
        Sense(parts_of_speech=("colloquial",), glosses=("something else",)),
    ),
)

CAT_KANJI = KanjiEntry(
    character="猫",
    onyomi=("ビョウ",),
    kunyomi=("ねこ",),
    meanings=("cat",),
    grade=None,
    stroke_count=11,
    jlpt=1,
)


def _children(widget: Gtk.Widget) -> list[Gtk.Widget]:
    children = []
    child = widget.get_first_child()
    while child is not None:
        children.append(child)
        child = child.get_next_sibling()
    return children


def _all_labels_text(widget: Gtk.Widget) -> list[str]:
    texts = []
    if isinstance(widget, Gtk.Label):
        texts.append(widget.get_label())
    for child in _children(widget):
        texts.extend(_all_labels_text(child))
    return texts


def test_renders_header_with_surface_and_reading() -> None:
    content = PopupContent(surface="猫", reading="ねこ", entries=())

    widget = render_popup_content(content)

    assert "猫 (ねこ)" in _all_labels_text(widget)


def test_renders_conjugation_note_when_present() -> None:
    content = PopupContent(
        surface="行き",
        reading="いき",
        entries=(),
        conjugation_note="continuative form of 行く",
    )

    widget = render_popup_content(content)
    texts = _all_labels_text(widget)

    assert "continuative form of 行く" in texts


def test_omits_conjugation_note_when_absent() -> None:
    content = PopupContent(surface="猫", reading="ねこ", entries=())

    widget = render_popup_content(content)
    texts = _all_labels_text(widget)

    assert not any("continuative" in text for text in texts)


def test_renders_a_numbered_sense_per_entry_sense() -> None:
    content = PopupContent(surface="猫", reading="ねこ", entries=(CAT_ENTRY,))

    widget = render_popup_content(content)
    texts = _all_labels_text(widget)

    assert "1." in texts
    assert "2." in texts
    assert "cat; feline" in texts
    assert "something else" in texts


def test_renders_part_of_speech_as_a_separate_tag_per_sense() -> None:
    content = PopupContent(surface="猫", reading="ねこ", entries=(CAT_ENTRY,))

    widget = render_popup_content(content)
    texts = _all_labels_text(widget)

    assert "noun" in texts
    assert "colloquial" in texts


def test_renders_kanji_readings_and_meanings() -> None:
    content = PopupContent(surface="猫", reading="ねこ", entries=(), kanji=(CAT_KANJI,))

    widget = render_popup_content(content)
    texts = _all_labels_text(widget)

    assert any("On: ビョウ" in text and "Kun: ねこ" in text and "cat" in text for text in texts)


def test_renders_a_placeholder_when_there_are_no_results() -> None:
    content = PopupContent(surface="foo", reading="foo", entries=())

    widget = render_popup_content(content)
    texts = _all_labels_text(widget)

    assert any("No dictionary entry found" in text for text in texts)


def test_multiple_entries_each_get_their_own_section() -> None:
    other_entry = DictionaryEntry(
        entry_id=2,
        kanji_forms=("猫",),
        readings=("ねこ",),
        senses=(Sense(parts_of_speech=("noun",), glosses=("kitty",)),),
    )
    content = PopupContent(surface="猫", reading="ねこ", entries=(CAT_ENTRY, other_entry))

    widget = render_popup_content(content)
    texts = _all_labels_text(widget)

    assert any("cat; feline" in text for text in texts)
    assert any("kitty" in text for text in texts)
