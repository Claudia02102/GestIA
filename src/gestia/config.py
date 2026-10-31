from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CameraConfig:
    index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    candidate_indices: list[int] = field(default_factory=lambda: [0, 1, 2, 3])


@dataclass(slots=True)
class VisionConfig:
    model_path: str = "models/face_landmarker.task"
    min_face_detection_confidence: float = 0.5
    min_face_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    max_result_age_ms: int = 750


@dataclass(slots=True)
class TrackingConfig:
    stable_detection_ms: int = 300


@dataclass(slots=True)
class MetricsConfig:
    path: str = "data/metrics.jsonl"


@dataclass(slots=True)
class CalibrationConfig:
    settle_ms: int = 1200
    neutral_hold_ms: int = 1500
    pose_hold_ms: int = 1000
    gesture_hold_ms: int = 700
    step_timeout_ms: int = 12000
    verify_timeout_ms: int = 30000
    min_head_delta: float = 0.04
    stable_tolerance: float = 0.02
    reach: float = 0.8
    max_gesture_attempts: int = 3
    recenter_hold_ms: int = 800
    recenter_timeout_ms: int = 4500


@dataclass(slots=True)
class ProfilesConfig:
    directory: str = "data/profiles"


@dataclass(slots=True)
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    profiles: ProfilesConfig = field(default_factory=ProfilesConfig)

    @classmethod
    def load(cls, path: Path) -> AppConfig:
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"No se pudo leer la configuración {path}: {exc}") from exc
        try:
            config = cls(
                camera=CameraConfig(**raw.get("camera", {})),
                vision=VisionConfig(**raw.get("vision", {})),
                tracking=TrackingConfig(**raw.get("tracking", {})),
                metrics=MetricsConfig(**raw.get("metrics", {})),
                calibration=CalibrationConfig(**raw.get("calibration", {})),
                profiles=ProfilesConfig(**raw.get("profiles", {})),
            )
        except TypeError as exc:
            raise ValueError(f"La configuración contiene campos no válidos: {exc}") from exc
        config.validate()
        return config

    def validate(self) -> None:
        if self.camera.index < 0 or self.camera.width <= 0 or self.camera.height <= 0:
            raise ValueError("Índice y resolución de cámara no válidos")
        if self.camera.fps <= 0:
            raise ValueError("Los FPS solicitados deben ser mayores que cero")
        thresholds = (
            ("detección", self.vision.min_face_detection_confidence),
            ("presencia", self.vision.min_face_presence_confidence),
            ("seguimiento", self.vision.min_tracking_confidence),
        )
        for name, value in thresholds:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"El umbral de {name} debe estar entre 0 y 1")
        if self.tracking.stable_detection_ms < 0 or self.vision.max_result_age_ms <= 0:
            raise ValueError("Los tiempos configurados no son válidos")
        c = self.calibration
        durations = (
            c.settle_ms, c.neutral_hold_ms, c.pose_hold_ms, c.gesture_hold_ms,
            c.step_timeout_ms, c.verify_timeout_ms, c.recenter_hold_ms, c.recenter_timeout_ms,
        )
        if min(durations) < 0 or c.recenter_hold_ms >= c.recenter_timeout_ms:
            raise ValueError("Los tiempos de calibración no son válidos")
        if c.min_head_delta <= 0 or c.stable_tolerance <= 0 or not 0.1 <= c.reach <= 1.0:
            raise ValueError("Los márgenes de calibración no son válidos")
        if c.max_gesture_attempts < 1:
            raise ValueError("Debe permitirse al menos un intento por gesto")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_from_project(path_text: str, project_root: Path) -> Path:
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else project_root / path
