"""Retroalimentación e indicador de estado (P3-44) y recordatorios de descanso (P3-45).

Lógica pura: qué estado mostrar, cuándo sonar y cuándo toca descansar. Las ventanas que lo
muestran están en ``ui_widgets.py`` y el sonido real en ``SystemSound``.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Protocol

from gestia.control import ControlMode
from gestia.domain import TrackingState

MIN_BREAK_MINUTES, MAX_BREAK_MINUTES = 1, 180


class StatusKind(StrEnum):
    STOPPED = "stopped"
    ACTIVE = "active"
    PAUSED = "paused"
    NO_FACE = "no_face"
    CURSOR_OFF = "cursor_off"


STATUS_TEXT = {
    StatusKind.STOPPED: "Detenido",
    StatusKind.ACTIVE: "Activo",
    StatusKind.PAUSED: "En pausa",
    StatusKind.NO_FACE: "Sin rostro",
    StatusKind.CURSOR_OFF: "Activo, cursor desactivado",
}
STATUS_COLOR = {
    StatusKind.STOPPED: "#64748b",
    StatusKind.ACTIVE: "#16a34a",
    StatusKind.PAUSED: "#ca8a04",
    StatusKind.NO_FACE: "#dc2626",
    StatusKind.CURSOR_OFF: "#2563eb",
}


def status_for(
    running: bool, tracking: TrackingState, mode: ControlMode | None, paused: bool
) -> StatusKind:
    """Estado que ve la persona. La pausa manda: aunque no haya rostro, sigue en pausa."""
    if not running or tracking in (TrackingState.STOPPED, TrackingState.ERROR):
        return StatusKind.STOPPED
    if paused or mode is ControlMode.PAUSED:
        return StatusKind.PAUSED
    if tracking is not TrackingState.TRACKING or mode is ControlMode.NO_FACE:
        return StatusKind.NO_FACE
    if mode is ControlMode.DISABLED:
        return StatusKind.CURSOR_OFF
    return StatusKind.ACTIVE


class Sound(StrEnum):
    GESTURE = "gesture"
    PAUSE = "pause"
    REMINDER = "reminder"


class SoundBackend(Protocol):
    def play(self, sound: Sound) -> None: ...


class SystemSound:
    """Sonidos del sistema: en Windows uno distinto por tipo; en otros, el pitido de Qt."""

    def play(self, sound: Sound) -> None:
        if sys.platform == "win32":
            import winsound

            kind = {
                Sound.GESTURE: winsound.MB_OK,
                Sound.PAUSE: winsound.MB_ICONEXCLAMATION,
                Sound.REMINDER: winsound.MB_ICONASTERISK,
            }[sound]
            winsound.MessageBeep(kind)
            return
        from PySide6.QtWidgets import QApplication

        QApplication.beep()


@dataclass(slots=True)
class FeedbackSettings:
    sound: bool = True
    indicator: bool = True
    breaks: bool = True
    break_minutes: int = 30

    def validate(self) -> None:
        flags = (self.sound, self.indicator, self.breaks)
        if not all(isinstance(flag, bool) for flag in flags):
            raise ValueError("Los ajustes de avisos deben ser verdadero o falso")
        minutes = self.break_minutes
        if (
            not isinstance(minutes, int)
            or isinstance(minutes, bool)
            or not MIN_BREAK_MINUTES <= minutes <= MAX_BREAK_MINUTES
        ):
            raise ValueError(
                f"El intervalo de descanso debe estar entre {MIN_BREAK_MINUTES} y "
                f"{MAX_BREAK_MINUTES} minutos"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> FeedbackSettings:
        if not isinstance(raw, dict):
            raise ValueError("Ajustes de avisos no válidos")
        settings = cls(**raw)
        settings.validate()
        return settings


class Feedback:
    """Decide si suena: el sonido es opcional; la señal visual no depende de él."""

    def __init__(self, backend: SoundBackend, settings: FeedbackSettings) -> None:
        self.backend, self.settings = backend, settings

    def play(self, sound: Sound) -> bool:
        if not self.settings.sound:
            return False
        self.backend.play(sound)
        return True


class BreakTimer:
    """Cuenta el tiempo de uso activo; la pausa no cuenta, y una pausa larga es un descanso.

    ``tick`` devuelve ``True`` una sola vez cuando se cumple el intervalo; luego vuelve a
    contar desde cero.
    """

    def __init__(self, settings: FeedbackSettings, rest_reset_s: float = 120.0) -> None:
        self.settings = settings
        self.rest_reset_s = rest_reset_s
        self.active_s = 0.0
        self._rest_s = 0.0
        self._last: float | None = None

    @property
    def interval_s(self) -> float:
        return self.settings.break_minutes * 60.0

    def reset(self) -> None:
        self.active_s = self._rest_s = 0.0

    def configure(self, settings: FeedbackSettings) -> None:
        self.settings = settings

    def tick(self, now_s: float, active: bool) -> bool:
        elapsed = 0.0 if self._last is None else max(now_s - self._last, 0.0)
        self._last = now_s
        if not active:
            self._rest_s += elapsed
            if self._rest_s >= self.rest_reset_s:
                self.reset()  # quien descansa por su cuenta no necesita el aviso
            return False
        self._rest_s = 0.0
        if not self.settings.breaks:
            self.active_s = 0.0
            return False
        self.active_s += elapsed
        # Tolerancia de 1 ms: sumar segundos con decimales no debe retrasar el aviso un tick.
        if self.active_s >= self.interval_s - 1e-3:
            self.active_s = 0.0
            return True
        return False


def break_message(minutes: int) -> str:
    return (
        f"Lleva {minutes} min usando GestIA. Relaje el cuello y los hombros, y mire algo "
        "lejano durante 20 segundos."
    )
