"""Tests for yomikata.util.logging."""

from __future__ import annotations

import logging

from yomikata.util.logging import configure_logging


def test_configure_logging_sets_level_and_single_handler() -> None:
    configure_logging(level=logging.DEBUG)

    root_logger = logging.getLogger()

    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0], logging.StreamHandler)


def test_configure_logging_replaces_existing_handlers() -> None:
    configure_logging()
    configure_logging()

    root_logger = logging.getLogger()

    assert len(root_logger.handlers) == 1
