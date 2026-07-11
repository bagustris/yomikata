"""Popup content rendering.

Responsible only for turning already-resolved dictionary data into a GTK4
widget tree. Must never look anything up itself -- callers pass in the
:class:`~yomikata.dictionary.backend.DictionaryEntry` and
:class:`~yomikata.dictionary.backend.KanjiEntry` objects to display.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from yomikata.dictionary.backend import DictionaryEntry, KanjiEntry, Sense  # noqa: E402


@dataclass(frozen=True)
class PopupContent:
    """Everything the popup needs to render a single hover result.

    Attributes:
        surface: The hovered token exactly as it appeared in the text.
        reading: The hovered token's reading.
        entries: Matching word dictionary entries, in display order.
        kanji: Reference data for each kanji character in ``surface``.
        conjugation_note: A short description of how ``surface`` was
            conjugated from its dictionary form, e.g. ``"continuative form
            of 食べる"``, or None if it is not an inflected form.
    """

    surface: str
    reading: str
    entries: tuple[DictionaryEntry, ...]
    kanji: tuple[KanjiEntry, ...] = field(default_factory=tuple)
    conjugation_note: str | None = None


def render_popup_content(content: PopupContent) -> Gtk.Widget:
    """Build the widget tree for a popup's contents.

    Args:
        content: The resolved data to display.

    Returns:
        A GTK4 widget ready to be placed inside a popup window.
    """
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    root.add_css_class("yomikata-popup")

    root.append(_render_header(content))

    if content.conjugation_note is not None:
        root.append(_render_conjugation_note(content.conjugation_note))

    for entry in content.entries:
        root.append(_render_entry(entry))

    for kanji in content.kanji:
        root.append(_render_kanji(kanji))

    if not content.entries and not content.kanji:
        root.append(_render_no_results())

    return root


_MAX_LABEL_WIDTH_CHARS = 50
_MAX_TAGS_PER_LINE = 3


def _label(text: str, css_class: str, wrap: bool = False) -> Gtk.Label:
    """Build a left-aligned label with a CSS class.

    Wrapping labels also get a max width so the popup's natural size stays
    bounded -- a wrapping GTK label's natural width is otherwise the full
    unwrapped line, which for long glosses would push the popup past the
    screen edge (compute_popup_position clamps position, never size).
    """
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class(css_class)
    if wrap:
        label.set_wrap(True)
        label.set_max_width_chars(_MAX_LABEL_WIDTH_CHARS)
    return label


def _render_header(content: PopupContent) -> Gtk.Widget:
    return _label(f"{content.surface} ({content.reading})", "yomikata-popup-header")


def _render_conjugation_note(note: str) -> Gtk.Widget:
    return _label(note, "yomikata-popup-conjugation", wrap=True)


def _render_entry(entry: DictionaryEntry) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.add_css_class("yomikata-popup-entry")

    for sense_number, sense in enumerate(entry.senses, start=1):
        box.append(_render_sense(sense_number, sense))

    return box


def _render_sense(sense_number: int, sense: Sense) -> Gtk.Widget:
    row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    row.add_css_class("yomikata-popup-sense-row")

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    number_label = Gtk.Label(label=f"{sense_number}.", valign=Gtk.Align.START)
    number_label.add_css_class("yomikata-popup-sense-number")
    header.append(number_label)
    header.append(_render_tags(sense.parts_of_speech))
    row.append(header)

    row.append(_label("; ".join(sense.glosses), "yomikata-popup-gloss", wrap=True))

    return row


def _render_tags(parts_of_speech: tuple[str, ...]) -> Gtk.Widget:
    # A FlowBox rather than a Box so that senses with several long
    # part-of-speech descriptions wrap onto extra rows instead of forcing
    # the popup wider than the screen.
    flow = Gtk.FlowBox()
    flow.set_selection_mode(Gtk.SelectionMode.NONE)
    flow.set_max_children_per_line(_MAX_TAGS_PER_LINE)
    flow.set_column_spacing(4)
    flow.set_row_spacing(2)
    for part_of_speech in parts_of_speech:
        tag = Gtk.Label(label=part_of_speech)
        tag.add_css_class("yomikata-popup-tag")
        flow.append(tag)
    return flow


def _render_kanji(kanji: KanjiEntry) -> Gtk.Widget:
    parts = [kanji.character]
    if kanji.onyomi:
        parts.append("On: " + "、".join(kanji.onyomi))
    if kanji.kunyomi:
        parts.append("Kun: " + "、".join(kanji.kunyomi))
    if kanji.meanings:
        parts.append(", ".join(kanji.meanings))

    return _label(" - ".join(parts), "yomikata-popup-kanji", wrap=True)


def _render_no_results() -> Gtk.Widget:
    return _label("No dictionary entry found", "yomikata-popup-empty")
