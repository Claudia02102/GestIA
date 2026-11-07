"""P3-47: el clic debe caer donde estaba el cursor y cerrar la boca no debe desplazar."""

from fakes import FakeMouse

from gestia.control import PointerController, PointerSettings, ScreenArea
from gestia.features import FaceFeatures
from gestia.gestures import (
    DEFAULT_ACTIONS,
    Action,
    GestureEngine,
    GestureEvent,
    GestureId,
    SignalRange,
    default_gesture_settings,
    positional_gesture_forming,
)

NEUTRAL = dict(yaw=0.5, pitch=0.55, eye_left=0.3, eye_right=0.3, mouth_open=0.05,
               brow_raise=0.2, smile=0.4)
RANGES = {
    GestureId.MOUTH_OPEN: SignalRange(0.05, 0.45),
    GestureId.PUCKER: SignalRange(0.4, 0.33),
    GestureId.SMILE: SignalRange(0.4, 0.47),
}


def face(**changes: float) -> FaceFeatures:
    return FaceFeatures(**{**NEUTRAL, **changes})


def engine() -> GestureEngine:
    settings = default_gesture_settings()
    for item in settings.values():
        item.hold_ms = 300
    item = GestureEngine()
    item.configure(settings, RANGES, DEFAULT_ACTIONS)
    return item


def run(gestures: GestureEngine, features: FaceFeatures, start: int, end: int):
    events = []
    for ts in range(start, end, 33):
        events.extend(gestures.update(features, ts).events)
    return [event.gesture for event in events]


def test_clicks_are_on_the_winks_by_default() -> None:
    settings = default_gesture_settings()
    assert DEFAULT_ACTIONS[GestureId.WINK_LEFT] is Action.LEFT_CLICK
    assert DEFAULT_ACTIONS[GestureId.WINK_RIGHT] is Action.RIGHT_CLICK
    assert settings[GestureId.WINK_LEFT].enabled and settings[GestureId.WINK_RIGHT].enabled
    assert len(set(DEFAULT_ACTIONS.values())) == len(DEFAULT_ACTIONS)


def test_closing_the_mouth_does_not_count_as_pucker() -> None:
    gestures = engine()
    assert run(gestures, face(mouth_open=0.45), 0, 600) == [GestureId.MOUTH_OPEN]
    # Al cerrar, los labios se juntan unos instantes: no debe activarse el desplazamiento.
    assert run(gestures, face(smile=0.34), 600, 1000) == []
    assert run(gestures, face(), 1000, 1200) == []


def test_pucker_still_works_after_the_pause() -> None:
    gestures = engine()
    run(gestures, face(mouth_open=0.45), 0, 600)
    run(gestures, face(), 600, 1400)
    assert run(gestures, face(smile=0.34), 1400, 2000) == [GestureId.PUCKER]


def test_cursor_is_held_while_a_click_gesture_forms() -> None:
    settings = default_gesture_settings()
    half_mouth = {GestureId.MOUTH_OPEN: 0.4}
    assert positional_gesture_forming(half_mouth, settings, DEFAULT_ACTIONS)
    assert not positional_gesture_forming({GestureId.MOUTH_OPEN: 0.1}, settings, DEFAULT_ACTIONS)
    # Recentrar no depende de la posición: no fija el cursor.
    assert not positional_gesture_forming({GestureId.BROW_RAISE: 0.9}, settings, DEFAULT_ACTIONS)
    # Girar la cabeza hace que un ojo parezca más cerrado: un guiño no debe trabar el cursor.
    assert not positional_gesture_forming({GestureId.WINK_LEFT: 0.9}, settings, DEFAULT_ACTIONS)
    disabled_map = {**DEFAULT_ACTIONS, GestureId.MOUTH_OPEN: Action.QUICK_MENU}
    assert not positional_gesture_forming(half_mouth, settings, disabled_map)


def test_click_lands_where_the_cursor_was_before_the_gesture() -> None:
    mouse = FakeMouse()
    controller = PointerController(mouse, ScreenArea(0, 0, 1921, 1081),
                                   PointerSettings(smoothing=0))
    controller.update((0.5, 0.5), (), 0)
    # Abrir la boca desplaza la inclinación medida: el cursor no debe seguirla.
    controller.update((0.5, 0.45), (), 33, hold_position=True)
    event = GestureEvent(GestureId.MOUTH_OPEN, Action.DOUBLE_CLICK, 66)
    controller.update((0.5, 0.42), (event,), 66, hold_position=True)
    assert mouse.of("click")[0][3] == (960, 540)
    controller.update((0.5, 0.3), (), 99)
    assert mouse.position == (960, 324)
