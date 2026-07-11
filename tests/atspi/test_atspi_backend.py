"""Tests for yomikata.atspi.extractor.AtspiAccessibilityBackend.

Uses a fake ``Atspi`` GI module, injected via the ``atspi_module``
constructor parameter, so these exercise the real active-frame-selection
and text-extraction logic without a running AT-SPI bus.
"""

from __future__ import annotations

from yomikata.atspi.extractor import AccessibleTextInfo, AtspiAccessibilityBackend


class FakeComponent:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x, self.y, self.width, self.height = x, y, width, height


class FakeStateSet:
    def __init__(self, active: bool) -> None:
        self._active = active

    def contains(self, state: str) -> bool:
        return state == "ACTIVE" and self._active


class FakeAccessible:
    def __init__(
        self,
        name: str = "",
        children: list[FakeAccessible] | None = None,
        component: FakeComponent | None = None,
        text: str | None = None,
        active: bool = False,
        offset_at_point: int = 0,
    ) -> None:
        self.name = name
        self._children = children or []
        self._component = component
        self.text = text
        self._active = active
        self.offset_at_point = offset_at_point

    def get_component_iface(self) -> FakeComponent | None:
        return self._component

    def get_text_iface(self) -> object | None:
        return object() if self.text is not None else None

    def get_child_count(self) -> int:
        return len(self._children)

    def get_child_at_index(self, index: int) -> FakeAccessible:
        return self._children[index]

    def get_state_set(self) -> FakeStateSet:
        return FakeStateSet(self._active)


class FakeComponentNamespace:
    @staticmethod
    def contains(component: FakeComponent, x: int, y: int, coord_type: str) -> bool:
        return component.x <= x < component.x + component.width and (
            component.y <= y < component.y + component.height
        )


class FakeTextNamespace:
    @staticmethod
    def get_character_count(accessible: FakeAccessible) -> int:
        return len(accessible.text or "")

    @staticmethod
    def get_text(accessible: FakeAccessible, start: int, end: int) -> str:
        return (accessible.text or "")[start:end]

    @staticmethod
    def get_offset_at_point(accessible: FakeAccessible, x: int, y: int, coord_type: str) -> int:
        return accessible.offset_at_point


class FakeCoordType:
    SCREEN = "SCREEN"


class FakeStateType:
    ACTIVE = "ACTIVE"


class FakeAtspiModule:
    Component = FakeComponentNamespace
    Text = FakeTextNamespace
    CoordType = FakeCoordType
    StateType = FakeStateType

    def __init__(self, desktop: FakeAccessible, init_result: int = 0) -> None:
        self._desktop = desktop
        self._init_result = init_result

    def init(self) -> int:
        return self._init_result

    def get_desktop(self, index: int) -> FakeAccessible:
        return self._desktop


def make_desktop(apps: list[FakeAccessible]) -> FakeAccessible:
    return FakeAccessible(name="desktop", children=apps)


def test_finds_text_at_point_within_the_active_frame() -> None:
    label = FakeAccessible(name="label", component=FakeComponent(0, 0, 50, 20), text="東京に行く")
    active_frame = FakeAccessible(
        name="active-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[label],
        active=True,
    )
    app = FakeAccessible(name="app", children=[active_frame])
    desktop = make_desktop([app])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))
    result = backend.get_text_at_point(10, 10)

    assert result == AccessibleTextInfo(text="東京に行く", offset=0)


def test_ignores_non_active_windows_even_if_they_contain_the_point() -> None:
    background_label = FakeAccessible(
        name="background-label", component=FakeComponent(0, 0, 50, 20), text="wrong window"
    )
    background_frame = FakeAccessible(
        name="background-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[background_label],
        active=False,
    )
    background_app = FakeAccessible(name="background-app", children=[background_frame])

    active_label = FakeAccessible(
        name="active-label", component=FakeComponent(0, 0, 50, 20), text="correct window"
    )
    active_frame = FakeAccessible(
        name="active-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[active_label],
        active=True,
    )
    active_app = FakeAccessible(name="active-app", children=[active_frame])

    desktop = make_desktop([background_app, active_app])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))
    result = backend.get_text_at_point(10, 10)

    assert result is not None
    assert result.text == "correct window"


def test_returns_none_when_no_frame_is_active() -> None:
    label = FakeAccessible(name="label", component=FakeComponent(0, 0, 50, 20), text="text")
    frame = FakeAccessible(
        name="frame", component=FakeComponent(0, 0, 100, 100), children=[label], active=False
    )
    app = FakeAccessible(name="app", children=[frame])
    desktop = make_desktop([app])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))

    assert backend.get_text_at_point(10, 10) is None


def test_returns_none_when_active_frame_has_no_text_at_the_point() -> None:
    active_frame = FakeAccessible(
        name="active-frame", component=FakeComponent(0, 0, 100, 100), children=[], active=True
    )
    app = FakeAccessible(name="app", children=[active_frame])
    desktop = make_desktop([app])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))

    assert backend.get_text_at_point(10, 10) is None


def test_returns_none_when_there_are_no_applications() -> None:
    desktop = make_desktop([])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))

    assert backend.get_text_at_point(10, 10) is None


def test_logs_but_does_not_raise_when_init_returns_nonzero() -> None:
    desktop = make_desktop([])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop, init_result=1))

    assert backend.get_text_at_point(0, 0) is None


def test_probes_descendants_when_text_object_reports_unusable_extents() -> None:
    # Models Evince: the page holding the text reports extents in page
    # units, so Component.contains never matches, but its
    # Text.get_offset_at_point still answers in screen coordinates.
    page = FakeAccessible(
        name="page",
        component=FakeComponent(5000, 5000, 3000, 4000),
        text="飲み物はすきです。",
        offset_at_point=1,
    )
    document_frame = FakeAccessible(
        name="document-frame", component=FakeComponent(0, 0, 100, 100), children=[page]
    )
    active_frame = FakeAccessible(
        name="active-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[document_frame],
        active=True,
    )
    app = FakeAccessible(name="app", children=[active_frame])
    desktop = make_desktop([app])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))
    result = backend.get_text_at_point(10, 10)

    assert result == AccessibleTextInfo(text="飲み物はすきです。", offset=1)


def test_descendant_probe_skips_text_objects_not_under_the_point() -> None:
    # Two pages with broken extents; only the second says the point maps to
    # one of its characters.
    page_one = FakeAccessible(
        name="page-1",
        component=FakeComponent(5000, 5000, 10, 10),
        text="wrong page",
        offset_at_point=-1,
    )
    page_two = FakeAccessible(
        name="page-2",
        component=FakeComponent(5000, 5000, 10, 10),
        text="right page",
        offset_at_point=3,
    )
    document_frame = FakeAccessible(
        name="document-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[page_one, page_two],
    )
    active_frame = FakeAccessible(
        name="active-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[document_frame],
        active=True,
    )
    app = FakeAccessible(name="app", children=[active_frame])
    desktop = make_desktop([app])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))
    result = backend.get_text_at_point(10, 10)

    assert result == AccessibleTextInfo(text="right page", offset=3)


def test_descendant_probe_gives_up_beyond_node_budget() -> None:
    # The text object hides behind more siblings than the probe budget
    # allows; extraction must return None rather than scan without bound.
    decoys = [
        FakeAccessible(name=f"decoy-{i}", component=FakeComponent(5000, 5000, 1, 1))
        for i in range(AtspiAccessibilityBackend._PROBE_MAX_NODES)
    ]
    buried_text = FakeAccessible(
        name="buried",
        component=FakeComponent(5000, 5000, 1, 1),
        text="unreachable",
        offset_at_point=0,
    )
    document_frame = FakeAccessible(
        name="document-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[*decoys, buried_text],
    )
    active_frame = FakeAccessible(
        name="active-frame",
        component=FakeComponent(0, 0, 100, 100),
        children=[document_frame],
        active=True,
    )
    app = FakeAccessible(name="app", children=[active_frame])
    desktop = make_desktop([app])

    backend = AtspiAccessibilityBackend(atspi_module=FakeAtspiModule(desktop))

    assert backend.get_text_at_point(10, 10) is None
