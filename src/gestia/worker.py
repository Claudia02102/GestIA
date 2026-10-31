from __future__ import annotations

import copy
import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from gestia.capture import CaptureProducer, LatestFrameBuffer, OpenCVCamera
from gestia.config import AppConfig
from gestia.domain import DisplayPacket, PerformanceSnapshot, TrackingState
from gestia.features import extract_features
from gestia.gestures import GestureEngine, GestureFrame
from gestia.profiles import Profile
from gestia.tracking import ResultFreshnessGate, TrackingStateMachine
from gestia.vision import FaceLandmarker, VisionError

LOGGER = logging.getLogger(__name__)


class PipelineWorker(QObject):
    packet_ready = Signal(object)
    state_changed = Signal(object)
    error_occurred = Signal(str)
    finished = Signal(object)

    def __init__(self, config: AppConfig, project_root: Path) -> None:
        super().__init__()
        self.config, self.project_root = config, project_root
        self._stop = threading.Event()
        self._producer: CaptureProducer | None = None
        self._profile_lock = threading.Lock()
        self._pending_profile: Profile | None = None

    def apply_profile(self, profile: Profile) -> None:
        """Puede llamarse desde la interfaz: el cambio se aplica en el siguiente fotograma."""
        with self._profile_lock:
            self._pending_profile = copy.deepcopy(profile)

    def _configure_engine(self, engine: GestureEngine) -> None:
        with self._profile_lock:
            profile, self._pending_profile = self._pending_profile, None
        if profile is not None:
            ranges = {} if profile.calibration is None else profile.calibration.gestures
            engine.configure(profile.gestures, ranges, profile.actions)

    def request_stop(self) -> None:
        self._stop.set()
        if self._producer is not None:
            self._producer.stop_event.set()

    @Slot()
    def run(self) -> None:
        machine = TrackingStateMachine(self.config.tracking.stable_detection_ms)
        gate = ResultFreshnessGate(self.config.vision.max_result_age_ms)
        buffer = LatestFrameBuffer()
        engine = GestureEngine()
        c = self.config.camera
        producer = CaptureProducer(OpenCVCamera(c.index, c.width, c.height, c.fps), buffer)
        self._producer = producer
        landmarker = None
        result_count = stale_count = 0
        started = time.perf_counter()
        last_inference_ms = 0.0
        final_state = machine.start()
        self.state_changed.emit(final_state)
        try:
            model_path = Path(self.config.vision.model_path).expanduser()
            if not model_path.is_absolute():
                model_path = self.project_root / model_path
            v = self.config.vision
            landmarker = FaceLandmarker(
                model_path,
                v.min_face_detection_confidence,
                v.min_face_presence_confidence,
                v.min_tracking_confidence,
            )
            producer.start()
            while not self._stop.is_set():
                frame = buffer.take()
                if producer.error is not None:
                    raise producer.error
                if frame is None:
                    continue
                result = landmarker.analyze(frame.frame_bgr, frame.timestamp_ms)
                now_ms = time.perf_counter_ns() // 1_000_000
                if not gate.accept(result.timestamp_ms, now_ms):
                    stale_count += 1
                    continue
                result_count += 1
                last_inference_ms = result.inference_ms
                final_state = machine.observe(result.detected, result.timestamp_ms)
                features = None
                if final_state is TrackingState.TRACKING:
                    height, width = frame.frame_bgr.shape[:2]
                    features = extract_features(result.landmarks, width / height)
                self._configure_engine(engine)
                gestures = GestureFrame()
                if features is None:
                    # Sin rostro fiable no se reconoce ningún gesto (HU-04).
                    engine.reset()
                else:
                    gestures = engine.update(features, result.timestamp_ms)
                elapsed = max(time.perf_counter() - started, 1e-9)
                performance = PerformanceSnapshot(
                    producer.fps,
                    result_count / elapsed,
                    result.inference_ms,
                    buffer.replaced,
                    stale_count,
                )
                self.state_changed.emit(final_state)
                self.packet_ready.emit(
                    DisplayPacket(
                        frame.frame_bgr, result, final_state, performance, features, gestures
                    )
                )
        except Exception as exc:
            LOGGER.exception("Pipeline failure")
            final_state = machine.fail()
            self.state_changed.emit(final_state)
            message = (
                str(exc)
                if isinstance(exc, VisionError | RuntimeError)
                else f"Error inesperado en el seguimiento: {exc}"
            )
            self.error_occurred.emit(message)
        finally:
            producer.stop()
            if landmarker is not None:
                landmarker.close()
            if final_state is not TrackingState.ERROR:
                final_state = machine.stop()
                self.state_changed.emit(final_state)
            elapsed = max(time.perf_counter() - started, 1e-9)
            self.finished.emit(
                {
                    "camera": {
                        "index": c.index,
                        "requested_width": c.width,
                        "requested_height": c.height,
                        "requested_fps": c.fps,
                        "actual_width": producer.camera.actual_width,
                        "actual_height": producer.camera.actual_height,
                        "actual_fps": producer.camera.actual_fps,
                        "backend": producer.camera.backend,
                    },
                    "duration_seconds": round(elapsed, 3),
                    "captured_frames": producer.frame_count,
                    "processed_results": result_count,
                    "average_capture_fps": round(producer.fps, 3),
                    "average_result_fps": round(result_count / elapsed, 3),
                    "last_inference_ms": round(last_inference_ms, 3),
                    "replaced_frames": buffer.replaced,
                    "stale_results": stale_count,
                    "final_state": str(final_state),
                }
            )
