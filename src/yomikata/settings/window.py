"""A minimal settings window for editing persisted user preferences.

Kept separate from popup/ (which renders hover results only and never
touches persisted configuration) and launched via ``yomikata --settings``
rather than a system tray icon: stock GNOME ships no tray/status-icon
support without a shell extension, so a tray-triggered dialog would not
reliably appear for most users.

The window edits the *persisted* settings (:func:`load_saved_settings`),
deliberately ignoring the transient ``YOMIKATA_HOVER_MODIFIER``
environment override -- otherwise the dialog would display the override
instead of the saved preference, and saving would silently overwrite the
file with the env value.
"""

from __future__ import annotations

import logging
from dataclasses import replace

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from yomikata.util.config import (  # noqa: E402
    HOVER_MODIFIER_NAMES,
    load_saved_settings,
    save_settings,
)

logger = logging.getLogger(__name__)


def run_settings_window() -> None:
    """Show the settings window and block until it is closed."""
    app = Adw.Application(application_id="io.github.yomikata.Settings")
    app.connect("activate", _build_window)
    app.run([])


def _build_window(app: Adw.Application) -> None:
    settings = load_saved_settings()

    window = Adw.PreferencesWindow(application=app)
    window.set_title("YomiKata Settings")

    group = Adw.PreferencesGroup(title="Hover")
    group.set_description("Controls how hovering over Japanese text triggers a lookup.")

    modifier_row = Adw.ComboRow(title="Hover modifier key")
    modifier_row.set_subtitle('Key that must be held while hovering, or "none"')
    modifier_row.set_model(Gtk.StringList.new(list(HOVER_MODIFIER_NAMES)))
    modifier_row.set_selected(HOVER_MODIFIER_NAMES.index(settings.hover_modifier))
    modifier_row.connect("notify::selected", _on_modifier_changed)
    group.add(modifier_row)

    page = Adw.PreferencesPage()
    page.add(group)
    window.add(page)

    window.present()


def _on_modifier_changed(row: Adw.ComboRow, _param: object) -> None:
    selected = HOVER_MODIFIER_NAMES[row.get_selected()]
    # Load-then-replace so fields other than the one this row edits keep
    # their persisted values instead of being reset to defaults.
    updated = replace(load_saved_settings(), hover_modifier=selected)
    save_settings(updated)
    logger.info("Saved hover_modifier=%s", selected)
