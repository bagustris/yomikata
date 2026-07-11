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

from yomikata.dictionary.backend import DictionaryEntry, KanjiEntry  # noqa: E402


@dataclass(frozen=True)
class PopupContent:
    """Everything the popup needs to render a single hover result.

    Attributes:
        surface: The hovered token exactly as it appeared in the text.
        reading: The hovered token's reading.
        entries: Matching word dictionary entries, in display order.
        kanji: Reference data for each kanji character in ``surface``.
    """

    surface: str
    reading: str
    entries: tuple[DictionaryEntry, ...]
    kanji: tuple[KanjiEntry, ...] = field(default_factory=tuple)


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

    for entry in content.entries:
        root.append(_render_entry(entry))

    for kanji in content.kanji:
        root.append(_render_kanji(kanji))

    if not content.entries and not content.kanji:
        root.append(_render_no_results())

    return root


def _render_header(content: PopupContent) -> Gtk.Widget:
    label = Gtk.Label(label=f"{content.surface} ({content.reading})", xalign=0)
    label.add_css_class("yomikata-popup-header")
    return label


def _render_entry(entry: DictionaryEntry) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.add_css_class("yomikata-popup-entry")

    for sense_number, sense in enumerate(entry.senses, start=1):
        pos_text = ", ".join(sense.parts_of_speech)
        gloss_text = "; ".join(sense.glosses)
        sense_label = Gtk.Label(label=f"{sense_number}. [{pos_text}] {gloss_text}", xalign=0)
        sense_label.set_wrap(True)
        box.append(sense_label)

    return box


def _render_kanji(kanji: KanjiEntry) -> Gtk.Widget:
    parts = [kanji.character]
    if kanji.onyomi:
        parts.append("On: " + "、".join(kanji.onyomi))
    if kanji.kunyomi:
        parts.append("Kun: " + "、".join(kanji.kunyomi))
    if kanji.meanings:
        parts.append(", ".join(kanji.meanings))

    label = Gtk.Label(label=" - ".join(parts), xalign=0)
    label.add_css_class("yomikata-popup-kanji")
    label.set_wrap(True)
    return label


def _render_no_results() -> Gtk.Widget:
    label = Gtk.Label(label="No dictionary entry found", xalign=0)
    label.add_css_class("yomikata-popup-empty")
    return label
