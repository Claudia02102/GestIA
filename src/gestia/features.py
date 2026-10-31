"""Medidas geométricas derivadas de los landmarks de Face Landmarker.

Todas las medidas son razones adimensionales: no dependen de la distancia a la cámara y no
identifican a la persona. Solo se conservan los valores escalares, nunca los landmarks.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

Point = tuple[float, float, float]

# Índices de la malla de 478 puntos. «Izquierdo/derecho» se refieren a la persona.
NOSE_TIP = 1
FOREHEAD = 10
CHIN = 152
CHEEK_RIGHT = 234
CHEEK_LEFT = 454
EYE_RIGHT = (33, 160, 158, 133, 153, 144)
EYE_LEFT = (362, 385, 387, 263, 373, 380)
BROW_RIGHT, EYE_TOP_RIGHT = 105, 159
BROW_LEFT, EYE_TOP_LEFT = 334, 386
EYE_OUTER_RIGHT, EYE_OUTER_LEFT = 33, 263
LIP_UPPER_INNER, LIP_LOWER_INNER = 13, 14
MOUTH_INNER_RIGHT, MOUTH_INNER_LEFT = 78, 308
MOUTH_CORNER_RIGHT, MOUTH_CORNER_LEFT = 61, 291
REQUIRED_POINTS = 468


@dataclass(frozen=True, slots=True)
class FaceFeatures:
    """Pose aproximada de la cabeza y medidas de los gestos en un instante."""

    yaw: float
    pitch: float
    eye_left: float
    eye_right: float
    mouth_open: float
    brow_raise: float
    smile: float

    def metric(self, name: str) -> float:
        return float(getattr(self, name))


METRIC_NAMES = ("yaw", "pitch", "eye_left", "eye_right", "mouth_open", "brow_raise", "smile")


def extract_features(landmarks: Sequence[Point], aspect: float) -> FaceFeatures | None:
    """Calcula las medidas; ``aspect`` es ancho/alto del fotograma para corregir x."""
    if len(landmarks) < REQUIRED_POINTS or aspect <= 0:
        return None

    def point(index: int) -> tuple[float, float]:
        x, y, _ = landmarks[index]
        return x * aspect, y

    def dist(a: int, b: int) -> float:
        (ax, ay), (bx, by) = point(a), point(b)
        return math.hypot(ax - bx, ay - by)

    def ratio(numerator: float, denominator: float) -> float:
        return numerator / denominator if denominator > 1e-9 else 0.0

    def eye_aspect(eye: tuple[int, ...]) -> float:
        p1, p2, p3, p4, p5, p6 = eye
        return ratio(dist(p2, p6) + dist(p3, p5), 2.0 * dist(p1, p4))

    nose_x, nose_y = point(NOSE_TIP)
    right_x, _ = point(CHEEK_RIGHT)
    left_x, _ = point(CHEEK_LEFT)
    _, top_y = point(FOREHEAD)
    _, chin_y = point(CHIN)
    interocular = dist(EYE_OUTER_RIGHT, EYE_OUTER_LEFT)
    brow = (dist(BROW_RIGHT, EYE_TOP_RIGHT) + dist(BROW_LEFT, EYE_TOP_LEFT)) / 2.0
    return FaceFeatures(
        yaw=ratio(nose_x - right_x, left_x - right_x),
        pitch=ratio(nose_y - top_y, chin_y - top_y),
        eye_left=eye_aspect(EYE_LEFT),
        eye_right=eye_aspect(EYE_RIGHT),
        mouth_open=ratio(
            dist(LIP_UPPER_INNER, LIP_LOWER_INNER), dist(MOUTH_INNER_RIGHT, MOUTH_INNER_LEFT)
        ),
        brow_raise=ratio(brow, interocular),
        smile=ratio(
            dist(MOUTH_CORNER_RIGHT, MOUTH_CORNER_LEFT), dist(CHEEK_RIGHT, CHEEK_LEFT)
        ),
    )
