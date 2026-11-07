import pytest

from gestia.calibration import (
    AxisRange,
    Calibration,
    CalibrationSession,
    HeadCalibration,
    Recenterer,
    RecenterStatus,
    StepKind,
)
from gestia.config import CalibrationConfig
from gestia.features import FaceFeatures
from gestia.gestures import GestureId, SignalRange

CONFIG = CalibrationConfig()
NEUTRAL = dict(yaw=0.5, pitch=0.55, eye_left=0.3, eye_right=0.3, mouth_open=0.05,
               brow_raise=0.2, smile=0.4)


def face(**changes: float) -> FaceFeatures:
    return FaceFeatures(**{**NEUTRAL, **changes})


class Clock:
    def __init__(self) -> None:
        self.now = 0

    def hold(self, session, features, ms: int, step: int = 33):
        updates = []
        end = self.now + ms
        while self.now < end:
            updates.append(session.feed(features, self.now))
            self.now += step
        return updates


def calibrate_head(session, clock: Clock) -> None:
    for kind, pose in (
        (StepKind.NEUTRAL, face()),
        (StepKind.HEAD_LEFT, face(yaw=0.6)),
        (StepKind.HEAD_RIGHT, face(yaw=0.4)),
        (StepKind.HEAD_UP, face(pitch=0.48)),
        (StepKind.HEAD_DOWN, face(pitch=0.62)),
    ):
        assert session.step.kind is kind
        clock.hold(session, pose, 3000)


def visit_corners(session, clock: Clock) -> None:
    for yaw in (0.6, 0.4):
        for pitch in (0.48, 0.62):
            clock.hold(session, face(yaw=yaw, pitch=pitch), 300)


def test_complete_wizard_with_gestures_only() -> None:
    session = CalibrationSession([GestureId.MOUTH_OPEN, GestureId.BROW_RAISE], CONFIG)
    clock = Clock()
    calibrate_head(session, clock)
    assert session.step.gesture is GestureId.MOUTH_OPEN
    clock.hold(session, face(mouth_open=0.4), 2500)
    assert session.step.gesture is GestureId.BROW_RAISE
    clock.hold(session, face(brow_raise=0.26), 2500)
    assert session.step.kind is StepKind.CORNERS
    clock.hold(session, face(), 1500)
    visit_corners(session, clock)
    assert session.finished
    result = session.result
    assert result is not None
    assert result.gestures[GestureId.MOUTH_OPEN] == SignalRange(0.05, pytest.approx(0.4))
    assert result.head.to_pointer(face(), CONFIG.reach) == (0.5, 0.5)
    assert result.head.to_pointer(face(yaw=0.6, pitch=0.48), CONFIG.reach) == (0.0, 0.0)
    assert result.head.to_pointer(face(yaw=0.4, pitch=0.62), CONFIG.reach) == (1.0, 1.0)


def test_wrong_direction_asks_to_repeat_the_step() -> None:
    session = CalibrationSession([], CONFIG)
    clock = Clock()
    clock.hold(session, face(), 3000)
    clock.hold(session, face(yaw=0.6), 3000)
    assert session.step.kind is StepKind.HEAD_RIGHT
    updates = clock.hold(session, face(yaw=0.62), 3000)
    assert any(u.step_failed and "Repita" in u.message for u in updates)
    assert session.step.kind is StepKind.HEAD_RIGHT
    assert session.attempts >= 2
    clock.hold(session, face(yaw=0.4), 3000)
    assert session.step.kind is StepKind.HEAD_UP


def test_insufficient_movement_times_out_and_repeats() -> None:
    session = CalibrationSession([], CONFIG)
    clock = Clock()
    clock.hold(session, face(), 3000)
    updates = clock.hold(session, face(yaw=0.51), CONFIG.step_timeout_ms + 500)
    assert any(u.step_failed for u in updates)
    assert session.step.kind is StepKind.HEAD_LEFT


def test_unachievable_gesture_is_skipped_after_max_attempts() -> None:
    session = CalibrationSession([GestureId.SMILE], CONFIG)
    clock = Clock()
    calibrate_head(session, clock)
    total = CONFIG.max_gesture_attempts * (CONFIG.step_timeout_ms + 100)
    clock.hold(session, face(), total)
    assert session.skipped == [GestureId.SMILE]
    assert session.step.kind is StepKind.CORNERS


def test_losing_the_face_restarts_the_hold() -> None:
    session = CalibrationSession([], CONFIG)
    clock = Clock()
    clock.hold(session, face(), CONFIG.settle_ms + 1000)
    update = session.feed(None, clock.now)
    assert "rostro" in update.message
    assert session.step.kind is StepKind.NEUTRAL
    clock.hold(session, face(), 1000)
    assert session.step.kind is StepKind.NEUTRAL


def test_failed_corner_check_repeats_only_head_range() -> None:
    session = CalibrationSession([GestureId.MOUTH_OPEN], CONFIG)
    clock = Clock()
    calibrate_head(session, clock)
    clock.hold(session, face(mouth_open=0.4), 2500)
    assert session.step.kind is StepKind.CORNERS
    updates = clock.hold(session, face(), CONFIG.verify_timeout_ms + 2000)
    assert any(u.step_failed for u in updates)
    assert session.step.kind is StepKind.HEAD_LEFT
    for pose in (face(yaw=0.6), face(yaw=0.4), face(pitch=0.48), face(pitch=0.62)):
        clock.hold(session, pose, 3000)
    assert session.step.kind is StepKind.CORNERS
    clock.hold(session, face(), 1500)
    visit_corners(session, clock)
    assert session.finished


def test_axis_range_is_direction_agnostic() -> None:
    axis = AxisRange(neutral=0.5, negative=0.6, positive=0.4)
    assert axis.to_unit(0.5, 1.0) == 0.5
    assert axis.to_unit(0.55, 1.0) == pytest.approx(0.25)
    assert axis.to_unit(0.45, 1.0) == pytest.approx(0.75)
    assert axis.to_unit(0.9, 1.0) == 0.0
    assert axis.to_unit(0.58, 0.8) == pytest.approx(0.0)


def test_calibration_round_trips_through_dict() -> None:
    original = Calibration(
        HeadCalibration(AxisRange(0.5, 0.6, 0.4), AxisRange(0.55, 0.48, 0.62)),
        {GestureId.MOUTH_OPEN: SignalRange(0.05, 0.4)},
        "2026-01-01T00:00:00+00:00",
    )
    assert Calibration.from_dict(original.to_dict()) == original


def test_recenter_keeps_range_and_gestures_and_finishes_quickly() -> None:
    calibration = Calibration(
        HeadCalibration(AxisRange(0.5, 0.6, 0.4), AxisRange(0.55, 0.48, 0.62)),
        {GestureId.MOUTH_OPEN: SignalRange(0.05, 0.4)},
    )
    recenter = Recenterer(CONFIG)
    status, ts = RecenterStatus.COLLECTING, 0
    while status is RecenterStatus.COLLECTING:
        status = recenter.feed(face(yaw=0.53, pitch=0.58), ts)
        ts += 33
    assert status is RecenterStatus.DONE
    assert ts < 5000
    updated = recenter.apply(calibration)
    assert updated.head.to_pointer(face(yaw=0.53, pitch=0.58), 1.0) == (0.5, 0.5)
    assert updated.head.yaw.negative == pytest.approx(0.63)
    assert updated.gestures == calibration.gestures


def test_recenter_fails_if_head_never_settles() -> None:
    recenter = Recenterer(CONFIG)
    status, ts = RecenterStatus.COLLECTING, 0
    while status is RecenterStatus.COLLECTING:
        status = recenter.feed(face(yaw=0.5 + (ts // 33 % 2) * 0.05), ts)
        last, ts = ts, ts + 33
    assert status is RecenterStatus.FAILED
    assert CONFIG.recenter_timeout_ms <= last < CONFIG.recenter_timeout_ms + 33


def test_smile_and_pucker_require_opposite_directions() -> None:
    session = CalibrationSession([GestureId.PUCKER], CONFIG)
    clock = Clock()
    calibrate_head(session, clock)
    assert session.step.gesture is GestureId.PUCKER
    clock.hold(session, face(smile=0.47), 3000)
    assert session.step.gesture is GestureId.PUCKER
    clock.hold(session, face(smile=0.34), 3000)
    assert session.step.kind is StepKind.CORNERS
    assert session.gesture_ranges[GestureId.PUCKER].peak < 0.4
