"""Locating the accessible object under a screen coordinate.

The traversal logic here is expressed against small :class:`Protocol`
interfaces rather than the real ``gi.repository.Atspi`` types, so it can be
unit tested with lightweight fakes instead of a running AT-SPI bus.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class ComponentLike(Protocol):
    """Subset of AT-SPI's Component interface used for hit-testing."""

    def contains(self, x: int, y: int) -> bool:
        """Return True if (x, y) falls within this component's bounds."""
        ...


class AccessibleLike(Protocol):
    """Subset of AT-SPI's Accessible interface used for hit-testing."""

    def get_component(self) -> ComponentLike | None:
        """Return this object's Component interface, if it implements one."""
        ...

    def get_child_count(self) -> int:
        """Return the number of direct children."""
        ...

    def get_child_at_index(self, index: int) -> AccessibleLike | None:
        """Return the direct child at the given index."""
        ...


def locate_accessible_at_point(root: AccessibleLike, x: int, y: int) -> AccessibleLike | None:
    """Find the most specific accessible object at a screen coordinate.

    Walks the accessibility tree starting at ``root``, repeatedly descending
    into whichever child's Component bounds contain (x, y), until no child
    contains the point. Descending via ``Component.contains`` rather than
    ``Component.get_accessible_at_point`` avoids relying on that method's
    inconsistent behavior across toolkits.

    Args:
        root: The accessible to start searching from, typically the desktop.
        x: Screen X coordinate, in pixels.
        y: Screen Y coordinate, in pixels.

    Returns:
        The most specific accessible containing (x, y), or None if nothing
        in the tree contains that point.
    """
    best_match: AccessibleLike | None = None
    current = root

    while True:
        hit_child = _find_containing_child(current, x, y)
        if hit_child is None:
            break
        best_match = hit_child
        current = hit_child

    return best_match


def _find_containing_child(node: AccessibleLike, x: int, y: int) -> AccessibleLike | None:
    try:
        child_count = node.get_child_count()
    except Exception:
        logger.debug("Failed to enumerate children while hit-testing", exc_info=True)
        return None

    for index in range(child_count):
        try:
            child = node.get_child_at_index(index)
        except Exception:
            logger.debug("Failed to fetch child %d while hit-testing", index, exc_info=True)
            continue

        if child is None:
            continue

        if _contains_point(child, x, y):
            return child

    return None


def _contains_point(node: AccessibleLike, x: int, y: int) -> bool:
    try:
        component = node.get_component()
    except Exception:
        logger.debug("Failed to fetch Component interface while hit-testing", exc_info=True)
        return False

    if component is None:
        return False

    try:
        return component.contains(x, y)
    except Exception:
        logger.debug("Component.contains raised while hit-testing", exc_info=True)
        return False
