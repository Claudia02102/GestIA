"""P3-19: pausar y reanudar el control con un gesto (criterios de aceptación de Jira)."""

import os

from test_control import FakeMouse

from gestia.control import ControlMode, PointerController, PointerSettings, ScreenArea
from gestia.features import FaceFeatures
from gestia.gestures import (
    DEFAULT_ACTIONS,
    Action,
    GestureEngine,
    GestureId,
    SignalRange,
    acts_while_paused,
    default_gesture_settings,
    resume_hint,
)

NEUTRAL = dict(yaw=0.5, pitch=0.55, eye_left=0.3, eye_right=0.3, mouth_open=0.05,
               brow_raise=0.2, smile=0.4)
RANGES = {
    GestureId.BLINK: SignalRange(0.3, 0.05),
    GestureId.WINK_LEFT: SignalRange(0.0, -0.25),
    GestureId.WINK_RIGHT: SignalRange(0.0, -0.25),
}
EYES_CLOSED = dict(eye_left=0.05, eye_right=0.05)
LEFT_WINK = dict(eye_left=0.05, eye_right=0.3)


def face(**changes: float) -> FaceFeatures:
    return FaceFeatures(**{**NEUTRAL, **changes})


class Session:
    """Motor de gestos + controlador del puntero con un mouse simulado."""

    def __init__(self) -> None:
        self.engine = GestureEngine()
        self.engine.configure(default_gesture_settings(), RANGES, DEFAULT_ACTIONS)
        self.mouse = FakeMouse()
        self.controller = PointerController(
            self.mouse, ScreenArea(0, 0, 1921, 1081), PointerSettings(smoothing=0)
        )
        self.ts = 0

    def hold(self, ms: int, pointer: tuple[float, float], **changes: float) -> None:
        for _ in range(0, ms, 33):
            frame = self.engine.update(face(**changes), self.ts)
            self.controller.update(pointer, frame.events, self.ts)
            self.ts += 33


def paused_session() -> Session:
    session = Session()
    session.hold(200, (0.5, 0.5))
    session.hold(1000, (0.5, 0.5), **EYES_CLOSED)
    session.hold(300, (0.5, 0.5))
    assert session.controller.paused
    return session


def test_pause_gesture_stops_the_cursor() -> None:
    session = paused_session()
    before = session.mouse.position
    session.hold(500, (0.1, 0.9))
    assert session.mouse.position == before
    assert session.controller.update((0.1, 0.9), (), session.ts).mode is ControlMode.PAUSED


def test_click_gestures_do_nothing_while_paused() -> None:
    session = paused_session()
    session.hold(700, (0.5, 0.5), **LEFT_WINK)
    session.hold(300, (0.5, 0.5))
    assert session.mouse.of("click") == [] and session.mouse.of("press") == []


def test_resume_gesture_gives_control_back() -> None:
    session = paused_session()
    session.hold(1000, (0.5, 0.5), **EYES_CLOSED)
    session.hold(300, (0.2, 0.2))
    assert not session.controller.paused
    assert session.mouse.position == (384, 216)


def test_short_natural_blink_does_not_pause() -> None:
    session = Session()
    session.hold(300, (0.5, 0.5), **EYES_CLOSED)
    session.hold(300, (0.5, 0.5))
    assert not session.controller.paused


def test_only_the_resume_gesture_acts_while_paused() -> None:
    assert acts_while_paused(Action.PAUSE)
    for action in (Action.RECALIBRATE, Action.QUICK_MENU, Action.LEFT_CLICK, None):
        assert not acts_while_paused(action)


def test_resume_hint_names_the_active_pause_gesture() -> None:
    settings = default_gesture_settings()
    assert resume_hint(settings, DEFAULT_ACTIONS) == (
        "Para reanudar: cerrar ambos ojos o Ctrl+Alt+P"
    )
    settings[GestureId.BLINK].enabled = False
    assert resume_hint(settings, DEFAULT_ACTIONS) == "Para reanudar: Ctrl+Alt+P"


def test_pause_indicator_shows_how_to_resume() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from gestia.ui_widgets import PauseIndicator

    app = QApplication.instance() or QApplication([])
    indicator = PauseIndicator()
    indicator.show_paused("Para reanudar: Ctrl+Alt+P")
    assert indicator.isVisible() and indicator.hint.text() == "Para reanudar: Ctrl+Alt+P"
    assert indicator.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    indicator.close()
    app.processEvents()
