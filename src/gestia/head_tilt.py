"""Gesto de inclinar la cabeza para abrir y cerrar las acciones rápidas (P3-64).

Se inclina la cabeza hacia un hombro (a cualquier lado) y se mantiene un momento: el menú se
abre; el mismo gesto lo cierra. No interfiere con el resto:

- usa la inclinación lateral (roll), que no mueve el cursor (el cursor sigue al giro y a la
  inclinación adelante/atrás);
- mientras la cabeza se inclina, el cursor se fija y los demás gestos esperan: al inclinarla un
  ojo parece más cerrado y daría un guiño (clic) falso;
- dispara una sola vez: para repetir hay que volver a la posición normal;
- la posición «normal» se aprende sola y se adapta despacio a la postura de cada persona.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

DEFAULT_ANGLE_DEG = 18
MIN_ANGLE_DEG, MAX_ANGLE_DEG = 10, 35
HOLD_MS = 500
# Por debajo de esta fracción del ángulo la cabeza cuenta como «de vuelta» y se rearma.
RELEASE_RATIO = 0.5
# Desde esta fracción del ángulo el cursor se fija y los demás gestos esperan.
FORMING_RATIO = 0.5
# Qué tan rápido la posición normal sigue a la postura (por fotograma, en reposo).
BASELINE_RATE = 0.02


@dataclass(slots=True)
class TiltSettings:
    enabled: bool = True
    angle_deg: int = DEFAULT_ANGLE_DEG

    def validate(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("El ajuste de inclinar la cabeza debe ser verdadero o falso")
        angle = self.angle_deg
        if isinstance(angle, bool) or not isinstance(angle, int):
            raise ValueError("El ángulo debe ser un número entero")
        if not MIN_ANGLE_DEG <= angle <= MAX_ANGLE_DEG:
            raise ValueError(f"El ángulo debe estar entre {MIN_ANGLE_DEG} y {MAX_ANGLE_DEG} grados")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TiltSettings:
        if not isinstance(raw, dict):
            raise ValueError("Ajustes de inclinar la cabeza no válidos")
        settings = cls(**raw)
        settings.validate()
        return settings


class HeadTiltDetector:
    def __init__(self, settings: TiltSettings | None = None) -> None:
        self.settings = settings or TiltSettings()
        self.reset()

    def reset(self) -> None:
        self._neutral: float | None = None
        self._since_ms: int | None = None
        self._armed = True
        self._delta = 0.0

    @property
    def threshold(self) -> float:
        return math.radians(self.settings.angle_deg)

    @property
    def forming(self) -> bool:
        """La cabeza se está inclinando (o aún no volvió): el cursor y los gestos esperan."""
        return self.settings.enabled and (
            self._delta >= self.threshold * FORMING_RATIO or not self._armed
        )

    def update(self, roll: float, timestamp_ms: int) -> bool:
        """Verdadero en el fotograma en que se completa el gesto."""
        if not self.settings.enabled:
            self.reset()
            return False
        if self._neutral is None:
            self._neutral = roll
        self._delta = abs(roll - self._neutral)
        if self._delta < self.threshold * RELEASE_RATIO:
            self._armed = True
            self._since_ms = None
            # En reposo, la posición normal se adapta a la postura de la persona.
            self._neutral += (roll - self._neutral) * BASELINE_RATE
            return False
        if self._delta < self.threshold or not self._armed:
            self._since_ms = None
            return False
        if self._since_ms is None:
            self._since_ms = timestamp_ms
        if timestamp_ms - self._since_ms >= HOLD_MS:
            self._armed = False
            self._since_ms = None
            return True
        return False
