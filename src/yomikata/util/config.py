"""Persisted user settings.

Settings are stored as JSON in the platform config directory (XDG:
``$XDG_CONFIG_HOME/yomikata/config.json``, falling back to
``~/.config/yomikata/config.json``) so the settings window
(:mod:`yomikata.settings.window`) and the main app agree on where to read
and write them. The ``YOMIKATA_HOVER_MODIFIER`` environment variable,
where set, overrides whatever is on disk -- this keeps the original
env-var-only workflow (CI, scripted runs) working unchanged.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from yomikata.hover.pointer_source import MODIFIER_MASKS

logger = logging.getLogger(__name__)

#: Valid hover-modifier names, in settings-window display order: "none"
#: (no modifier required) plus every key the hover layer's mask table
#: supports. Derived from MODIFIER_MASKS so a modifier added there is
#: automatically accepted here and offered in the settings window.
HOVER_MODIFIER_NAMES: tuple[str, ...] = ("none", *MODIFIER_MASKS)

#: Same names as :data:`HOVER_MODIFIER_NAMES`, as a set, for validation.
VALID_HOVER_MODIFIERS = frozenset(HOVER_MODIFIER_NAMES)

_DEFAULT_HOVER_MODIFIER = "ctrl"


@dataclass(frozen=True)
class Settings:
    """User-configurable settings.

    Attributes:
        hover_modifier: The modifier key that must be held for a hover to
            trigger a lookup, or "none" to require no modifier. One of
            :data:`VALID_HOVER_MODIFIERS`.
    """

    hover_modifier: str = _DEFAULT_HOVER_MODIFIER


def config_path(environ: Mapping[str, str] | None = None) -> Path:
    """Return the path to the settings file.

    Args:
        environ: Environment mapping to inspect. Defaults to ``os.environ``;
            injectable so tests need not mutate the process environment or
            touch the real home directory.

    Returns:
        ``$XDG_CONFIG_HOME/yomikata/config.json``, or
        ``~/.config/yomikata/config.json`` if XDG_CONFIG_HOME is unset or
        not an absolute path (the XDG Base Directory spec requires
        relative values to be ignored).
    """
    env = os.environ if environ is None else environ
    config_home = env.get("XDG_CONFIG_HOME", "").strip()
    if config_home and Path(config_home).is_absolute():
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    return base / "yomikata" / "config.json"


def _validated_modifier(raw: object, source: str) -> str | None:
    """Normalize and validate a hover-modifier name from ``source``.

    Args:
        raw: The value as read (any JSON type from the file, str from env).
        source: Where the value came from, for the warning message.

    Returns:
        The normalized (stripped, lowercased) name if valid, else None
        after logging a warning.
    """
    if not isinstance(raw, str):
        logger.warning("Ignoring non-string hover_modifier from %s: %r", source, raw)
        return None
    name = raw.strip().lower()
    if name in VALID_HOVER_MODIFIERS:
        return name
    logger.warning(
        "Unrecognized hover modifier %r from %s. Valid values: %s",
        raw,
        source,
        ", ".join(HOVER_MODIFIER_NAMES),
    )
    return None


def load_saved_settings(
    path: Path | None = None, environ: Mapping[str, str] | None = None
) -> Settings:
    """Load settings from disk only, without the environment override.

    This is what the settings window edits: the persisted preferences,
    unaffected by any transient ``YOMIKATA_HOVER_MODIFIER`` override in
    the invoking shell.

    Args:
        path: Settings file to read. Defaults to :func:`config_path`.
        environ: Environment mapping used only to locate the config file
            (XDG_CONFIG_HOME). Defaults to ``os.environ``.

    Returns:
        The persisted settings; defaults for anything missing or invalid.
    """
    resolved_path = path if path is not None else config_path(environ)
    settings = Settings()
    if not resolved_path.exists():
        return settings

    try:
        data = json.loads(resolved_path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to read settings file at %s", resolved_path, exc_info=True)
        return settings

    raw = data.get("hover_modifier")
    if raw is not None:
        validated = _validated_modifier(raw, f"settings file {resolved_path}")
        if validated is not None:
            settings = replace(settings, hover_modifier=validated)
    return settings


def load_settings(path: Path | None = None, environ: Mapping[str, str] | None = None) -> Settings:
    """Load settings, applying the ``YOMIKATA_HOVER_MODIFIER`` override.

    Where the environment variable is set, it wins over the file: set but
    empty means "none" (no modifier required), and an unrecognized value
    is logged and forced to "ctrl" -- the safe default, since an
    unmodified system-wide hover popup is the failure mode the modifier
    requirement exists to prevent.

    Args:
        path: Settings file to read. Defaults to :func:`config_path`.
        environ: Environment mapping to inspect. Defaults to
            ``os.environ``.

    Returns:
        The effective settings.
    """
    env = os.environ if environ is None else environ
    settings = load_saved_settings(path, environ)

    if "YOMIKATA_HOVER_MODIFIER" in env:
        raw = env["YOMIKATA_HOVER_MODIFIER"]
        if not raw.strip():
            override = "none"
        else:
            override = _validated_modifier(raw, "YOMIKATA_HOVER_MODIFIER") or (
                _DEFAULT_HOVER_MODIFIER
            )
        settings = replace(settings, hover_modifier=override)

    return settings


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Persist settings to disk, creating the config directory if needed.

    Args:
        settings: The settings to save.
        path: Settings file to write. Defaults to :func:`config_path`.
    """
    resolved_path = path if path is not None else config_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps({"hover_modifier": settings.hover_modifier}, indent=2))
