"""Tests for yomikata.util.config."""

from __future__ import annotations

from pathlib import Path

from yomikata.util.config import (
    Settings,
    config_path,
    load_saved_settings,
    load_settings,
    save_settings,
)


def test_config_path_prefers_xdg_config_home() -> None:
    path = config_path({"XDG_CONFIG_HOME": "/custom/config"})

    assert path == Path("/custom/config/yomikata/config.json")


def test_config_path_falls_back_to_dot_config() -> None:
    path = config_path({})

    assert path == Path.home() / ".config" / "yomikata" / "config.json"


def test_config_path_ignores_a_relative_xdg_config_home() -> None:
    # The XDG Base Directory spec requires non-absolute paths be ignored.
    path = config_path({"XDG_CONFIG_HOME": "relative/config"})

    assert path == Path.home() / ".config" / "yomikata" / "config.json"


def test_load_settings_defaults_when_file_is_missing(tmp_path: Path) -> None:
    settings = load_settings(path=tmp_path / "missing.json", environ={})

    assert settings == Settings(hover_modifier="ctrl")


def test_load_settings_reads_a_saved_value(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_settings(Settings(hover_modifier="alt"), path=path)

    settings = load_settings(path=path, environ={})

    assert settings.hover_modifier == "alt"


def test_load_settings_ignores_an_unrecognized_file_value(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"hover_modifier": "meta"}')

    settings = load_settings(path=path, environ={})

    assert settings.hover_modifier == "ctrl"


def test_file_value_is_normalized_case_insensitively(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"hover_modifier": " Shift "}')

    settings = load_settings(path=path, environ={})

    assert settings.hover_modifier == "shift"


def test_load_settings_ignores_unreadable_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("not json")

    settings = load_settings(path=path, environ={})

    assert settings.hover_modifier == "ctrl"


def test_env_var_overrides_the_saved_file_value(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_settings(Settings(hover_modifier="alt"), path=path)

    settings = load_settings(path=path, environ={"YOMIKATA_HOVER_MODIFIER": "shift"})

    assert settings.hover_modifier == "shift"


def test_unrecognized_env_var_falls_back_to_ctrl(tmp_path: Path) -> None:
    # Not to the file value: with hover_modifier="none" on disk, honoring
    # the file on an env typo would silently drop the modifier requirement
    # entirely -- the failure mode the ctrl fallback exists to prevent.
    path = tmp_path / "config.json"
    save_settings(Settings(hover_modifier="none"), path=path)

    settings = load_settings(path=path, environ={"YOMIKATA_HOVER_MODIFIER": "meta"})

    assert settings.hover_modifier == "ctrl"


def test_env_var_set_but_empty_means_no_modifier(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_settings(Settings(hover_modifier="alt"), path=path)

    settings = load_settings(path=path, environ={"YOMIKATA_HOVER_MODIFIER": ""})

    assert settings.hover_modifier == "none"


def test_load_saved_settings_ignores_the_env_override(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    save_settings(Settings(hover_modifier="alt"), path=path)

    settings = load_saved_settings(path=path, environ={"YOMIKATA_HOVER_MODIFIER": "shift"})

    assert settings.hover_modifier == "alt"


def test_save_settings_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "config.json"

    save_settings(Settings(hover_modifier="none"), path=path)

    assert path.exists()
    assert load_settings(path=path, environ={}).hover_modifier == "none"
