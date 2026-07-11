"""Live smoke test against the real AT-SPI bus.

This is best-effort: it is skipped whenever no AT-SPI bus is reachable
(e.g. headless CI runners with no desktop session), since PLAN.md requires
this module to degrade gracefully rather than assume any particular
environment. It does not assert on any specific application being open --
only that querying the real bus never raises.
"""

from __future__ import annotations

import pytest

from yomikata.atspi.extractor import AtspiAccessibilityBackend


def _atspi_bus_available() -> bool:
    try:
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        Atspi.init()
        return Atspi.get_desktop(0) is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _atspi_bus_available(), reason="No reachable AT-SPI bus in this environment"
)


def test_querying_the_real_desktop_never_raises() -> None:
    backend = AtspiAccessibilityBackend()

    result = backend.get_text_at_point(50, 50)

    assert result is None or isinstance(result.text, str)


def test_querying_an_out_of_bounds_point_returns_none() -> None:
    backend = AtspiAccessibilityBackend()

    assert backend.get_text_at_point(-100_000, -100_000) is None
