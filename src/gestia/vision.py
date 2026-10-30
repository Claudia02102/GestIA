from __future__ import annotations

import locale
import time
from pathlib import Path

from gestia.domain import FaceResult


class VisionError(RuntimeError):
    pass


class FaceLandmarker:
    """Adaptador MediaPipe independiente de la interfaz."""

    def __init__(
        self,
        model_path: Path,
        detection_confidence: float,
        presence_confidence: float,
        tracking_confidence: float,
    ) -> None:
        if not model_path.is_file():
            raise VisionError(
                f"No se encontró el modelo en {model_path}. Ejecute: python tools/download_model.py"
            )
        try:
            locale.setlocale(locale.LC_NUMERIC, "C")
            import mediapipe as mp

            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=detection_confidence,
                min_face_presence_confidence=presence_confidence,
                min_tracking_confidence=tracking_confidence,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            self._mp = mp
            self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        except (ImportError, RuntimeError, ValueError) as exc:
            raise VisionError(f"No se pudo inicializar MediaPipe Face Landmarker: {exc}") from exc

    def analyze(self, frame_bgr: object, timestamp_ms: int) -> FaceResult:
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        started = time.perf_counter()
        try:
            output = self._landmarker.detect_for_video(image, timestamp_ms)
        except (RuntimeError, ValueError) as exc:
            raise VisionError(f"Falló el análisis facial: {exc}") from exc
        inference_ms = (time.perf_counter() - started) * 1000.0
        landmarks: tuple[tuple[float, float, float], ...] = ()
        if output.face_landmarks:
            landmarks = tuple(
                (float(point.x), float(point.y), float(point.z))
                for point in output.face_landmarks[0]
            )
        return FaceResult(timestamp_ms, landmarks, inference_ms)

    def close(self) -> None:
        self._landmarker.close()
