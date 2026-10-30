from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol


class CameraError(RuntimeError):
    pass


class CameraDevice(Protocol):
    def open(self) -> None: ...
    def read(self) -> tuple[bool, object]: ...
    def close(self) -> None: ...


class OpenCVCamera:
    def __init__(self, index: int, width: int, height: int, fps: int) -> None:
        self.index, self.width, self.height, self.fps = index, width, height, fps
        self._capture = None
        self.actual_width = 0
        self.actual_height = 0
        self.actual_fps = 0.0
        self.backend = "no informado"

    def open(self) -> None:
        import cv2

        capture = cv2.VideoCapture(self.index)
        if not capture.isOpened():
            capture.release()
            raise CameraError(
                f"No se pudo abrir la cámara {self.index}. Verifique permisos y que no esté en uso."
            )
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.actual_fps = float(capture.get(cv2.CAP_PROP_FPS))
        self.backend = capture.getBackendName()
        self._capture = capture

    def read(self) -> tuple[bool, object]:
        return (False, None) if self._capture is None else self._capture.read()

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    sequence: int
    timestamp_ms: int
    frame_bgr: object


class LatestFrameBuffer:
    """Buzón de capacidad uno: siempre conserva el fotograma más reciente."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._latest: CapturedFrame | None = None
        self._closed = False
        self.replaced = 0

    def put(self, frame: CapturedFrame) -> None:
        with self._condition:
            if self._latest is not None:
                self.replaced += 1
            self._latest = frame
            self._condition.notify()

    def take(self, timeout: float = 0.25) -> CapturedFrame | None:
        with self._condition:
            if self._latest is None and not self._closed:
                self._condition.wait(timeout)
            frame, self._latest = self._latest, None
            return frame

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


class CaptureProducer:
    def __init__(self, camera: CameraDevice, output: LatestFrameBuffer) -> None:
        self.camera, self.output = camera, output
        self.stop_event = threading.Event()
        self.error: CameraError | None = None
        self.frame_count = 0
        self.started_at = 0.0
        self._thread: threading.Thread | None = None

    @property
    def fps(self) -> float:
        elapsed = time.perf_counter() - self.started_at
        return self.frame_count / elapsed if self.started_at and elapsed > 0 else 0.0

    def start(self) -> None:
        self.camera.open()
        self.started_at = time.perf_counter()
        self._thread = threading.Thread(target=self._run, name="camera-capture", daemon=False)
        self._thread.start()

    def _run(self) -> None:
        failures = sequence = 0
        last_timestamp_ms = -1
        try:
            while not self.stop_event.is_set():
                ok, image = self.camera.read()
                if not ok or image is None:
                    failures += 1
                    if failures >= 5:
                        self.error = CameraError(
                            "La cámara dejó de entregar imágenes o fue desconectada."
                        )
                        break
                    time.sleep(0.02)
                    continue
                failures = 0
                sequence += 1
                self.frame_count += 1
                # MediaPipe exige timestamps estrictamente crecientes; perf_counter tiene
                # resolución alta también en Windows (monotonic avanza cada ~15,6 ms).
                timestamp_ms = max(time.perf_counter_ns() // 1_000_000, last_timestamp_ms + 1)
                last_timestamp_ms = timestamp_ms
                self.output.put(CapturedFrame(sequence, timestamp_ms, image))
        finally:
            self.camera.close()
            self.output.close()

    def stop(self) -> None:
        self.stop_event.set()
        self.output.close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.camera.close()
