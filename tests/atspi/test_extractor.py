"""Tests for yomikata.atspi.extractor."""

from __future__ import annotations

from yomikata.atspi.extractor import AccessibilityExtractor, AccessibleTextInfo


class FakeBackend:
    def __init__(
        self, result: AccessibleTextInfo | None = None, error: Exception | None = None
    ) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[int, int]] = []

    def get_text_at_point(self, x: int, y: int) -> AccessibleTextInfo | None:
        self.calls.append((x, y))
        if self._error is not None:
            raise self._error
        return self._result


def test_extract_delegates_to_backend_and_returns_its_result() -> None:
    expected = AccessibleTextInfo(text="日本語", offset=1)
    backend = FakeBackend(result=expected)
    extractor = AccessibilityExtractor(backend=backend)

    result = extractor.extract(100, 200)

    assert result == expected
    assert backend.calls == [(100, 200)]


def test_extract_returns_none_when_backend_returns_none() -> None:
    extractor = AccessibilityExtractor(backend=FakeBackend(result=None))

    assert extractor.extract(0, 0) is None


def test_extract_returns_none_when_backend_raises() -> None:
    backend = FakeBackend(error=RuntimeError("AT-SPI bus unavailable"))
    extractor = AccessibilityExtractor(backend=backend)

    assert extractor.extract(0, 0) is None
