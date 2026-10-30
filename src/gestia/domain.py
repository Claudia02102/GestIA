from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrackingState(StrEnum):
    STOPPED = "DETENIDO"
    SEARCHING = "BUSCANDO"
    TRACKING = "SIGUIENDO"
    LOST = "PERDIDO"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class FaceResult:
    timestamp_ms: int
    landmarks: tuple[tuple[float, float, float], ...]
    inference_ms: float

    @property
    def detected(self) -> bool:
        return bool(self.landmarks)


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    capture_fps: float
    result_fps: float
    inference_ms: float
    dropped_frames: int
    stale_results: int


@dataclass(frozen=True, slots=True)
class DisplayPacket:
    frame_bgr: object
    result: FaceResult
    state: TrackingState
    performance: PerformanceSnapshot
