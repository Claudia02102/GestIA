from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gestia.config import AppConfig, resolve_from_project
from gestia.domain import DisplayPacket, TrackingState
from gestia.persistence import MetricsWriter
from gestia.worker import PipelineWorker

STATE_TEXT = {
    TrackingState.STOPPED: "Detenido",
    TrackingState.SEARCHING: "Buscando rostro",
    TrackingState.TRACKING: "Rostro detectado",
    TrackingState.LOST: "Seguimiento perdido — buscando nuevamente",
    TrackingState.ERROR: "Error",
}


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, project_root: Path) -> None:
        super().__init__()
        self.config, self.project_root = config, project_root
        self.worker: PipelineWorker | None = None
        self.thread: QThread | None = None
        self.metrics = MetricsWriter(resolve_from_project(config.metrics.path, project_root))
        self.setWindowTitle("GestIA — seguimiento facial")
        self.resize(900, 700)
        self._build_ui()
        self._set_state(TrackingState.STOPPED)

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        controls = QHBoxLayout()
        self.camera_selector = QComboBox()
        candidates = list(dict.fromkeys(self.config.camera.candidate_indices))
        if self.config.camera.index not in candidates:
            candidates.insert(0, self.config.camera.index)
        for index in candidates:
            self.camera_selector.addItem(f"Cámara {index}", index)
        self.camera_selector.setCurrentIndex(
            max(0, self.camera_selector.findData(self.config.camera.index))
        )
        self.start_button = QPushButton("Iniciar")
        self.stop_button = QPushButton("Detener")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_tracking)
        self.stop_button.clicked.connect(self.stop_tracking)
        controls.addWidget(QLabel("Cámara:"))
        controls.addWidget(self.camera_selector)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.preview = QLabel("Presione Iniciar para abrir la cámara")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 480)
        self.preview.setStyleSheet(
            "background: #17191c; color: #cbd5e1; border-radius: 8px;"
        )
        layout.addWidget(self.preview, 1)
        self.state_label = QLabel()
        layout.addWidget(self.state_label)

        metrics = QFormLayout()
        self.capture_fps = QLabel("—")
        self.result_fps = QLabel("—")
        self.inference = QLabel("—")
        self.dropped = QLabel("—")
        metrics.addRow("FPS de captura:", self.capture_fps)
        metrics.addRow("FPS de resultados:", self.result_fps)
        metrics.addRow("Duración de inferencia:", self.inference)
        metrics.addRow("Frames reemplazados / resultados obsoletos:", self.dropped)
        layout.addLayout(metrics)
        guidance = QLabel(
            "Mantenga el rostro visible y con iluminación frontal. Las imágenes se "
            "procesan localmente y no se guardan."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        self.setCentralWidget(central)

    @Slot()
    def start_tracking(self) -> None:
        if self.thread is not None:
            return
        self.config.camera.index = int(self.camera_selector.currentData())
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.camera_selector.setEnabled(False)
        self.worker = PipelineWorker(self.config, self.project_root)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.packet_ready.connect(self._show_packet)
        self.worker.state_changed.connect(self._set_state)
        self.worker.error_occurred.connect(self._show_error)
        self.worker.finished.connect(self._session_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._thread_finished)
        self.thread.start()

    @Slot()
    def stop_tracking(self) -> None:
        if self.worker is not None:
            self.stop_button.setEnabled(False)
            self.worker.request_stop()

    @Slot(object)
    def _show_packet(self, packet: DisplayPacket) -> None:
        import cv2

        frame = packet.frame_bgr.copy()
        height, width = frame.shape[:2]
        if packet.result.detected and packet.state is TrackingState.TRACKING:
            xs: list[int] = []
            ys: list[int] = []
            for x_norm, y_norm, _ in packet.result.landmarks:
                x = max(0, min(width - 1, round(x_norm * width)))
                y = max(0, min(height - 1, round(y_norm * height)))
                xs.append(x)
                ys.append(y)
                cv2.circle(frame, (x, y), 1, (74, 222, 128), -1)
            if xs and ys:
                cv2.rectangle(
                    frame, (min(xs), min(ys)), (max(xs), max(ys)), (34, 197, 94), 2
                )
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb.data, width, height, int(rgb.strides[0]), QImage.Format.Format_RGB888
        ).copy()
        self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        perf = packet.performance
        self.capture_fps.setText(f"{perf.capture_fps:.1f}")
        self.result_fps.setText(f"{perf.result_fps:.1f}")
        self.inference.setText(f"{perf.inference_ms:.1f} ms")
        self.dropped.setText(f"{perf.dropped_frames} / {perf.stale_results}")

    @Slot(object)
    def _set_state(self, state: TrackingState) -> None:
        colors = {
            TrackingState.STOPPED: "#64748b",
            TrackingState.SEARCHING: "#ca8a04",
            TrackingState.TRACKING: "#16a34a",
            TrackingState.LOST: "#ea580c",
            TrackingState.ERROR: "#dc2626",
        }
        self.state_label.setText(f"Estado: {STATE_TEXT[state]}")
        self.state_label.setStyleSheet(
            f"font-size: 18px; font-weight: 600; color: {colors[state]};"
        )

    @Slot(str)
    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "GestIA", message)

    @Slot(object)
    def _session_finished(self, summary: dict) -> None:
        try:
            self.metrics.append(summary)
        except OSError as exc:
            QMessageBox.warning(self, "Métricas", f"No se pudieron guardar: {exc}")

    @Slot()
    def _thread_finished(self) -> None:
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.camera_selector.setEnabled(True)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.worker is not None:
            self.worker.request_stop()
        if self.thread is not None and not self.thread.wait(3000):
            QMessageBox.warning(
                self,
                "Cierre en curso",
                "La cámara aún se está liberando. Intente cerrar nuevamente.",
            )
            event.ignore()
            return
        event.accept()
