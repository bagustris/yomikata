"""Tests for yomikata.hover.debounce."""

from __future__ import annotations

from yomikata.hover.debounce import DebounceConfig, Debouncer


def make_debouncer(dwell_seconds: float = 0.15, movement_threshold_px: float = 4.0) -> Debouncer:
    config = DebounceConfig(
        dwell_seconds=dwell_seconds, movement_threshold_px=movement_threshold_px
    )
    return Debouncer(config)


def test_first_sample_never_reports_immediately() -> None:
    debouncer = make_debouncer()

    assert debouncer.update(100, 100, now=0.0) is False


def test_reports_after_dwell_time_at_stationary_position() -> None:
    debouncer = make_debouncer(dwell_seconds=0.15)

    assert debouncer.update(100, 100, now=0.0) is False
    assert debouncer.update(100, 100, now=0.10) is False
    assert debouncer.update(100, 100, now=0.16) is True


def test_does_not_report_before_dwell_time_elapses() -> None:
    debouncer = make_debouncer(dwell_seconds=0.15)

    debouncer.update(100, 100, now=0.0)
    assert debouncer.update(100, 100, now=0.14) is False


def test_does_not_report_twice_for_same_settled_anchor() -> None:
    debouncer = make_debouncer(dwell_seconds=0.15)

    debouncer.update(100, 100, now=0.0)
    assert debouncer.update(100, 100, now=0.16) is True
    assert debouncer.update(100, 100, now=0.20) is False
    assert debouncer.update(100, 100, now=1.0) is False


def test_movement_beyond_threshold_resets_the_anchor() -> None:
    debouncer = make_debouncer(dwell_seconds=0.15, movement_threshold_px=4.0)

    debouncer.update(100, 100, now=0.0)
    assert debouncer.update(100, 100, now=0.16) is True

    assert debouncer.update(200, 200, now=0.20) is False
    assert debouncer.update(200, 200, now=0.20 + 0.14) is False
    assert debouncer.update(200, 200, now=0.20 + 0.16) is True


def test_small_jitter_within_threshold_does_not_reset_anchor() -> None:
    debouncer = make_debouncer(dwell_seconds=0.15, movement_threshold_px=4.0)

    debouncer.update(100, 100, now=0.0)
    debouncer.update(102, 101, now=0.05)
    assert debouncer.update(101, 100, now=0.16) is True


def test_reset_clears_tracked_state() -> None:
    debouncer = make_debouncer(dwell_seconds=0.15)

    debouncer.update(100, 100, now=0.0)
    debouncer.update(100, 100, now=0.16)
    debouncer.reset()

    assert debouncer.update(100, 100, now=0.20) is False
    assert debouncer.update(100, 100, now=0.20 + 0.16) is True
