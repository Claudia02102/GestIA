from gestia.control import (
    Button,
    ControlMode,
    OneEuroFilter,
    PointerController,
    PointerSettings,
    ScreenArea,
    apply_speed,
)
from gestia.gestures import Action, GestureEvent, GestureId

SCREEN = ScreenArea(0, 0, 1921, 1081)
CENTER = (0.5, 0.5)


class FakeMouse:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.position: tuple[int, int] | None = None

    def move(self, x: int, y: int) -> None:
        self.position = (x, y)
        self.calls.append(("move", x, y))

    def press(self, button: Button) -> None:
        self.calls.append(("press", button, self.position))

    def release(self, button: Button) -> None:
        self.calls.append(("release", button, self.position))

    def click(self, button: Button, count: int = 1) -> None:
        self.calls.append(("click", button, count, self.position))

    def scroll(self, dx: int, dy: int) -> None:
        self.calls.append(("scroll", dx, dy))

    def escape(self) -> None:
        self.calls.append(("escape",))

    def of(self, kind: str) -> list[tuple]:
        return [call for call in self.calls if call[0] == kind]


def event(action: Action) -> GestureEvent:
    return GestureEvent(GestureId.MOUTH_OPEN, action, 0)


def make(**settings) -> tuple[PointerController, FakeMouse]:
    mouse = FakeMouse()
    values = {"smoothing": 0, **settings}
    return PointerController(mouse, SCREEN, PointerSettings(**values)), mouse


def feed(controller, pointer, start: int, end: int, events=(), step: int = 33):
    status = None
    for ts in range(start, end, step):
        status = controller.update(pointer, events if ts == start else (), ts)
    return status


def test_cursor_follows_head_and_reaches_all_edges() -> None:
    controller, mouse = make()
    controller.update(CENTER, (), 0)
    assert mouse.position == (960, 540)
    for pointer, expected in (((0.0, 0.5), (0, 540)), ((1.0, 0.5), (1920, 540)),
                              ((0.5, 0.0), (960, 0)), ((0.5, 1.0), (960, 1080))):
        controller.update(pointer, (), 100)
        assert mouse.position == expected


def test_still_head_does_not_move_cursor() -> None:
    controller, mouse = make(smoothing=5, dead_zone_px=4)
    feed(controller, CENTER, 0, 500)
    moves = len(mouse.of("move"))
    for ts, jitter in zip(range(500, 3000, 33), [0.0005, -0.0005] * 50, strict=False):
        controller.update((0.5 + jitter, 0.5 - jitter), (), ts)
    assert len(mouse.of("move")) == moves


def test_speed_reduces_head_motion_needed() -> None:
    assert apply_speed((0.75, 0.5), 2.0) == (1.0, 0.5)
    assert apply_speed((0.6, 0.4), 1.0) == (0.6, 0.4)
    controller, mouse = make(speed=2.0)
    controller.update((0.75, 0.5), (), 0)
    assert mouse.position == (1920, 540)


def test_smoothing_reduces_jitter() -> None:
    raw, smooth = OneEuroFilter(0.0), OneEuroFilter(0.6)
    raw.min_cutoff = 1e9
    signal = [0.5 + (0.01 if i % 2 else -0.01) for i in range(60)]
    raw_out = [raw(v, i * 33) for i, v in enumerate(signal)][30:]
    smooth_out = [smooth(v, i * 33) for i, v in enumerate(signal)][30:]
    assert max(smooth_out) - min(smooth_out) < (max(raw_out) - min(raw_out)) / 3


def test_each_click_gesture_runs_once_at_cursor_position() -> None:
    controller, mouse = make()
    controller.update((0.25, 0.25), (event(Action.LEFT_CLICK),), 0)
    controller.update((0.25, 0.25), (event(Action.RIGHT_CLICK),), 33)
    controller.update((0.25, 0.25), (event(Action.DOUBLE_CLICK),), 66)
    controller.update((0.25, 0.25), (), 99)
    position = (480, 270)
    assert mouse.of("click") == [
        ("click", Button.LEFT, 1, position),
        ("click", Button.RIGHT, 1, position),
        ("click", Button.LEFT, 2, position),
    ]


def test_dwell_click_after_configured_time_only_when_still() -> None:
    controller, mouse = make(dwell_enabled=True, dwell_ms=1000, dwell_radius_px=30)
    feed(controller, CENTER, 0, 900)
    assert mouse.of("click") == []
    feed(controller, (0.7, 0.5), 900, 1800)
    assert mouse.of("click") == []
    feed(controller, (0.7, 0.5), 1800, 3500)
    assert len(mouse.of("click")) == 1


def test_dwell_time_change_applies() -> None:
    controller, mouse = make(dwell_enabled=True, dwell_ms=2000)
    feed(controller, CENTER, 0, 1500)
    controller.configure(PointerSettings(smoothing=0, dwell_enabled=True, dwell_ms=500))
    feed(controller, CENTER, 1500, 2100)
    assert len(mouse.of("click")) == 1


def test_drag_and_drop_with_gesture() -> None:
    controller, mouse = make()
    controller.update((0.25, 0.25), (event(Action.DRAG),), 0)
    assert controller.mode is ControlMode.DRAGGING
    feed(controller, (0.75, 0.75), 33, 300)
    controller.update((0.75, 0.75), (event(Action.DRAG),), 300)
    assert controller.mode is ControlMode.NORMAL
    assert mouse.of("press") == [("press", Button.LEFT, (480, 270))]
    assert mouse.of("release") == [("release", Button.LEFT, (1440, 810))]
    assert mouse.of("click") == []


def test_losing_face_during_drag_cancels_without_moving_item() -> None:
    controller, mouse = make()
    controller.update((0.25, 0.25), (event(Action.DRAG),), 0)
    feed(controller, (0.75, 0.75), 33, 300)
    status = controller.update(None, (), 300)
    assert status.mode is ControlMode.NO_FACE
    assert ("escape",) in mouse.calls
    assert mouse.of("release") == [("release", Button.LEFT, (480, 270))]
    moves = len(mouse.of("move"))
    controller.update(None, (), 333)
    assert len(mouse.of("move")) == moves


def test_scroll_mode_scrolls_and_returns_to_normal_control() -> None:
    controller, mouse = make(scroll_speed=10)
    controller.update(CENTER, (event(Action.SCROLL),), 0)
    assert controller.mode is ControlMode.SCROLLING
    feed(controller, (0.5, 0.1), 33, 1000)
    up = sum(call[2] for call in mouse.of("scroll"))
    feed(controller, (0.5, 0.9), 1000, 2000)
    assert up > 0
    assert sum(call[2] for call in mouse.of("scroll")) < up
    feed(controller, (0.95, 0.5), 2000, 2500)
    assert sum(call[1] for call in mouse.of("scroll")) > 0
    moves = len(mouse.of("move"))
    assert moves == 1  # el cursor no se mueve mientras se desplaza
    controller.update((0.3, 0.5), (event(Action.SCROLL),), 2500)
    assert controller.mode is ControlMode.NORMAL
    assert mouse.position == (576, 540)
    assert mouse.of("click") == []


def test_pause_blocks_movement_and_clicks() -> None:
    controller, mouse = make()
    controller.update(CENTER, (), 0)
    controller.update(CENTER, (event(Action.PAUSE),), 33)
    status = controller.update((0.1, 0.1), (event(Action.LEFT_CLICK),), 66)
    assert status.mode is ControlMode.PAUSED
    assert mouse.of("click") == [] and mouse.position == (960, 540)
    controller.update((0.1, 0.1), (event(Action.PAUSE),), 99)
    controller.update((0.1, 0.1), (), 132)
    assert mouse.position == (192, 108)


def test_disabled_control_never_touches_the_mouse() -> None:
    controller, mouse = make(enabled=False)
    status = controller.update((0.1, 0.1), (event(Action.LEFT_CLICK),), 0)
    assert status.mode is ControlMode.DISABLED
    assert mouse.calls == []
