"""Tutorial interactivo y modo de práctica (P3-26), sin dependencias de Qt.

El tutorial enseña, con el mapeo y la calibración de la persona, a mover el puntero y a hacer
cada gesto activo. El modo de práctica es un tablero libre para ensayar. En ambos los gestos
solo actúan sobre la pantalla del tutorial: nunca mueven el cursor ni hacen clic en el sistema.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from gestia.gestures import (
    ACTION_TEXT,
    GESTURES,
    SELECTION_ACTIONS,
    Action,
    GestureEvent,
    GestureId,
    GestureSettings,
)

TARGET_RADIUS = 0.09  # fracción de la pantalla del tutorial
REACH_MS = 300  # tiempo sobre un objetivo para alcanzarlo en «Mover el puntero»
ADVANCE_MS = 1500  # pausa para ver el resultado antes de la lección siguiente
EXIT_TARGET = "salir"

# Orden de enseñanza: primero los clics, al final la pausa (que se enseña con más contexto).
ACTION_ORDER = (
    Action.LEFT_CLICK,
    Action.RIGHT_CLICK,
    Action.DOUBLE_CLICK,
    Action.DRAG,
    Action.SCROLL,
    Action.QUICK_MENU,
    Action.RECALIBRATE,
    Action.PAUSE,
)
ACTION_TIP = {
    Action.LEFT_CLICK: "Sirve para pulsar botones y enlaces.",
    Action.RIGHT_CLICK: "Abre el menú con más opciones de lo que está bajo el cursor.",
    Action.DOUBLE_CLICK: "Abre archivos y programas.",
    Action.DRAG: "En uso real agarra lo que está bajo el cursor; repite el gesto para soltarlo.",
    Action.SCROLL: "En uso real activa el desplazamiento: aleja la cabeza del centro para "
    "recorrer la página y repite el gesto para salir.",
    Action.QUICK_MENU: "Abre el menú de acciones rápidas para cambiar de ventana o abrir apps.",
    Action.RECALIBRATE: "Si cambias de postura, quédate quieto tras el gesto y se recentra.",
    Action.PAUSE: "Pausa el control para descansar o conversar; el mismo gesto lo reanuda.",
}


class LessonKind(StrEnum):
    MOVE = "move"
    GESTURE = "gesture"
    PRACTICE = "practice"
    DONE = "done"


@dataclass(frozen=True, slots=True)
class Target:
    id: str
    x: float
    y: float
    label: str


@dataclass(frozen=True, slots=True)
class Lesson:
    kind: LessonKind
    title: str
    instruction: str
    targets: tuple[Target, ...] = ()
    gesture: GestureId | None = None
    action: Action | None = None

    @property
    def needs_target(self) -> bool:
        return self.action in SELECTION_ACTIONS


@dataclass(frozen=True, slots=True)
class TutorialUpdate:
    index: int
    lesson: Lesson
    pointer: tuple[float, float] | None
    hovered: str | None
    done: frozenset[str]
    message: str
    success: bool = False  # algo se logró en este fotograma (para el sonido)
    finished: bool = False


MOVE_TARGETS = (
    Target("m1", 0.18, 0.22, "1"),
    Target("m2", 0.82, 0.22, "2"),
    Target("m3", 0.82, 0.78, "3"),
    Target("m4", 0.18, 0.78, "4"),
)
GESTURE_TARGET = Target("objetivo", 0.5, 0.5, "Aquí")
PRACTICE_TARGETS = (
    Target("abrir", 0.2, 0.3, "Abrir"),
    Target("guardar", 0.5, 0.3, "Guardar"),
    Target("enviar", 0.8, 0.3, "Enviar"),
    Target("copiar", 0.2, 0.7, "Copiar"),
    Target("pegar", 0.5, 0.7, "Pegar"),
    Target(EXIT_TARGET, 0.8, 0.7, "Salir"),
)


def gesture_name(gesture: GestureId) -> str:
    return GESTURES[gesture].name


def build_lessons(
    settings: Mapping[GestureId, GestureSettings],
    actions: Mapping[GestureId, Action],
    is_calibrated: Callable[[GestureId], bool],
) -> list[Lesson]:
    """Lecciones según los gestos que la persona tiene activos y calibrados."""
    lessons = [
        Lesson(
            LessonKind.MOVE,
            "Mover el puntero",
            "Gira la cabeza suavemente para llevar el puntero naranja a cada círculo numerado.",
            MOVE_TARGETS,
        )
    ]
    usable = [
        (gesture, actions[gesture])
        for gesture in GESTURES
        if settings[gesture].enabled and is_calibrated(gesture) and gesture in actions
    ]
    usable.sort(key=lambda item: ACTION_ORDER.index(item[1]) if item[1] in ACTION_ORDER else 99)
    for gesture, action in usable:
        name, what = gesture_name(gesture), ACTION_TEXT[action]
        if action in SELECTION_ACTIONS:
            how = f"Lleva el puntero al círculo y haz «{name}»."
            targets: tuple[Target, ...] = (GESTURE_TARGET,)
        else:
            how = f"Haz «{name}» cuando quieras."
            targets = ()
        lessons.append(
            Lesson(
                LessonKind.GESTURE,
                f"{what}: {name.lower()}",
                f"{how} {ACTION_TIP.get(action, '')}".strip(),
                targets,
                gesture,
                action,
            )
        )
    lessons.append(
        Lesson(
            LessonKind.DONE,
            "¡Listo!",
            "Ya conoces tus gestos. Puedes repetir este tutorial o practicar libremente cuando "
            "quieras con los botones «Tutorial» y «Practicar».",
        )
    )
    return lessons


def practice_lessons() -> list[Lesson]:
    return [
        Lesson(
            LessonKind.PRACTICE,
            "Modo de práctica",
            "Ensaya libremente: tus gestos solo actúan en esta pantalla. Para terminar, haz clic "
            "en «Salir».",
            PRACTICE_TARGETS,
        )
    ]


def _distance(pointer: tuple[float, float], target: Target) -> float:
    return math.hypot(pointer[0] - target.x, pointer[1] - target.y)


@dataclass(slots=True)
class TutorialSession:
    """Avanza por las lecciones con el puntero virtual y los gestos reconocidos."""

    lessons: list[Lesson]
    advance_ms: int = ADVANCE_MS
    index: int = 0
    done: set[str] = field(default_factory=set)
    _hover_since: dict[str, int] = field(default_factory=dict)
    _completed_at: int | None = None
    _message: str = ""
    finished: bool = False

    def __post_init__(self) -> None:
        if not self.lessons:
            raise ValueError("El tutorial necesita al menos una lección")
        self._message = self.lessons[0].instruction

    @property
    def lesson(self) -> Lesson:
        return self.lessons[self.index]

    @property
    def practice(self) -> bool:
        return self.lesson.kind is LessonKind.PRACTICE

    def go_to(self, index: int) -> None:
        self.index = max(0, min(len(self.lessons) - 1, index))
        self.done = set()
        self._hover_since = {}
        self._completed_at = None
        self._message = self.lesson.instruction
        self.finished = False

    def skip(self) -> None:
        self.go_to(self.index + 1)

    def restart(self) -> None:
        self.go_to(0)

    def hovered(self, pointer: tuple[float, float] | None) -> Target | None:
        if pointer is None:
            return None
        inside = [t for t in self.lesson.targets if _distance(pointer, t) <= TARGET_RADIUS]
        return min(inside, key=lambda t: _distance(pointer, t), default=None)

    def feed(
        self,
        pointer: tuple[float, float] | None,
        events: Iterable[GestureEvent],
        now_ms: int,
    ) -> TutorialUpdate:
        events = list(events)
        target = self.hovered(pointer)
        success = False
        lesson = self.lesson
        if self._completed_at is not None:
            waited = now_ms - self._completed_at >= self.advance_ms
            if waited and lesson.kind is not LessonKind.DONE:
                self.skip()
                lesson = self.lesson
                target = self.hovered(pointer)
        elif lesson.kind is LessonKind.MOVE:
            success = self._feed_move(target, now_ms)
        elif lesson.kind is LessonKind.GESTURE:
            success = self._feed_gesture(target, events, now_ms)
        elif lesson.kind is LessonKind.PRACTICE:
            success = self._feed_practice(target, events)
        if pointer is None and not self.finished:
            self._message = "No vemos tu rostro: colócate frente a la cámara."
        elif pointer is not None and self._message.startswith("No vemos"):
            self._message = lesson.instruction
        if lesson.kind is LessonKind.DONE:
            self.finished = True
        return TutorialUpdate(
            self.index,
            self.lesson,
            pointer,
            None if target is None else target.id,
            frozenset(self.done),
            self._message,
            success,
            self.finished,
        )

    def _complete(self, now_ms: int, message: str) -> None:
        self._completed_at = now_ms
        self._message = message

    def _feed_move(self, target: Target | None, now_ms: int) -> bool:
        for key in list(self._hover_since):
            if target is None or key != target.id:
                del self._hover_since[key]
        if target is None or target.id in self.done:
            return False
        since = self._hover_since.setdefault(target.id, now_ms)
        if now_ms - since < REACH_MS:
            return False
        self.done.add(target.id)
        remaining = len(self.lesson.targets) - len(self.done)
        if remaining:
            self._message = f"¡Bien! Faltan {remaining}."
        else:
            self._complete(now_ms, "¡Muy bien! Ya mueves el puntero con la cabeza.")
        return True

    def _feed_gesture(self, target: Target | None, events: list[GestureEvent], now_ms: int) -> bool:
        lesson = self.lesson
        for event in events:
            if event.gesture is not lesson.gesture:
                self._message = (
                    f"Eso fue «{gesture_name(event.gesture)}» "
                    f"({ACTION_TEXT[event.action].lower()}). Ahora prueba "
                    f"«{gesture_name(lesson.gesture)}»."  # type: ignore[arg-type]
                )
                continue
            if lesson.needs_target and target is None:
                self._message = "¡Gesto reconocido! Ahora hazlo con el puntero sobre el círculo."
                continue
            if target is not None:
                self.done.add(target.id)
            self._complete(now_ms, f"¡Perfecto! {ACTION_TEXT[event.action]} reconocido.")
            return True
        return False

    def _feed_practice(self, target: Target | None, events: list[GestureEvent]) -> bool:
        success = False
        for event in events:
            name, what = gesture_name(event.gesture), ACTION_TEXT[event.action]
            if event.action in SELECTION_ACTIONS and target is not None:
                if target.id == EXIT_TARGET:
                    self.finished = True
                    self._message = "Práctica terminada."
                    return True
                self.done.add(target.id)
                self._message = f"{name} → {what} en «{target.label}»."
                success = True
            else:
                self._message = f"{name} → {what}."
                success = True
        return success
