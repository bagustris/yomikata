"""Application entry point for YomiKata.

Wires the pipeline stages together and drives them from a single GLib main
loop: hover polling and the popup's fade animation both run as GLib
timeouts on the same thread, which avoids the cross-thread GTK calls that
running HoverMonitor on its own thread would require.
"""

from __future__ import annotations

import logging
import os
import signal
from pathlib import Path

from gi.repository import GLib

from yomikata.atspi.extractor import AccessibilityExtractor
from yomikata.dictionary.sqlite import SqliteDictionaryBackend
from yomikata.hover.monitor import HoverMonitor, SystemClock
from yomikata.hover.pointer_source import MODIFIER_MASKS, XlibModifierKeySource, XlibPointerSource
from yomikata.pipeline import HoverPipeline
from yomikata.popup.window import PopupWindow
from yomikata.tokenizer.sudachi import SudachiTokenizer
from yomikata.util.logging import configure_logging
from yomikata.util.session import is_wayland_session

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DATABASE_PATH = _REPO_ROOT / "database" / "dictionary.sqlite3"
_POLL_INTERVAL_SECONDS = 0.03


def _database_path() -> Path:
    override = os.environ.get("YOMIKATA_DATABASE_PATH")
    return Path(override) if override else _DEFAULT_DATABASE_PATH


def _hover_modifier_source() -> XlibModifierKeySource | None:
    """Build the modifier key source configured via YOMIKATA_HOVER_MODIFIER.

    Accepts "ctrl", "alt", or "shift" (case-insensitive); defaults to
    "ctrl" since polling the pointer system-wide (unlike a browser
    extension scoped to one tab) would otherwise pop up over Japanese
    text any time the pointer drifts near it during normal desktop use.
    Set to "none" to require no modifier. An unrecognized value is logged
    and treated as "ctrl".
    """
    name = os.environ.get("YOMIKATA_HOVER_MODIFIER", "ctrl").strip().lower()
    if name == "none" or not name:
        return None
    mask = MODIFIER_MASKS.get(name)
    if mask is None:
        logger.warning(
            "Unrecognized YOMIKATA_HOVER_MODIFIER=%r, falling back to ctrl. Valid values: %s, none",
            name,
            ", ".join(MODIFIER_MASKS),
        )
        mask = MODIFIER_MASKS["ctrl"]
    return XlibModifierKeySource(mask)


def main() -> None:
    """Start the YomiKata application."""
    configure_logging()
    logger.info("YomiKata starting up")

    if is_wayland_session():
        logger.info(
            "Wayland session detected. YomiKata reads text only from applications "
            "running under XWayland; launch target apps with GDK_BACKEND=x11 "
            "(e.g. GDK_BACKEND=x11 evince file.pdf). See README.md's Wayland section."
        )

    database_path = _database_path()
    if not database_path.exists():
        logger.error(
            "Dictionary database not found at %s. Build one with "
            "yomikata.dictionary.jmdict.build_dictionary_database and "
            "yomikata.dictionary.kanjidic.build_kanji_database, or set "
            "YOMIKATA_DATABASE_PATH. See README.md.",
            database_path,
        )
        return

    accessibility_extractor = AccessibilityExtractor()
    tokenizer = SudachiTokenizer()
    dictionary_backend = SqliteDictionaryBackend(database_path)
    popup = PopupWindow()
    pointer_source = XlibPointerSource()
    modifier_source = _hover_modifier_source()

    pipeline = HoverPipeline(
        accessibility_extractor=accessibility_extractor,
        tokenizer=tokenizer,
        dictionary_backend=dictionary_backend,
        popup=popup,
    )

    hover_monitor = HoverMonitor(
        pointer_source=pointer_source,
        clock=SystemClock(),
        poll_interval_seconds=_POLL_INTERVAL_SECONDS,
        modifier_source=modifier_source,
    )
    hover_monitor.add_listener(pipeline.on_hover)
    hover_monitor.add_end_listener(popup.hide)

    def poll_tick() -> bool:
        hover_monitor.poll_once()
        return GLib.SOURCE_CONTINUE

    GLib.timeout_add(int(_POLL_INTERVAL_SECONDS * 1000), poll_tick)

    main_loop = GLib.MainLoop()
    signal.signal(signal.SIGINT, lambda *_args: main_loop.quit())

    logger.info("YomiKata ready, hovering over Japanese text will show a popup")
    try:
        main_loop.run()
    finally:
        logger.info("YomiKata shutting down")
        pipeline.close()
        pointer_source.close()
        if modifier_source is not None:
            modifier_source.close()


if __name__ == "__main__":
    main()
