"""Catálogo de gestos faciales y motor de reconocimiento calibrado por persona."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from gestia.features import FaceFeatures


class GestureId(StrEnum):
    MOUTH_OPEN = "mouth_open"
    BLINK = "blink"
    WINK_LEFT = "wink_left"
    WINK_RIGHT = "wink_right"
    BROW_RAISE = "brow_raise"
    SMILE = "smile"


class Action(StrEnum):
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    DOUBLE_CLICK = "double_click"
    DRAG = "drag"
    PAUSE = "pause"
    RECALIBRATE = "recalibrate"


ACTION_TEXT = {
    Action.LEFT_CLICK: "Clic izquierdo",
    Action.RIGHT_CLICK: "Clic derecho",
    Action.DOUBLE_CLICK: "Doble clic",
    Action.DRAG: "Arrastrar y soltar",
    Action.PAUSE: "Pausar / reanudar",
    Action.RECALIBRATE: "Recalibrar (recentrar)",
}
SELECTION_ACTIONS = frozenset(
    {Action.LEFT_CLICK, Action.RIGHT_CLICK, Action.DOUBLE_CLICK, Action.DRAG}
)


@dataclass(frozen=True, slots=True)
class GestureSpec:
    gesture: GestureId
    name: str
    instruction: str
    signal: Callable[[FaceFeatures], float]
    group: str = ""


GESTURES: dict[GestureId, GestureSpec] = {
    spec.gesture: spec
    for spec in (
        GestureSpec(
            GestureId.MOUTH_OPEN, "Abrir la boca", "Abra la boca y manténgala abierta",
            lambda f: f.mouth_open,
        ),
        GestureSpec(
            GestureId.BLINK, "Cerrar ambos ojos", "Cierre ambos ojos hasta oír la señal",
            lambda f: (f.eye_left + f.eye_right) / 2.0, group="eyes",
        ),
        GestureSpec(
            GestureId.WINK_LEFT, "Guiño izquierdo", "Cierre solo el ojo izquierdo",
            lambda f: f.eye_left - f.eye_right, group="eyes",
        ),
        GestureSpec(
            GestureId.WINK_RIGHT, "Guiño derecho", "Cierre solo el ojo derecho",
            lambda f: f.eye_right - f.eye_left, group="eyes",
        ),
        GestureSpec(
            GestureId.BROW_RAISE, "Levantar las cejas", "Levante las cejas y manténgalas",
            lambda f: f.brow_raise,
        ),
        GestureSpec(
            GestureId.SMILE, "Sonreír", "Sonría ampliamente y mantenga la sonrisa",
            lambda f: f.smile,
        ),
    )
}

DEFAULT_ACTIONS: dict[GestureId, Action] = {
    GestureId.MOUTH_OPEN: Action.LEFT_CLICK,
    GestureId.SMILE: Action.RIGHT_CLICK,
    GestureId.WINK_LEFT: Action.DOUBLE_CLICK,
    GestureId.WINK_RIGHT: Action.DRAG,
    GestureId.BLINK: Action.PAUSE,
    GestureId.BROW_RAISE: Action.RECALIBRATE,
}
# Los guiños exigen control independiente de los párpados; se ofrecen desactivados.
DEFAULT_DISABLED = frozenset({GestureId.WINK_LEFT, GestureId.WINK_RIGHT})

MIN_SENSITIVITY, MAX_SENSITIVITY = 1, 10
RELEASE_RATIO = 0.7


def sensitivity_to_threshold(sensitivity: int) -> float:
    """Fracción del gesto calibrado necesaria: 1 → 90 %, 10 → 20 %."""
    level = min(max(int(sensitivity), MIN_SENSITIVITY), MAX_SENSITIVITY)
    return 0.9 - (level - MIN_SENSITIVITY) * 0.7 / (MAX_SENSITIVITY - MIN_SENSITIVITY)


@dataclass(slots=True)
class GestureSettings:
    enabled: bool = True
    sensitivity: int = 5
    hold_ms: int = 400

    @property
    def threshold(self) -> float:
        return sensitivity_to_threshold(self.sensitivity)


def default_gesture_settings() -> dict[GestureId, GestureSettings]:
    settings = {gesture: GestureSettings(gesture not in DEFAULT_DISABLED) for gesture in GESTURES}
    # Un parpadeo natural dura ~100–400 ms; cerrar los ojos exige más tiempo.
    settings[GestureId.BLINK].hold_ms = 800
    settings[GestureId.BROW_RAISE].hold_ms = 1000
    return settings


@dataclass(frozen=True, slots=True)
class SignalRange:
    """Valor en reposo y valor del gesto pleno de una persona; admite ambos sentidos."""

    neutral: float
    peak: float

    def normalize(self, value: float) -> float:
        span = self.peak - self.neutral
        if abs(span) < 1e-9:
            return 0.0
        return min(max((value - self.neutral) / span, 0.0), 1.5)


def selection_gestures(
    settings: Mapping[GestureId, GestureSettings], actions: Mapping[GestureId, Action]
) -> list[GestureId]:
    return [
        gesture
        for gesture, item in settings.items()
        if item.enabled and actions.get(gesture) in SELECTION_ACTIONS
    ]


@dataclass(frozen=True, slots=True)
class GestureEvent:
    gesture: GestureId
    action: Action
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class GestureFrame:
    activations: dict[GestureId, float] = field(default_factory=dict)
    events: tuple[GestureEvent, ...] = ()


@dataclass(slots=True)
class _Tracker:
    active_since_ms: int | None = None
    fired: bool = False


class GestureEngine:
    """Convierte medidas en eventos: umbral por sensibilidad, sostenimiento e histéresis."""

    def __init__(self) -> None:
        self._settings: dict[GestureId, GestureSettings] = {}
        self._ranges: dict[GestureId, SignalRange] = {}
        self._actions: dict[GestureId, Action] = {}
        self._trackers: dict[GestureId, _Tracker] = {}

    def configure(
        self,
        settings: Mapping[GestureId, GestureSettings],
        ranges: Mapping[GestureId, SignalRange],
        actions: Mapping[GestureId, Action],
    ) -> None:
        self._settings = dict(settings)
        self._ranges = dict(ranges)
        self._actions = dict(actions)
        self._trackers = {gesture: self._trackers.get(gesture, _Tracker()) for gesture in GESTURES}

    def active_gestures(self) -> list[GestureId]:
        """Gestos activados y calibrados: los únicos que pueden reconocerse."""
        return [
            gesture
            for gesture, item in self._settings.items()
            if item.enabled and gesture in self._ranges and gesture in GESTURES
        ]

    def reset(self) -> None:
        self._trackers = {gesture: _Tracker() for gesture in GESTURES}

    def update(self, features: FaceFeatures, timestamp_ms: int) -> GestureFrame:
        activations = {
            gesture: self._ranges[gesture].normalize(GESTURES[gesture].signal(features))
            for gesture in self.active_gestures()
        }
        # En un mismo grupo solo cuenta el gesto más marcado: un guiño no es un parpadeo.
        leaders: dict[str, GestureId] = {}
        for gesture, value in activations.items():
            group = GESTURES[gesture].group
            if group and (group not in leaders or value > activations[leaders[group]]):
                leaders[group] = gesture
        events: list[GestureEvent] = []
        for gesture in GESTURES:
            tracker = self._trackers.setdefault(gesture, _Tracker())
            if gesture not in activations:
                tracker.active_since_ms, tracker.fired = None, False
                continue
            settings, value = self._settings[gesture], activations[gesture]
            group = GESTURES[gesture].group
            suppressed = bool(group) and leaders.get(group) != gesture
            if value >= settings.threshold and not suppressed:
                if tracker.active_since_ms is None:
                    tracker.active_since_ms = timestamp_ms
                held = timestamp_ms - tracker.active_since_ms >= settings.hold_ms
                if held and not tracker.fired:
                    tracker.fired = True
                    action = self._actions.get(gesture)
                    if action is not None:
                        events.append(GestureEvent(gesture, action, timestamp_ms))
            else:
                tracker.active_since_ms = None
                if value < settings.threshold * RELEASE_RATIO or suppressed:
                    tracker.fired = False
        return GestureFrame(activations, tuple(events))
