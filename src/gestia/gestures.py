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
    PUCKER = "pucker"


class Action(StrEnum):
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    DOUBLE_CLICK = "double_click"
    DRAG = "drag"
    PAUSE = "pause"
    RECALIBRATE = "recalibrate"
    SCROLL = "scroll"
    QUICK_MENU = "quick_menu"


ACTION_TEXT = {
    Action.LEFT_CLICK: "Clic izquierdo",
    Action.RIGHT_CLICK: "Clic derecho",
    Action.DOUBLE_CLICK: "Doble clic",
    Action.DRAG: "Arrastrar y soltar",
    Action.PAUSE: "Pausar / reanudar",
    Action.RECALIBRATE: "Recalibrar (recentrar)",
    Action.SCROLL: "Modo desplazamiento",
    Action.QUICK_MENU: "Acciones rápidas (menú)",
}
SELECTION_ACTIONS = frozenset(
    {Action.LEFT_CLICK, Action.RIGHT_CLICK, Action.DOUBLE_CLICK, Action.DRAG}
)
# Acciones que actúan donde está el cursor: mientras se forma un gesto de la boca que las
# tenga asignadas, el cursor se fija.
POSITIONAL_ACTIONS = SELECTION_ACTIONS


@dataclass(frozen=True, slots=True)
class GestureSpec:
    gesture: GestureId
    name: str
    instruction: str
    signal: Callable[[FaceFeatures], float]
    group: str = ""
    # Sentido exigido al calibrar: +1 la medida crece, -1 decrece, 0 cualquiera.
    direction: int = 0
    # El gesto desplaza los puntos que miden la pose (la boca mueve el mentón): mientras se
    # forma, el cursor se fija. Un guiño no la mueve y fijarlo trabaría el cursor (P3-47).
    shifts_head: bool = False


GESTURES: dict[GestureId, GestureSpec] = {
    spec.gesture: spec
    for spec in (
        GestureSpec(
            GestureId.MOUTH_OPEN, "Abrir la boca", "Abra la boca y manténgala abierta",
            lambda f: f.mouth_open, group="mouth", shifts_head=True,
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
            lambda f: f.smile, group="mouth", direction=1, shifts_head=True,
        ),
        # Misma medida que la sonrisa en sentido contrario: la boca se estrecha.
        GestureSpec(
            GestureId.PUCKER, "Fruncir los labios", "Junte los labios como para dar un beso",
            lambda f: f.smile, group="mouth", direction=-1, shifts_head=True,
        ),
    )
}

# P3-47: los clics van en los guiños. Abrir la boca mueve el mentón (y con él la inclinación
# medida) y, al cerrarla, los labios se juntan como al fruncirlos; en el clic principal eso
# desviaba el clic y activaba el desplazamiento.
DEFAULT_ACTIONS: dict[GestureId, Action] = {
    GestureId.WINK_LEFT: Action.LEFT_CLICK,
    GestureId.WINK_RIGHT: Action.RIGHT_CLICK,
    GestureId.MOUTH_OPEN: Action.DOUBLE_CLICK,
    GestureId.SMILE: Action.DRAG,
    GestureId.BLINK: Action.PAUSE,
    GestureId.BROW_RAISE: Action.RECALIBRATE,
    GestureId.PUCKER: Action.SCROLL,
}
DEFAULT_DISABLED: frozenset[GestureId] = frozenset()

MIN_SENSITIVITY, MAX_SENSITIVITY = 1, 10
RELEASE_RATIO = 0.7
# Tras soltar un gesto de la boca, los otros de su grupo esperan: al cerrarla, los labios se
# juntan y parecen fruncidos (P3-47).
GROUP_COOLDOWN_MS = {"mouth": 600}
# P3-22: hablar abre y cierra la boca varias veces seguidas. Con SPEECH_OPENINGS aperturas en
# SPEECH_WINDOW_MS se considera que la persona habla, y los gestos de la boca esperan hasta
# SPEECH_HOLD_MS después de la última apertura.
SPEECH_LEVEL = 0.3
SPEECH_OPENINGS = 3
SPEECH_WINDOW_MS = 2000
SPEECH_HOLD_MS = 1200
# Fracción del umbral a partir de la cual un gesto posicional fija el cursor.
FREEZE_RATIO = 0.5


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


def remap_action(
    actions: Mapping[GestureId, Action], gesture: GestureId, action: Action
) -> dict[GestureId, Action]:
    """Asigna ``action`` a ``gesture``; si otro gesto la tenía, recibe la acción anterior.

    El intercambio mantiene una acción por gesto y evita que dos gestos hagan lo mismo (P3-10).
    """
    mapping = dict(actions)
    previous = mapping.get(gesture)
    for other, current in actions.items():
        if other is not gesture and current is action:
            if previous is None:
                del mapping[other]
            else:
                mapping[other] = previous
    mapping[gesture] = action
    return mapping


def has_left_click(
    settings: Mapping[GestureId, GestureSettings], actions: Mapping[GestureId, Action]
) -> bool:
    """El perfil conserva un gesto activo con clic izquierdo, la acción básica de selección."""
    return any(
        item.enabled and actions.get(gesture) is Action.LEFT_CLICK
        for gesture, item in settings.items()
    )


def acts_while_paused(action: Action | None) -> bool:
    """En pausa solo actúa el gesto de reanudar; los demás se ignoran (P3-19)."""
    return action is Action.PAUSE


def resume_hint(
    settings: Mapping[GestureId, GestureSettings], actions: Mapping[GestureId, Action]
) -> str:
    """Cómo reanudar el control: el gesto activo de pausa (si lo hay) o el atajo."""
    gestures = [
        GESTURES[gesture].name.lower()
        for gesture, action in actions.items()
        if action is Action.PAUSE and gesture in settings and settings[gesture].enabled
    ]
    ways = [*gestures, "Ctrl+Alt+P"]
    return "Para reanudar: " + " o ".join(ways)


def positional_gesture_forming(
    activations: Mapping[GestureId, float],
    settings: Mapping[GestureId, GestureSettings],
    actions: Mapping[GestureId, Action],
) -> bool:
    """Un gesto de la boca con clic o arrastre está en marcha: el cursor no debe moverse.

    Abrir la boca o sonreír baja el mentón o mueve las mejillas, y la pose medida se desvía;
    si el cursor siguiera esa deriva, el clic caería fuera del objetivo (P3-47). Los guiños se
    excluyen: al girar o inclinar la cabeza un ojo parece más cerrado que el otro y el cursor
    se trabaría a mitad de camino.
    """
    return any(
        GESTURES[gesture].shifts_head
        and actions.get(gesture) in POSITIONAL_ACTIONS
        and value >= settings[gesture].threshold * FREEZE_RATIO
        for gesture, value in activations.items()
        if gesture in settings
    )


@dataclass(frozen=True, slots=True)
class GestureEvent:
    gesture: GestureId
    action: Action
    timestamp_ms: int


@dataclass(frozen=True, slots=True)
class GestureFrame:
    activations: dict[GestureId, float] = field(default_factory=dict)
    events: tuple[GestureEvent, ...] = ()
    # P3-22: la persona está hablando y los gestos de la boca no cuentan.
    speaking: bool = False


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
        # Último gesto de cada grupo que estuvo marcado y cuándo dejó de estarlo.
        self._group_owner: dict[str, tuple[GestureId, int]] = {}
        self._mouth_open = False
        self._openings: list[int] = []
        self._speaking_until_ms = -1

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
        self._group_owner = {}
        self._mouth_open = False
        self._openings = []
        self._speaking_until_ms = -1

    def _detect_speech(self, features: FaceFeatures, timestamp_ms: int) -> bool:
        """Varias aperturas cortas de la boca seguidas: la persona habla (P3-22)."""
        mouth = self._ranges.get(GestureId.MOUTH_OPEN)
        if mouth is None:
            return False
        opened = mouth.normalize(features.mouth_open) >= SPEECH_LEVEL
        if opened and not self._mouth_open:
            self._openings = [
                ts for ts in self._openings if timestamp_ms - ts < SPEECH_WINDOW_MS
            ] + [timestamp_ms]
            if len(self._openings) >= SPEECH_OPENINGS:
                self._speaking_until_ms = timestamp_ms + SPEECH_HOLD_MS
        self._mouth_open = opened
        return timestamp_ms < self._speaking_until_ms

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
        for group, leader in leaders.items():
            if group not in GROUP_COOLDOWN_MS:
                continue
            owner = self._group_owner.get(group)
            recent = owner is not None and timestamp_ms - owner[1] < GROUP_COOLDOWN_MS[group]
            if recent and owner is not None and owner[0] is not leader:
                # Otro gesto del grupo acaba de soltarse: este aún no cuenta.
                leaders[group] = owner[0]
            elif activations[leader] >= self._settings[leader].threshold * RELEASE_RATIO:
                self._group_owner[group] = (leader, timestamp_ms)
        speaking = self._detect_speech(features, timestamp_ms)
        events: list[GestureEvent] = []
        for gesture in GESTURES:
            tracker = self._trackers.setdefault(gesture, _Tracker())
            if gesture not in activations:
                tracker.active_since_ms, tracker.fired = None, False
                continue
            settings, value = self._settings[gesture], activations[gesture]
            group = GESTURES[gesture].group
            suppressed = (
                (bool(group) and leaders.get(group) != gesture)
                or (speaking and group == "mouth")
            )
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
        return GestureFrame(activations, tuple(events), speaking)
