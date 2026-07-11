"""Tests for yomikata.atspi.cursor."""

from __future__ import annotations

from yomikata.atspi.cursor import locate_accessible_at_point


class FakeComponent:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self._x, self._y, self._width, self._height = x, y, width, height

    def contains(self, x: int, y: int) -> bool:
        return self._x <= x < self._x + self._width and self._y <= y < self._y + self._height


class RaisingComponent:
    def contains(self, x: int, y: int) -> bool:
        raise RuntimeError("object went defunct")


class FakeAccessible:
    def __init__(
        self, name: str, component: FakeComponent | RaisingComponent | None = None
    ) -> None:
        self.name = name
        self._component = component
        self._children: list[FakeAccessible] = []

    def add_child(self, child: FakeAccessible) -> FakeAccessible:
        self._children.append(child)
        return child

    def get_component(self) -> FakeComponent | RaisingComponent | None:
        return self._component

    def get_child_count(self) -> int:
        return len(self._children)

    def get_child_at_index(self, index: int) -> FakeAccessible | None:
        return self._children[index]


class RaisingAccessible(FakeAccessible):
    def get_child_count(self) -> int:
        raise RuntimeError("accessible is defunct")


def test_returns_none_when_nothing_contains_the_point() -> None:
    root = FakeAccessible("desktop", FakeComponent(0, 0, 1000, 1000))

    assert locate_accessible_at_point(root, 5000, 5000) is None


def test_returns_direct_child_containing_the_point() -> None:
    root = FakeAccessible("desktop", FakeComponent(0, 0, 1000, 1000))
    window = root.add_child(FakeAccessible("window", FakeComponent(0, 0, 500, 500)))

    result = locate_accessible_at_point(root, 10, 10)

    assert result is window


def test_descends_to_the_deepest_containing_descendant() -> None:
    root = FakeAccessible("desktop", FakeComponent(0, 0, 1000, 1000))
    window = root.add_child(FakeAccessible("window", FakeComponent(0, 0, 500, 500)))
    panel = window.add_child(FakeAccessible("panel", FakeComponent(0, 0, 300, 300)))
    label = panel.add_child(FakeAccessible("label", FakeComponent(10, 10, 50, 20)))

    result = locate_accessible_at_point(root, 20, 15)

    assert result is label


def test_prefers_sibling_that_actually_contains_the_point() -> None:
    root = FakeAccessible("desktop", FakeComponent(0, 0, 1000, 1000))
    root.add_child(FakeAccessible("left", FakeComponent(0, 0, 100, 100)))
    right = root.add_child(FakeAccessible("right", FakeComponent(200, 0, 100, 100)))

    result = locate_accessible_at_point(root, 250, 50)

    assert result is right


def test_stops_at_the_last_matched_node_when_its_child_has_no_component() -> None:
    root = FakeAccessible("desktop", FakeComponent(0, 0, 1000, 1000))
    window = root.add_child(FakeAccessible("window", FakeComponent(0, 0, 500, 500)))
    window.add_child(FakeAccessible("childless", None))

    result = locate_accessible_at_point(root, 10, 10)

    assert result is window


def test_returns_none_when_the_root_itself_has_no_matching_child() -> None:
    root = FakeAccessible("desktop", None)
    root.add_child(FakeAccessible("leaf", None))

    assert locate_accessible_at_point(root, 10, 10) is None


def test_ignores_child_whose_component_raises() -> None:
    root = FakeAccessible("desktop", FakeComponent(0, 0, 1000, 1000))
    root.add_child(FakeAccessible("defunct", RaisingComponent()))
    good = root.add_child(FakeAccessible("good", FakeComponent(0, 0, 100, 100)))

    result = locate_accessible_at_point(root, 10, 10)

    assert result is good


def test_stops_descending_when_a_matched_nodes_children_cannot_be_enumerated() -> None:
    root = FakeAccessible("desktop", FakeComponent(0, 0, 1000, 1000))
    window = root.add_child(FakeAccessible("window", FakeComponent(0, 0, 500, 500)))
    broken = window.add_child(RaisingAccessible("broken", FakeComponent(0, 0, 100, 100)))

    result = locate_accessible_at_point(root, 10, 10)

    assert result is broken


def test_returns_none_for_empty_tree() -> None:
    root = FakeAccessible("desktop", None)

    assert locate_accessible_at_point(root, 0, 0) is None
