"""Application entry point for YomiKata.

Wires the pipeline stages together and drives them from a single GLib main
loop: hover polling and the popup's fade animation both run as GLib
timeouts on the same thread, which avoids the cross-thread GTK calls that
running HoverMonitor on its own thread would require.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from gi.repository import GLib

from yomikata.atspi.extractor import AccessibilityExtractor
from yomikata.dictionary.sqlite import SqliteDictionaryBackend
from yomikata.hover.monitor import HoverMonitor, SystemClock
from yomikata.hover.pointer_source import MODIFIER_MASKS, XlibModifierKeySource, XlibPointerSource
from yomikata.pipeline import HoverPipeline
from yomikata.popup.window import PopupWindow
from yomikata.tokenizer.sudachi import SudachiTokenizer
from yomikata.util.config import Settings, load_settings
from yomikata.util.logging import configure_logging
from yomikata.util.session import is_wayland_session

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DATABASE_PATH = _REPO_ROOT / "database" / "dictionary.sqlite3"
_POLL_INTERVAL_SECONDS = 0.03


def _database_path() -> Path:
    override = os.environ.get("YOMIKATA_DATABASE_PATH")
    return Path(override) if override else _DEFAULT_DATABASE_PATH


def _prompt_build_dictionary(database_path: Path) -> bool:
    """Ask the user whether to download and build the missing dictionary now.

    Only meaningful when stdin is a terminal; callers should check
    ``sys.stdin.isatty()`` first so a headless launch (e.g. autostart)
    never blocks on input.
    """
    response = input(
        f"Dictionary database not found at {database_path}. "
        "Download JMdict/KANJIDIC2 and build it now? [y/N] "
    )
    return response.strip().lower() in ("y", "yes")


def _hover_modifier_source(settings: Settings) -> XlibModifierKeySource | None:
    """Build the modifier key source for the given settings.

    The default of "ctrl" exists because polling the pointer system-wide
    (unlike a browser extension scoped to one tab) would otherwise pop up
    over Japanese text any time the pointer drifts near it during normal
    desktop use. A setting of "none" requires no modifier.

    Args:
        settings: The effective settings (see
            :func:`yomikata.util.config.load_settings`), whose
            ``hover_modifier`` is guaranteed valid by that loader.
    """
    if settings.hover_modifier == "none":
        return None
    return XlibModifierKeySource(MODIFIER_MASKS[settings.hover_modifier])


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="yomikata")
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Open the settings window instead of starting the hover dictionary.",
    )
    parser.add_argument(
        "--build-dict",
        action="store_true",
        help="Download JMdict/KANJIDIC2 and build the dictionary database, then exit.",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Start the YomiKata application."""
    configure_logging()
    args = _parse_args(sys.argv[1:])

    if args.settings:
        from yomikata.settings.window import run_settings_window

        run_settings_window()
        return

    database_path = _database_path()

    if args.build_dict:
        from yomikata.dictionary.setup import download_and_build

        download_and_build(database_path)
        return

    logger.info("YomiKata starting up")

    if is_wayland_session():
        logger.info(
            "Wayland session detected. YomiKata reads text only from applications "
            "running under XWayland; launch target apps with GDK_BACKEND=x11 "
            "(e.g. GDK_BACKEND=x11 evince file.pdf). See README.md's Wayland section."
        )

    if not database_path.exists():
        if sys.stdin.isatty() and _prompt_build_dictionary(database_path):
            from yomikata.dictionary.setup import download_and_build

            download_and_build(database_path)
        else:
            logger.error(
                "Dictionary database not found at %s. Build one with "
                "`uv run yomikata --build-dict`, or set YOMIKATA_DATABASE_PATH. "
                "See README.md.",
                database_path,
            )
            return

    settings = load_settings()
    accessibility_extractor = AccessibilityExtractor()
    tokenizer = SudachiTokenizer()
    dictionary_backend = SqliteDictionaryBackend(database_path)
    popup = PopupWindow()
    pointer_source = XlibPointerSource()
    modifier_source = _hover_modifier_source(settings)

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
