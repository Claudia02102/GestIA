"""Calibración guiada (HU-06), recentrado rápido (HU-10) y mapeo cabeza → puntero.

Toda la lógica es pura (sin Qt ni cámara) y avanza solo con medidas faciales, de modo que el
asistente se completa sin teclado ni ratón.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from gestia.config import CalibrationConfig
from gestia.features import METRIC_NAMES, FaceFeatures
from gestia.gestures import GESTURES, GestureId, SignalRange

# Desplazamiento mínimo de cada señal respecto del reposo para aceptar el gesto calibrado.
MIN_GESTURE_DELTA = {
    GestureId.MOUTH_OPEN: 0.08,
    GestureId.BLINK: 0.05,
    GestureId.WINK_LEFT: 0.05,
    GestureId.WINK_RIGHT: 0.05,
    GestureId.BROW_RAISE: 0.025,
    GestureId.SMILE: 0.025,
    GestureId.PUCKER: 0.025,
}
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")
CORNER_ZONE = 0.05


@dataclass(frozen=True, slots=True)
class AxisRange:
    """Reposo y extremos cómodos de un eje; ``negative`` lleva el puntero a 0."""

    neutral: float
    negative: float
    positive: float

    def to_unit(self, value: float, reach: float) -> float:
        towards_negative = (value - self.neutral) * (self.negative - self.neutral) > 0
        span = (self.negative if towards_negative else self.positive) - self.neutral
        offset = 0.0 if abs(span) < 1e-9 else min((value - self.neutral) / span / reach, 1.0)
        return 0.5 - 0.5 * offset if towards_negative else 0.5 + 0.5 * offset

    def shifted(self, neutral: float) -> AxisRange:
        delta = neutral - self.neutral
        return AxisRange(neutral, self.negative + delta, self.positive + delta)


@dataclass(frozen=True, slots=True)
class HeadCalibration:
    yaw: AxisRange
    pitch: AxisRange

    def to_pointer(self, features: FaceFeatures, reach: float) -> tuple[float, float]:
        """Posición normalizada [0,1]² del puntero; el reposo corresponde al centro."""
        return self.yaw.to_unit(features.yaw, reach), self.pitch.to_unit(features.pitch, reach)

    def recentered(self, yaw: float, pitch: float) -> HeadCalibration:
        return HeadCalibration(self.yaw.shifted(yaw), self.pitch.shifted(pitch))


@dataclass(frozen=True, slots=True)
class Calibration:
    head: HeadCalibration
    gestures: dict[GestureId, SignalRange] = field(default_factory=dict)
    calibrated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        def axis(item: AxisRange) -> dict[str, float]:
            return {"neutral": item.neutral, "negative": item.negative, "positive": item.positive}

        return {
            "calibrated_at": self.calibrated_at,
            "head": {"yaw": axis(self.head.yaw), "pitch": axis(self.head.pitch)},
            "gestures": {
                str(gesture): {"neutral": item.neutral, "peak": item.peak}
                for gesture, item in self.gestures.items()
            },
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Calibration:
        head = raw["head"]
        return cls(
            head=HeadCalibration(
                AxisRange(**{k: float(v) for k, v in head["yaw"].items()}),
                AxisRange(**{k: float(v) for k, v in head["pitch"].items()}),
            ),
            gestures={
                GestureId(gesture): SignalRange(float(item["neutral"]), float(item["peak"]))
                for gesture, item in raw.get("gestures", {}).items()
                if gesture in GestureId.__members__.values()
            },
            calibrated_at=str(raw.get("calibrated_at", "")),
        )


class _Hold:
    """Detecta una condición sostenida durante ``hold_ms`` con estabilidad opcional."""

    def __init__(self, hold_ms: int, tolerance: float | None) -> None:
        self.hold_ms, self.tolerance = hold_ms, tolerance
        self.samples: list[tuple[int, tuple[float, ...], FaceFeatures]] = []

    def clear(self) -> None:
        self.samples.clear()

    def progress(self, timestamp_ms: int) -> float:
        if not self.samples:
            return 0.0
        return min((timestamp_ms - self.samples[0][0]) / self.hold_ms, 1.0) if self.hold_ms else 1.0

    def add(
        self, timestamp_ms: int, values: tuple[float, ...], features: FaceFeatures, ok: bool
    ) -> list[FaceFeatures] | None:
        if not ok:
            self.clear()
            return None
        self.samples.append((timestamp_ms, values, features))
        if self.tolerance is not None:
            while len(self.samples) > 1 and not self._stable():
                self.samples.pop(0)
        if timestamp_ms - self.samples[0][0] >= self.hold_ms:
            return [item[2] for item in self.samples]
        return None

    def _stable(self) -> bool:
        assert self.tolerance is not None
        for dim in range(len(self.samples[0][1])):
            column = [item[1][dim] for item in self.samples]
            if max(column) - min(column) > self.tolerance:
                return False
        return True


def _median(samples: Iterable[FaceFeatures], metric: str) -> float:
    return float(statistics.median(item.metric(metric) for item in samples))


class StepKind(StrEnum):
    NEUTRAL = "neutral"
    HEAD_LEFT = "head_left"
    HEAD_RIGHT = "head_right"
    HEAD_UP = "head_up"
    HEAD_DOWN = "head_down"
    GESTURE = "gesture"
    CORNERS = "corners"
    DONE = "done"


HEAD_STEPS = {
    StepKind.HEAD_LEFT: ("yaw", "Gire la cabeza hacia la izquierda, cómodo, y manténgala"),
    StepKind.HEAD_RIGHT: ("yaw", "Gire la cabeza hacia la derecha, cómodo, y manténgala"),
    StepKind.HEAD_UP: ("pitch", "Incline la cabeza hacia arriba, cómodo, y manténgala"),
    StepKind.HEAD_DOWN: ("pitch", "Incline la cabeza hacia abajo, cómodo, y manténgala"),
}
OPPOSITE_STEP = {StepKind.HEAD_RIGHT: StepKind.HEAD_LEFT, StepKind.HEAD_DOWN: StepKind.HEAD_UP}


@dataclass(frozen=True, slots=True)
class Step:
    kind: StepKind
    gesture: GestureId | None = None

    @property
    def instruction(self) -> str:
        if self.kind is StepKind.NEUTRAL:
            return "Mire al centro de la pantalla y mantenga la cabeza quieta"
        if self.kind in HEAD_STEPS:
            return HEAD_STEPS[self.kind][1]
        if self.kind is StepKind.GESTURE and self.gesture is not None:
            return GESTURES[self.gesture].instruction
        if self.kind is StepKind.CORNERS:
            return "Lleve el puntero a las cuatro esquinas moviendo la cabeza"
        return "Calibración completada"


@dataclass(frozen=True, slots=True)
class SessionUpdate:
    step: Step
    progress: float
    message: str = ""
    step_completed: bool = False
    step_failed: bool = False
    pointer: tuple[float, float] | None = None
    corners_reached: frozenset[str] = frozenset()


class CalibrationSession:
    """Secuencia: reposo, rango de cabeza, gestos activos y verificación de esquinas."""

    def __init__(self, gestures: Iterable[GestureId], config: CalibrationConfig) -> None:
        self.config = config
        self.steps = [Step(StepKind.NEUTRAL)]
        self.steps += [Step(kind) for kind in HEAD_STEPS]
        self.steps += [Step(StepKind.GESTURE, gesture) for gesture in gestures]
        self.steps += [Step(StepKind.CORNERS), Step(StepKind.DONE)]
        self.index = 0
        self.attempts = 1
        self.neutral: dict[str, float] = {}
        self.head_values: dict[StepKind, float] = {}
        self.gesture_ranges: dict[GestureId, SignalRange] = {}
        self.skipped: list[GestureId] = []
        self.corners: set[str] = set()
        self.head: HeadCalibration | None = None
        self._repeating_range = False
        self._step_started_ms: int | None = None
        self._hold = _Hold(0, None)
        self._enter_step()

    @property
    def step(self) -> Step:
        return self.steps[self.index]

    @property
    def finished(self) -> bool:
        return self.step.kind is StepKind.DONE

    @property
    def result(self) -> Calibration | None:
        if not self.finished or self.head is None:
            return None
        return Calibration(self.head, dict(self.gesture_ranges), datetime.now(UTC).isoformat())

    def _enter_step(self) -> None:
        self._step_started_ms = None
        kind = self.step.kind
        c = self.config
        if kind is StepKind.NEUTRAL:
            self._hold = _Hold(c.neutral_hold_ms, c.stable_tolerance)
        elif kind in HEAD_STEPS:
            self._hold = _Hold(c.pose_hold_ms, c.stable_tolerance)
        else:
            self._hold = _Hold(c.gesture_hold_ms, None)

    def _advance(self) -> None:
        if self._repeating_range and self.step.kind is StepKind.HEAD_DOWN:
            self._repeating_range = False
            self.index = self.steps.index(Step(StepKind.CORNERS))
        else:
            self.index += 1
        self.attempts = 1
        if self.step.kind is StepKind.CORNERS:
            self.head = HeadCalibration(
                AxisRange(
                    self.neutral["yaw"],
                    self.head_values[StepKind.HEAD_LEFT],
                    self.head_values[StepKind.HEAD_RIGHT],
                ),
                AxisRange(
                    self.neutral["pitch"],
                    self.head_values[StepKind.HEAD_UP],
                    self.head_values[StepKind.HEAD_DOWN],
                ),
            )
            self.corners.clear()
        self._enter_step()

    def _fail(self, step: Step, message: str, timestamp_ms: int) -> SessionUpdate:
        if (
            step.kind is StepKind.GESTURE
            and step.gesture is not None
            and self.attempts >= self.config.max_gesture_attempts
        ):
            self.skipped.append(step.gesture)
            self._advance()
            return SessionUpdate(
                self.step, 0.0,
                f"Se omitió «{GESTURES[step.gesture].name}»; quedará desactivado.",
                step_failed=True,
            )
        if step.kind is StepKind.CORNERS:
            # El rango registrado no permite cubrir la pantalla: repetir el rango de cabeza.
            self.index = self.steps.index(Step(StepKind.HEAD_LEFT))
            self.attempts = 1
            self._repeating_range = True
            self._enter_step()
            return SessionUpdate(self.step, 0.0, message, step_failed=True)
        self.attempts += 1
        self._enter_step()
        self._step_started_ms = timestamp_ms
        return SessionUpdate(self.step, 0.0, f"{message} Repita el paso.", step_failed=True)

    def feed(self, features: FaceFeatures | None, timestamp_ms: int) -> SessionUpdate:
        step, c = self.step, self.config
        if step.kind is StepKind.DONE:
            return SessionUpdate(step, 1.0)
        if self._step_started_ms is None:
            self._step_started_ms = timestamp_ms
        elapsed = timestamp_ms - self._step_started_ms
        if features is None:
            self._hold.clear()
            return SessionUpdate(step, 0.0, "No se ve el rostro: vuelva al encuadre.")
        if elapsed < c.settle_ms:
            return SessionUpdate(step, 0.0)
        if step.kind is StepKind.CORNERS:
            return self._feed_corners(features, timestamp_ms, elapsed)
        timeout = elapsed >= c.step_timeout_ms

        if step.kind is StepKind.NEUTRAL:
            done = self._hold.add(timestamp_ms, (features.yaw, features.pitch), features, True)
            if done:
                self.neutral = {name: _median(done, name) for name in METRIC_NAMES}
                self._advance()
                return SessionUpdate(self.step, 0.0, "Reposo registrado.", step_completed=True)
            if timeout:
                return self._fail(step, "La cabeza no se mantuvo quieta.", timestamp_ms)
            return SessionUpdate(step, self._hold.progress(timestamp_ms))

        if step.kind in HEAD_STEPS:
            axis = HEAD_STEPS[step.kind][0]
            value = features.metric(axis)
            displaced = abs(value - self.neutral[axis]) >= c.min_head_delta
            done = self._hold.add(timestamp_ms, (value,), features, displaced)
            if done:
                measured = _median(done, axis)
                opposite = OPPOSITE_STEP.get(step.kind)
                if opposite is not None:
                    reference = self.head_values[opposite] - self.neutral[axis]
                    if (measured - self.neutral[axis]) * reference > 0:
                        return self._fail(
                            step, "El movimiento fue hacia el mismo lado que el anterior.",
                            timestamp_ms,
                        )
                self.head_values[step.kind] = measured
                self._advance()
                return SessionUpdate(self.step, 0.0, "Movimiento registrado.",
                                     step_completed=True)
            if timeout:
                return self._fail(step, "No se detectó un movimiento suficiente.", timestamp_ms)
            return SessionUpdate(step, self._hold.progress(timestamp_ms))

        assert step.gesture is not None
        spec = GESTURES[step.gesture]
        neutral_value = spec.signal(_neutral_features(self.neutral))
        value = spec.signal(features)
        delta = value - neutral_value
        if spec.direction:
            delta *= spec.direction
        else:
            delta = abs(delta)
        displaced = delta >= MIN_GESTURE_DELTA[step.gesture]
        done = self._hold.add(timestamp_ms, (value,), features, displaced)
        if done:
            peak = float(statistics.median(spec.signal(item) for item in done))
            self.gesture_ranges[step.gesture] = SignalRange(neutral_value, peak)
            self._advance()
            return SessionUpdate(self.step, 0.0, "Gesto registrado.", step_completed=True)
        if timeout:
            return self._fail(step, "No se detectó el gesto.", timestamp_ms)
        return SessionUpdate(step, self._hold.progress(timestamp_ms))

    def _feed_corners(
        self, features: FaceFeatures, timestamp_ms: int, elapsed: int
    ) -> SessionUpdate:
        assert self.head is not None
        x, y = self.head.to_pointer(features, self.config.reach)
        for name, reached in zip(
            CORNERS,
            (
                x <= CORNER_ZONE and y <= CORNER_ZONE,
                x >= 1 - CORNER_ZONE and y <= CORNER_ZONE,
                x <= CORNER_ZONE and y >= 1 - CORNER_ZONE,
                x >= 1 - CORNER_ZONE and y >= 1 - CORNER_ZONE,
            ),
            strict=True,
        ):
            if reached:
                self.corners.add(name)
        if len(self.corners) == len(CORNERS):
            self._advance()
            return SessionUpdate(
                self.step, 1.0, "Las cuatro esquinas son alcanzables.", step_completed=True,
                pointer=(x, y), corners_reached=frozenset(CORNERS),
            )
        if elapsed >= self.config.verify_timeout_ms:
            return self._fail(
                self.step, "No se alcanzaron las cuatro esquinas: repita el rango de movimiento.",
                timestamp_ms,
            )
        return SessionUpdate(
            self.step, len(self.corners) / len(CORNERS), pointer=(x, y),
            corners_reached=frozenset(self.corners),
        )


def _neutral_features(neutral: Mapping[str, float]) -> FaceFeatures:
    return FaceFeatures(**neutral)


class RecenterStatus(StrEnum):
    COLLECTING = "collecting"
    DONE = "done"
    FAILED = "failed"


class Recenterer:
    """HU-10: toma la postura actual como nuevo centro sin tocar el resto del perfil."""

    def __init__(self, config: CalibrationConfig) -> None:
        self.config = config
        self.started_ms: int | None = None
        self._hold = _Hold(config.recenter_hold_ms, config.stable_tolerance)
        self.center: tuple[float, float] | None = None

    def feed(self, features: FaceFeatures | None, timestamp_ms: int) -> RecenterStatus:
        if self.started_ms is None:
            self.started_ms = timestamp_ms
        if timestamp_ms - self.started_ms >= self.config.recenter_timeout_ms:
            return RecenterStatus.FAILED
        if features is None:
            self._hold.clear()
            return RecenterStatus.COLLECTING
        done = self._hold.add(timestamp_ms, (features.yaw, features.pitch), features, True)
        if done:
            self.center = (_median(done, "yaw"), _median(done, "pitch"))
            return RecenterStatus.DONE
        return RecenterStatus.COLLECTING

    def apply(self, calibration: Calibration) -> Calibration:
        assert self.center is not None
        return replace(calibration, head=calibration.head.recentered(*self.center))
