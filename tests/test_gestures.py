from gestia.features import FaceFeatures
from gestia.gestures import (
    DEFAULT_ACTIONS,
    Action,
    GestureEngine,
    GestureId,
    GestureSettings,
    SignalRange,
    default_gesture_settings,
    selection_gestures,
    sensitivity_to_threshold,
)

NEUTRAL = FaceFeatures(0.5, 0.55, 0.3, 0.3, 0.05, 0.2, 0.4)
MOUTH = SignalRange(0.05, 0.45)


def mouth(value: float) -> FaceFeatures:
    return FaceFeatures(0.5, 0.55, 0.3, 0.3, value, 0.2, 0.4)


def engine_with(settings: dict, ranges: dict | None = None) -> GestureEngine:
    engine = GestureEngine()
    if ranges is None:
        ranges = {GestureId.MOUTH_OPEN: MOUTH}
    engine.configure(settings, ranges, DEFAULT_ACTIONS)
    return engine


def run(engine: GestureEngine, features: FaceFeatures, start: int, end: int, step: int = 33):
    events = []
    for ts in range(start, end, step):
        events.extend(engine.update(features, ts).events)
    return events


def test_sensitivity_maps_to_decreasing_threshold() -> None:
    assert sensitivity_to_threshold(1) == 0.9
    assert round(sensitivity_to_threshold(10), 6) == 0.2
    assert sensitivity_to_threshold(8) < sensitivity_to_threshold(3)


def test_gesture_fires_once_after_hold_and_rearms_after_release() -> None:
    engine = engine_with({GestureId.MOUTH_OPEN: GestureSettings(True, 5, 300)})
    assert run(engine, mouth(0.45), 0, 290) == []
    events = run(engine, mouth(0.45), 290, 2000)
    assert [(e.gesture, e.action) for e in events] == [(GestureId.MOUTH_OPEN, Action.LEFT_CLICK)]
    run(engine, NEUTRAL, 2000, 2100)
    assert len(run(engine, mouth(0.45), 2100, 2500)) == 1


def test_subtle_gesture_depends_on_sensitivity_and_changes_live() -> None:
    settings = {GestureId.MOUTH_OPEN: GestureSettings(True, 3, 100)}
    engine = engine_with(settings)
    subtle = mouth(0.05 + 0.4 * 0.45)  # 45 % del gesto calibrado
    assert run(engine, subtle, 0, 1000) == []
    settings[GestureId.MOUTH_OPEN].sensitivity = 8
    engine.configure(settings, {GestureId.MOUTH_OPEN: MOUTH}, DEFAULT_ACTIONS)
    assert len(run(engine, subtle, 1000, 1500)) == 1
    settings[GestureId.MOUTH_OPEN].sensitivity = 3
    engine.configure(settings, {GestureId.MOUTH_OPEN: MOUTH}, DEFAULT_ACTIONS)
    run(engine, NEUTRAL, 1500, 1600)
    assert run(engine, subtle, 1600, 3000) == []


def test_disabled_or_uncalibrated_gestures_are_not_recognized() -> None:
    disabled = engine_with({GestureId.MOUTH_OPEN: GestureSettings(False, 10, 0)})
    assert disabled.active_gestures() == []
    assert run(disabled, mouth(0.6), 0, 500) == []
    uncalibrated = engine_with({GestureId.MOUTH_OPEN: GestureSettings(True, 10, 0)}, {})
    assert run(uncalibrated, mouth(0.6), 0, 500) == []


def test_wink_is_not_reported_as_blink() -> None:
    settings = default_gesture_settings()
    for item in settings.values():
        item.enabled, item.hold_ms, item.sensitivity = False, 100, 10
    settings[GestureId.BLINK].enabled = settings[GestureId.WINK_LEFT].enabled = True
    ranges = {
        GestureId.BLINK: SignalRange(0.3, 0.1),
        GestureId.WINK_LEFT: SignalRange(0.0, -0.2),
    }
    engine = engine_with(settings, ranges)
    wink = FaceFeatures(0.5, 0.55, 0.1, 0.3, 0.05, 0.2, 0.4)
    assert [e.gesture for e in run(engine, wink, 0, 600)] == [GestureId.WINK_LEFT]
    run(engine, NEUTRAL, 600, 700)
    both = FaceFeatures(0.5, 0.55, 0.1, 0.1, 0.05, 0.2, 0.4)
    assert [e.gesture for e in run(engine, both, 700, 1300)] == [GestureId.BLINK]


def test_reset_cancels_a_gesture_in_progress() -> None:
    engine = engine_with({GestureId.MOUTH_OPEN: GestureSettings(True, 5, 300)})
    run(engine, mouth(0.45), 0, 200)
    engine.reset()
    assert run(engine, mouth(0.45), 200, 450) == []


def test_selection_gestures_follow_enabled_flags_and_actions() -> None:
    settings = default_gesture_settings()
    assert GestureId.MOUTH_OPEN in selection_gestures(settings, DEFAULT_ACTIONS)
    assert GestureId.BROW_RAISE not in selection_gestures(settings, DEFAULT_ACTIONS)
    for item in settings.values():
        item.enabled = False
    settings[GestureId.BROW_RAISE].enabled = True
    assert selection_gestures(settings, DEFAULT_ACTIONS) == []
