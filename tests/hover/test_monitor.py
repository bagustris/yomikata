"""Tests for yomikata.hover.monitor."""

from __future__ import annotations

from collections.abc import Iterator

from yomikata.hover.debounce import DebounceConfig, Debouncer
from yomikata.hover.monitor import HoverEvent, HoverMonitor, SystemClock


class FakeClock:
    """A controllable clock: time only advances when the test asks it to."""

    def __init__(self, start: float = 0.0) -> None:
        self._time = start
        self.sleep_calls: list[float] = []

    def now(self) -> float:
        return self._time

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self._time += seconds

    def advance(self, seconds: float) -> None:
        self._time += seconds


class FakePointerSource:
    """Replays a fixed sequence of positions, one per call."""

    def __init__(self, positions: Iterator[tuple[int, int] | None]) -> None:
        self._positions = positions

    def get_position(self) -> tuple[int, int] | None:
        return next(self._positions)


class FailingPointerSource:
    def get_position(self) -> tuple[int, int] | None:
        raise RuntimeError("accessibility bus unavailable")


class FakeModifierSource:
    """Reports a controllable, settable modifier-active state."""

    def __init__(self, active: bool = True) -> None:
        self.active = active

    def is_active(self) -> bool:
        return self.active


class FailingModifierSource:
    def is_active(self) -> bool:
        raise RuntimeError("could not query modifier state")


def make_monitor(positions: list[tuple[int, int] | None], clock: FakeClock) -> HoverMonitor:
    return HoverMonitor(
        pointer_source=FakePointerSource(iter(positions)),
        clock=clock,
        debouncer=Debouncer(DebounceConfig(dwell_seconds=0.15, movement_threshold_px=4.0)),
    )


def test_poll_once_returns_none_when_pointer_has_not_settled() -> None:
    clock = FakeClock()
    monitor = make_monitor([(100, 100)], clock)

    assert monitor.poll_once() is None


def test_poll_once_returns_event_once_settled() -> None:
    clock = FakeClock()
    monitor = make_monitor([(100, 100), (100, 100)], clock)

    monitor.poll_once()
    clock.advance(0.2)

    event = monitor.poll_once()

    assert event == HoverEvent(x=100, y=100, timestamp=0.2)


def test_poll_once_returns_none_when_position_unavailable() -> None:
    clock = FakeClock()
    monitor = make_monitor([None], clock)

    assert monitor.poll_once() is None


def test_listeners_are_notified_on_settled_hover() -> None:
    clock = FakeClock()
    monitor = make_monitor([(100, 100), (100, 100)], clock)
    received: list[HoverEvent] = []
    monitor.add_listener(received.append)

    monitor.poll_once()
    clock.advance(0.2)
    monitor.poll_once()

    assert len(received) == 1
    assert received[0].x == 100
    assert received[0].y == 100


def test_removed_listener_is_not_notified() -> None:
    clock = FakeClock()
    monitor = make_monitor([(100, 100), (100, 100)], clock)
    received: list[HoverEvent] = []
    monitor.add_listener(received.append)
    monitor.remove_listener(received.append)

    monitor.poll_once()
    clock.advance(0.2)
    monitor.poll_once()

    assert received == []


def test_listener_exception_does_not_propagate() -> None:
    clock = FakeClock()
    monitor = make_monitor([(100, 100), (100, 100)], clock)

    def bad_listener(event: HoverEvent) -> None:
        raise ValueError("boom")

    monitor.add_listener(bad_listener)

    monitor.poll_once()
    clock.advance(0.2)

    event = monitor.poll_once()
    assert event is not None


def test_pointer_source_exception_does_not_propagate() -> None:
    clock = FakeClock()
    monitor = HoverMonitor(pointer_source=FailingPointerSource(), clock=clock)

    assert monitor.poll_once() is None


def test_run_forever_polls_until_stopped() -> None:
    clock = FakeClock()
    positions: list[tuple[int, int] | None] = [(100, 100)] * 10
    monitor = make_monitor(positions, clock)
    poll_count = 0
    original_poll_once = monitor.poll_once

    def counting_poll_once() -> HoverEvent | None:
        nonlocal poll_count
        poll_count += 1
        if poll_count >= 3:
            monitor.stop()
        return original_poll_once()

    monitor.poll_once = counting_poll_once  # type: ignore[method-assign]

    monitor.run_forever()

    assert poll_count == 3
    assert len(clock.sleep_calls) == 3


def test_run_forever_uses_configured_poll_interval() -> None:
    clock = FakeClock()
    positions: list[tuple[int, int] | None] = [None, None]
    monitor = HoverMonitor(
        pointer_source=FakePointerSource(iter(positions)),
        clock=clock,
        poll_interval_seconds=0.03,
    )
    call_count = 0
    original_poll_once = monitor.poll_once

    def limited_poll_once() -> HoverEvent | None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            monitor.stop()
        return original_poll_once()

    monitor.poll_once = limited_poll_once  # type: ignore[method-assign]

    monitor.run_forever()

    assert clock.sleep_calls == [0.03, 0.03]


def test_system_clock_now_advances() -> None:
    clock = SystemClock()

    first = clock.now()
    clock.sleep(0.01)
    second = clock.now()

    assert second > first


def test_system_clock_sleep_blocks_for_approximately_the_requested_duration() -> None:
    clock = SystemClock()

    start = clock.now()
    clock.sleep(0.02)
    elapsed = clock.now() - start

    assert elapsed >= 0.02


def test_poll_once_returns_none_when_modifier_not_held_even_if_settled() -> None:
    clock = FakeClock()
    monitor = HoverMonitor(
        pointer_source=FakePointerSource(iter([(100, 100), (100, 100)])),
        clock=clock,
        debouncer=Debouncer(DebounceConfig(dwell_seconds=0.15, movement_threshold_px=4.0)),
        modifier_source=FakeModifierSource(active=False),
    )

    monitor.poll_once()
    clock.advance(0.2)

    assert monitor.poll_once() is None


def test_poll_once_reports_hover_once_modifier_held_and_settled() -> None:
    clock = FakeClock()
    modifier = FakeModifierSource(active=True)
    monitor = HoverMonitor(
        pointer_source=FakePointerSource(iter([(100, 100), (100, 100)])),
        clock=clock,
        debouncer=Debouncer(DebounceConfig(dwell_seconds=0.15, movement_threshold_px=4.0)),
        modifier_source=modifier,
    )

    monitor.poll_once()
    clock.advance(0.2)

    event = monitor.poll_once()

    assert event == HoverEvent(x=100, y=100, timestamp=0.2)


def test_releasing_modifier_resets_dwell_so_hover_is_not_reported_instantly() -> None:
    clock = FakeClock()
    modifier = FakeModifierSource(active=True)
    monitor = HoverMonitor(
        pointer_source=FakePointerSource(iter([(100, 100), (100, 100), (100, 100)])),
        clock=clock,
        debouncer=Debouncer(DebounceConfig(dwell_seconds=0.15, movement_threshold_px=4.0)),
        modifier_source=modifier,
    )

    monitor.poll_once()
    clock.advance(0.2)
    modifier.active = False
    assert monitor.poll_once() is None

    modifier.active = True
    assert monitor.poll_once() is None


def test_modifier_source_exception_does_not_propagate() -> None:
    clock = FakeClock()
    monitor = HoverMonitor(
        pointer_source=FakePointerSource(iter([(100, 100)])),
        clock=clock,
        modifier_source=FailingModifierSource(),
    )

    assert monitor.poll_once() is None
