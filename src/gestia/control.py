"""Control del puntero del sistema operativo (Épica E3: HU-12 a HU-18).

``PointerController`` es lógica pura: recibe la posición normalizada de la cabeza y los eventos
de gesto, y emite órdenes a un ``MouseBackend``. El backend real usa pynput; las pruebas usan
uno simulado.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from gestia.gestures import Action, GestureEvent


class Button(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class MouseBackend(Protocol):
    def move(self, x: int, y: int) -> None: ...
    def press(self, button: Button) -> None: ...
    def release(self, button: Button) -> None: ...
    def click(self, button: Button, count: int = 1) -> None: ...
    def scroll(self, dx: int, dy: int) -> None: ...
    def escape(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ScreenArea:
    left: int
    top: int
    width: int
    height: int

    def to_pixels(self, x: float, y: float) -> tuple[int, int]:
        return (
            self.left + round(min(max(x, 0.0), 1.0) * (self.width - 1)),
            self.top + round(min(max(y, 0.0), 1.0) * (self.height - 1)),
        )


@dataclass(slots=True)
class PointerSettings:
    enabled: bool = True
    speed: float = 1.0
    smoothing: int = 5
    dead_zone_px: int = 4
    dwell_enabled: bool = False
    dwell_ms: int = 1200
    dwell_radius_px: int = 30
    scroll_speed: int = 5

    def validate(self) -> None:
        if not 0.5 <= self.speed <= 3.0:
            raise ValueError("La velocidad debe estar entre 0,5 y 3")
        if not 0 <= self.smoothing <= 10 or not 1 <= self.scroll_speed <= 10:
            raise ValueError("Suavizado o velocidad de desplazamiento fuera de rango")
        if self.dead_zone_px < 0 or self.dwell_ms < 200 or self.dwell_radius_px < 1:
            raise ValueError("Zona muerta o permanencia fuera de rango")


def apply_speed(pointer: tuple[float, float], speed: float) -> tuple[float, float]:
    """Amplía el desplazamiento respecto del centro: más velocidad, menos giro necesario."""
    x, y = pointer
    return (
        min(max(0.5 + (x - 0.5) * speed, 0.0), 1.0),
        min(max(0.5 + (y - 0.5) * speed, 0.0), 1.0),
    )


class OneEuroFilter:
    """Filtro adaptativo: suaviza mucho en reposo y poco en movimientos rápidos."""

    def __init__(self, min_cutoff: float, beta: float = 1.0, d_cutoff: float = 1.0) -> None:
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self._value: float | None = None
        self._derivative = 0.0
        self._last_ms: int | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        self._value, self._last_ms, self._derivative = None, None, 0.0

    def __call__(self, value: float, timestamp_ms: int) -> float:
        if self._value is None or self._last_ms is None or timestamp_ms <= self._last_ms:
            self._value, self._last_ms = value, timestamp_ms
            return value
        dt = (timestamp_ms - self._last_ms) / 1000.0
        self._last_ms = timestamp_ms
        derivative = (value - self._value) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        self._derivative = a_d * derivative + (1 - a_d) * self._derivative
        cutoff = self.min_cutoff + self.beta * abs(self._derivative)
        a = self._alpha(cutoff, dt)
        self._value = a * value + (1 - a) * self._value
        return self._value


class ControlMode(StrEnum):
    DISABLED = "DESACTIVADO"
    NO_FACE = "SIN_ROSTRO"
    NORMAL = "NORMAL"
    DRAGGING = "ARRASTRANDO"
    SCROLLING = "DESPLAZAMIENTO"
    PAUSED = "PAUSA"


@dataclass(frozen=True, slots=True)
class ControlStatus:
    mode: ControlMode
    position: tuple[int, int] | None = None
    dwell_progress: float = 0.0
    executed: tuple[str, ...] = ()


SCROLL_DEAD_ZONE = 0.12


class PointerController:
    def __init__(self, backend: MouseBackend, screen: ScreenArea, settings: PointerSettings):
        self.backend, self.screen = backend, screen
        self.settings = settings
        self.paused = False
        self.mode = ControlMode.NORMAL
        self.position: tuple[int, int] | None = None
        self._filters = (OneEuroFilter(1.0), OneEuroFilter(1.0))
        self._drag_origin: tuple[int, int] | None = None
        self._dwell_anchor: tuple[int, int] | None = None
        self._dwell_since_ms: int | None = None
        self._dwell_fired = False
        self._scroll_rest = [0.0, 0.0]
        self.configure(settings)

    def configure(self, settings: PointerSettings) -> None:
        self.settings = settings
        cutoff = 3.0 / settings.smoothing if settings.smoothing else 0.0
        for item in self._filters:
            item.min_cutoff = cutoff
            item.reset()

    def _smooth(self, pointer: tuple[float, float], timestamp_ms: int) -> tuple[float, float]:
        if not self.settings.smoothing:
            return pointer
        return (
            self._filters[0](pointer[0], timestamp_ms),
            self._filters[1](pointer[1], timestamp_ms),
        )

    def _reset_motion(self) -> None:
        for item in self._filters:
            item.reset()
        self._dwell_anchor, self._dwell_since_ms, self._dwell_fired = None, None, False
        self._scroll_rest = [0.0, 0.0]

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self.release_all(cancel=True)
            self._reset_motion()

    def release_all(self, cancel: bool) -> list[str]:
        """Suelta un arrastre en curso; ``cancel`` lo anula devolviendo el elemento."""
        executed: list[str] = []
        if self.mode is ControlMode.DRAGGING:
            if cancel and self._drag_origin is not None:
                self.backend.escape()
                self.backend.move(*self._drag_origin)
                executed.append("arrastre cancelado")
            else:
                executed.append("soltar")
            self.backend.release(Button.LEFT)
            self._drag_origin = None
        self.mode = ControlMode.NORMAL
        return executed

    def update(
        self,
        pointer: tuple[float, float] | None,
        events: Iterable[GestureEvent],
        timestamp_ms: int,
    ) -> ControlStatus:
        executed: list[str] = []
        actions = [event.action for event in events]
        if Action.PAUSE in actions:
            self.toggle_pause()
            executed.append("pausa" if self.paused else "reanudar")
        if not self.settings.enabled:
            executed += self.release_all(cancel=True)
            self._reset_motion()
            return ControlStatus(ControlMode.DISABLED, self.position, executed=tuple(executed))
        if self.paused:
            return ControlStatus(ControlMode.PAUSED, self.position, executed=tuple(executed))
        if pointer is None:
            # Sin rostro: el cursor se detiene y un arrastre se cancela (HU-04, HU-16).
            executed += self.release_all(cancel=True)
            self._reset_motion()
            return ControlStatus(ControlMode.NO_FACE, self.position, executed=tuple(executed))

        if self.mode is ControlMode.SCROLLING:
            if Action.SCROLL in actions or Action.LEFT_CLICK in actions:
                self.mode = ControlMode.NORMAL
                self._reset_motion()
                executed.append("fin del desplazamiento")
                actions = []
            else:
                self._scroll(pointer)
                return ControlStatus(self.mode, self.position, executed=tuple(executed))

        target = self.screen.to_pixels(*self._smooth(apply_speed(pointer, self.settings.speed),
                                                     timestamp_ms))
        if self.position is None or math.dist(target, self.position) >= self.settings.dead_zone_px:
            self.position = target
            self.backend.move(*target)
        assert self.position is not None

        if self.mode is ControlMode.DRAGGING:
            if Action.DRAG in actions or Action.LEFT_CLICK in actions:
                executed += self.release_all(cancel=False)
            return ControlStatus(self.mode, self.position, executed=tuple(executed))

        for action in actions:
            if action is Action.LEFT_CLICK:
                self.backend.click(Button.LEFT)
                executed.append("clic izquierdo")
            elif action is Action.RIGHT_CLICK:
                self.backend.click(Button.RIGHT)
                executed.append("clic derecho")
            elif action is Action.DOUBLE_CLICK:
                self.backend.click(Button.LEFT, 2)
                executed.append("doble clic")
            elif action is Action.DRAG:
                self._drag_origin = self.position
                self.backend.press(Button.LEFT)
                self.mode = ControlMode.DRAGGING
                executed.append("arrastre iniciado")
                return ControlStatus(self.mode, self.position, executed=tuple(executed))
            elif action is Action.SCROLL:
                self.mode = ControlMode.SCROLLING
                self._scroll_rest = [0.0, 0.0]
                executed.append("modo desplazamiento")
                return ControlStatus(self.mode, self.position, executed=tuple(executed))
        if any(a in actions for a in (Action.LEFT_CLICK, Action.DOUBLE_CLICK)):
            # Un clic por gesto no debe sumarse a uno por permanencia en el mismo punto.
            self._dwell_fired, self._dwell_anchor = True, self.position
        progress = self._dwell(timestamp_ms, executed)
        return ControlStatus(self.mode, self.position, progress, tuple(executed))

    def _dwell(self, timestamp_ms: int, executed: list[str]) -> float:
        if not self.settings.dwell_enabled or self.position is None:
            return 0.0
        if (
            self._dwell_anchor is None
            or math.dist(self.position, self._dwell_anchor) > self.settings.dwell_radius_px
        ):
            self._dwell_anchor, self._dwell_since_ms = self.position, timestamp_ms
            self._dwell_fired = False
            return 0.0
        if self._dwell_since_ms is None:
            self._dwell_since_ms = timestamp_ms
        if self._dwell_fired:
            return 0.0
        progress = (timestamp_ms - self._dwell_since_ms) / self.settings.dwell_ms
        if progress >= 1.0:
            self.backend.click(Button.LEFT)
            self._dwell_fired = True
            executed.append("clic por permanencia")
            return 1.0
        return progress

    def _scroll(self, pointer: tuple[float, float]) -> None:
        """La cabeza fuera del centro desplaza; más lejos, más rápido."""
        steps = []
        for axis, value in enumerate(pointer):
            offset = value - 0.5
            magnitude = max(abs(offset) - SCROLL_DEAD_ZONE, 0.0) / (0.5 - SCROLL_DEAD_ZONE)
            rate = math.copysign(magnitude, offset) * self.settings.scroll_speed * 0.15
            self._scroll_rest[axis] += rate
            whole = int(self._scroll_rest[axis])
            self._scroll_rest[axis] -= whole
            steps.append(whole)
        dx, dy = steps
        if dx or dy:
            # Cabeza arriba (y < 0,5) sube el contenido: rueda positiva.
            self.backend.scroll(dx, -dy)


class PynputBackend:
    """Backend real. En Windows pynput usa SendInput."""

    def __init__(self) -> None:
        from pynput import keyboard, mouse

        self._mouse = mouse.Controller()
        self._keyboard = keyboard.Controller()
        self._buttons = {Button.LEFT: mouse.Button.left, Button.RIGHT: mouse.Button.right}
        self._esc = keyboard.Key.esc

    def move(self, x: int, y: int) -> None:
        self._mouse.position = (x, y)

    def press(self, button: Button) -> None:
        self._mouse.press(self._buttons[button])

    def release(self, button: Button) -> None:
        self._mouse.release(self._buttons[button])

    def click(self, button: Button, count: int = 1) -> None:
        self._mouse.click(self._buttons[button], count)

    def scroll(self, dx: int, dy: int) -> None:
        self._mouse.scroll(dx, dy)

    def escape(self) -> None:
        self._keyboard.press(self._esc)
        self._keyboard.release(self._esc)
