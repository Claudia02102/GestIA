"""P3-22: filtrado de gestos involuntarios (criterios de aceptación de Jira)."""

import pytest

from gestia.features import FaceFeatures
from gestia.gestures import (
    DEFAULT_ACTIONS,
    Action,
    GestureEngine,
    GestureId,
    SignalRange,
    default_gesture_settings,
)

NEUTRAL = dict(yaw=0.5, pitch=0.55, eye_left=0.3, eye_right=0.3, mouth_open=0.05,
               brow_raise=0.2, smile=0.4)
RANGES = {
    GestureId.BLINK: SignalRange(0.3, 0.05),
    GestureId.WINK_LEFT: SignalRange(0.0, -0.25),
    GestureId.WINK_RIGHT: SignalRange(0.0, -0.25),
    GestureId.MOUTH_OPEN: SignalRange(0.05, 0.45),
    GestureId.SMILE: SignalRange(0.4, 0.47),
    GestureId.PUCKER: SignalRange(0.4, 0.33),
}
FRAME_MS = 33


class Camera:
    """Reproduce cuadros a 30 fps y guarda las acciones que dispara el motor."""

    def __init__(self, sensitivity: int = 5) -> None:
        settings = default_gesture_settings()
        for item in settings.values():
            item.sensitivity = sensitivity
        self.engine = GestureEngine()
        self.engine.configure(settings, RANGES, DEFAULT_ACTIONS)
        self.ts = 0
        self.actions: list[Action] = []
        self.speaking = False

    def show(self, ms: int, **changes: float) -> None:
        for _ in range(max(1, ms // FRAME_MS)):
            frame = self.engine.update(FaceFeatures(**{**NEUTRAL, **changes}), self.ts)
            self.actions += [event.action for event in frame.events]
            self.speaking = frame.speaking
            self.ts += FRAME_MS


def natural_blink(camera: Camera, closed_ms: int, leading: str) -> None:
    """Parpadeo real: un ojo empieza a cerrarse y se abre un poco antes que el otro."""
    other = "eye_right" if leading == "eye_left" else "eye_left"
    camera.show(66, **{leading: 0.16, other: 0.26})
    camera.show(closed_ms, eye_left=0.06, eye_right=0.06)
    camera.show(66, **{leading: 0.26, other: 0.14})


def talk(camera: Camera, seconds: int, smiling: bool = False) -> None:
    """Sílabas: la boca se abre de forma corta y desigual, a veces con una vocal larga."""
    smile = {"smile": 0.47} if smiling else {}
    pattern = [(165, 0.25), (132, 0.12), (198, 0.33), (99, 0.1), (330, 0.3), (132, 0.08),
               (165, 0.22), (231, 0.06), (495, 0.31), (165, 0.1)]
    end = camera.ts + seconds * 1000
    while camera.ts < end:
        for ms, mouth in pattern:
            camera.show(ms, mouth_open=mouth, **smile)


# --- Criterio 1: parpadear de forma natural durante un minuto no genera clics ----------------


@pytest.mark.parametrize("sensitivity", [5, 10])
def test_natural_blinking_for_a_minute_makes_no_click(sensitivity) -> None:
    # Los guiños y el parpadeo compiten en el grupo «ojos»: gana el más marcado, y un
    # parpadeo natural (< 500 ms) no llega a los 800 ms de la pausa.
    camera = Camera(sensitivity)
    for second in range(0, 60, 3):
        natural_blink(camera, closed_ms=99 + (second % 6) * 66,
                      leading="eye_left" if second % 2 else "eye_right")
        camera.show(2600)
    assert camera.actions == []


def test_slow_asymmetric_blink_is_not_a_wink() -> None:
    camera = Camera()
    # El ojo izquierdo cierra del todo y el derecho casi: sigue siendo un parpadeo.
    camera.show(500, eye_left=0.05, eye_right=0.12)
    camera.show(300)
    assert camera.actions == []


# --- Criterio 2: hablar y sonreír no ejecuta acciones ----------------------------------------


def test_talking_does_not_trigger_mouth_gestures() -> None:
    camera = Camera()
    talk(camera, seconds=20)
    assert camera.actions == []


def test_talking_while_smiling_does_not_trigger_actions() -> None:
    camera = Camera()
    talk(camera, seconds=5)
    talk(camera, seconds=15, smiling=True)
    assert camera.actions == []


def test_speech_is_detected_and_ends_after_silence() -> None:
    camera = Camera()
    talk(camera, seconds=3)
    assert camera.speaking
    camera.show(1500)
    assert not camera.speaking


def test_brief_social_smile_does_not_drag() -> None:
    camera = Camera()
    camera.show(264, smile=0.47)
    camera.show(300)
    assert camera.actions == []


# --- Criterio 3: sostener el gesto el tiempo configurado sí ejecuta la acción ----------------


def test_held_wink_still_clicks() -> None:
    camera = Camera()
    camera.show(500, eye_left=0.05, eye_right=0.3)
    assert camera.actions == [Action.LEFT_CLICK]


def test_held_mouth_and_smile_still_work_when_not_talking() -> None:
    camera = Camera()
    camera.show(500, mouth_open=0.45)
    camera.show(800)
    camera.show(500, smile=0.47)
    assert camera.actions == [Action.DOUBLE_CLICK, Action.DRAG]


def test_deliberate_gesture_works_again_after_talking() -> None:
    camera = Camera()
    talk(camera, seconds=5)
    camera.show(1500)
    camera.show(500, mouth_open=0.45)
    assert camera.actions == [Action.DOUBLE_CLICK]


def test_hold_time_comes_from_the_profile() -> None:
    settings = default_gesture_settings()
    settings[GestureId.WINK_LEFT].hold_ms = 800
    engine = GestureEngine()
    engine.configure(settings, RANGES, DEFAULT_ACTIONS)
    wink = FaceFeatures(**{**NEUTRAL, "eye_left": 0.05})
    fired = [
        event.action
        for ts in range(0, 600, FRAME_MS)
        for event in engine.update(wink, ts).events
    ]
    assert fired == []
    assert [event.action for event in engine.update(wink, 820).events] == [Action.LEFT_CLICK]

