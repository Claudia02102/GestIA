from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gestia.calibration import Calibration, Recenterer, RecenterStatus
from gestia.config import AppConfig, resolve_from_project
from gestia.domain import DisplayPacket, TrackingState
from gestia.gestures import GESTURES, Action
from gestia.persistence import MetricsWriter
from gestia.profiles import Profile, ProfileStore
from gestia.ui_calibration import CalibrationDialog
from gestia.ui_profile import GesturePanel
from gestia.ui_widgets import PointerPreview
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
        self.store = ProfileStore(resolve_from_project(config.profiles.directory, project_root))
        self.profile: Profile = self.store.load_active()
        self.wizard: CalibrationDialog | None = None
        self.wizard_offered = False
        self.recenterer: Recenterer | None = None
        self.setWindowTitle("GestIA — seguimiento facial")
        self.resize(1280, 760)
        self._build_ui()
        self._load_profiles()
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

        profile_bar = QHBoxLayout()
        self.profile_selector = QComboBox()
        self.profile_selector.setMinimumWidth(180)
        self.profile_selector.activated.connect(self._profile_selected)
        new_profile = QPushButton("Nuevo perfil")
        new_profile.clicked.connect(self.create_profile)
        self.delete_button = QPushButton("Eliminar perfil")
        self.delete_button.clicked.connect(self.delete_profile)
        self.calibrate_button = QPushButton("Calibrar")
        self.calibrate_button.setEnabled(False)
        self.calibrate_button.clicked.connect(self.open_calibration)
        self.recenter_button = QPushButton("Recentrar")
        self.recenter_button.setEnabled(False)
        self.recenter_button.clicked.connect(self.start_recenter)
        self.profile_status = QLabel()
        for widget in (
            QLabel("Perfil:"), self.profile_selector, new_profile, self.delete_button,
            self.calibrate_button, self.recenter_button, self.profile_status,
        ):
            profile_bar.addWidget(widget)
        profile_bar.addStretch()
        layout.addLayout(profile_bar)

        body = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()
        body.addLayout(left, 3)
        body.addLayout(right, 2)
        layout.addLayout(body, 1)

        self.preview = QLabel("Presione Iniciar para abrir la cámara")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 480)
        self.preview.setStyleSheet(
            "background: #17191c; color: #cbd5e1; border-radius: 8px;"
        )
        left.addWidget(self.preview, 1)
        self.state_label = QLabel()
        left.addWidget(self.state_label)

        metrics = QFormLayout()
        self.capture_fps = QLabel("—")
        self.result_fps = QLabel("—")
        self.inference = QLabel("—")
        self.dropped = QLabel("—")
        metrics.addRow("FPS de captura:", self.capture_fps)
        metrics.addRow("FPS de resultados:", self.result_fps)
        metrics.addRow("Duración de inferencia:", self.inference)
        metrics.addRow("Frames reemplazados / resultados obsoletos:", self.dropped)
        left.addLayout(metrics)
        guidance = QLabel(
            "Mantenga el rostro visible y con iluminación frontal. Las imágenes se "
            "procesan localmente y no se guardan."
        )
        guidance.setWordWrap(True)
        left.addWidget(guidance)

        right.addWidget(QLabel("Puntero virtual (vista previa; aún no mueve el cursor):"))
        self.pointer = PointerPreview()
        self.pointer.setMinimumHeight(170)
        right.addWidget(self.pointer)
        self.panel = GesturePanel()
        self.panel.changed.connect(self._profile_changed)
        right.addWidget(self.panel, 1)
        self.setCentralWidget(central)

    # --- Perfiles -------------------------------------------------------------------------

    def _load_profiles(self) -> None:
        self.profile_selector.clear()
        for profile in self.store.list():
            self.profile_selector.addItem(profile.name, profile.id)
        if self.profile_selector.findData(self.profile.id) < 0:
            self.profile_selector.addItem(self.profile.name, self.profile.id)
        self.profile_selector.setCurrentIndex(self.profile_selector.findData(self.profile.id))
        self._activate_profile(self.profile)

    def _activate_profile(self, profile: Profile) -> None:
        self.profile = profile
        self.recenterer = None
        self.panel.set_profile(profile)
        self.pointer.set_pointer(None)
        self._update_profile_status()
        if self.worker is not None:
            self.worker.apply_profile(profile)

    def _update_profile_status(self) -> None:
        if self.profile.calibration is None:
            text, color = "Sin calibrar", "#ca8a04"
        else:
            text, color = "Calibrado", "#16a34a"
        self.profile_status.setText(text)
        self.profile_status.setStyleSheet(f"font-weight: 600; color: {color};")

    def _save_profile(self) -> None:
        try:
            self.store.save(self.profile)
        except OSError as exc:
            QMessageBox.warning(self, "Perfil", f"No se pudo guardar el perfil: {exc}")
        if self.worker is not None:
            self.worker.apply_profile(self.profile)
        self._update_profile_status()

    @Slot()
    def _profile_changed(self) -> None:
        self._save_profile()

    @Slot(int)
    def _profile_selected(self, row: int) -> None:
        profile_id = self.profile_selector.itemData(row)
        if profile_id is None or profile_id == self.profile.id:
            return
        try:
            profile = self.store.load(profile_id)
            self.store.set_active(profile_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Perfil", f"No se pudo cargar el perfil: {exc}")
            self.profile_selector.setCurrentIndex(
                self.profile_selector.findData(self.profile.id)
            )
            return
        self.wizard_offered = False
        self._activate_profile(profile)
        self.panel.log_message(f"Perfil activo: {profile.name}")

    @Slot()
    def create_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Nuevo perfil", "Nombre de la persona usuaria:")
        if not ok:
            return
        try:
            profile = self.store.create(name)
            self.store.set_active(profile.id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Perfil", str(exc))
            return
        self.profile = profile
        self.wizard_offered = False
        self._load_profiles()

    @Slot()
    def delete_profile(self) -> None:
        answer = QMessageBox.question(
            self,
            "Eliminar perfil",
            f"¿Eliminar el perfil «{self.profile.name}»? Se perderán su calibración y sus "
            "ajustes. Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete(self.profile.id)
            self.profile = self.store.load_active()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Perfil", f"No se pudo eliminar el perfil: {exc}")
            return
        self.wizard_offered = False
        self._load_profiles()

    # --- Calibración y recentrado ---------------------------------------------------------

    @Slot()
    def open_calibration(self) -> None:
        if self.wizard is not None or self.worker is None:
            return
        self.wizard_offered = True
        self.recenterer = None
        gestures = [g for g in GESTURES if self.profile.gestures[g].enabled]
        self.wizard = CalibrationDialog(gestures, self.config.calibration, self)
        self.wizard.completed.connect(self._calibration_completed)
        self.wizard.finished.connect(self._wizard_closed)
        self.wizard.setModal(True)
        self.wizard.showFullScreen()

    @Slot(object, list)
    def _calibration_completed(self, calibration: Calibration, skipped: list) -> None:
        self.profile.calibration = calibration
        for gesture in skipped:
            self.profile.gestures[gesture].enabled = False
        if not self.profile.selection_gestures():
            for gesture in skipped:
                self.profile.gestures[gesture].enabled = True
            QMessageBox.warning(
                self,
                "Calibración",
                "Ningún gesto de selección pudo calibrarse. Ajuste los gestos activos y "
                "repita la calibración.",
            )
        elif skipped:
            names = ", ".join(GESTURES[gesture].name for gesture in skipped)
            self.panel.log_message(f"Gestos omitidos y desactivados: {names}")
        self._save_profile()
        self.panel.set_profile(self.profile)
        self.panel.log_message("Calibración guardada en el perfil.")

    @Slot()
    def _wizard_closed(self) -> None:
        if self.wizard is not None:
            self.wizard.deleteLater()
        self.wizard = None

    @Slot()
    def start_recenter(self) -> None:
        if self.profile.calibration is None:
            self.panel.log_message("Calibre el perfil antes de recentrar.")
            return
        if self.recenterer is None:
            self.recenterer = Recenterer(self.config.calibration)
            self.panel.log_message("Recentrando: mantenga la cabeza quieta en su nueva postura…")

    def _feed_recenter(self, packet: DisplayPacket) -> None:
        if self.recenterer is None or self.profile.calibration is None:
            return
        features = packet.features if packet.state is TrackingState.TRACKING else None
        status = self.recenterer.feed(features, packet.result.timestamp_ms)
        if status is RecenterStatus.COLLECTING:
            return
        if status is RecenterStatus.DONE:
            started = self.recenterer.started_ms or packet.result.timestamp_ms
            self.profile.calibration = self.recenterer.apply(self.profile.calibration)
            self._save_profile()
            seconds = (packet.result.timestamp_ms - started) / 1000
            self.panel.log_message(f"Puntero recentrado en {seconds:.1f} s.")
        else:
            self.panel.log_message("No se pudo recentrar: mantenga la cabeza quieta.")
        self.recenterer = None

    @Slot()
    def start_tracking(self) -> None:
        if self.thread is not None:
            return
        self.config.camera.index = int(self.camera_selector.currentData())
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.camera_selector.setEnabled(False)
        self.calibrate_button.setEnabled(True)
        self.recenter_button.setEnabled(True)
        self.worker = PipelineWorker(self.config, self.project_root)
        self.worker.apply_profile(self.profile)
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
        self._render_frame(packet)
        if self.wizard is not None:
            self.wizard.feed(packet)
            return
        self.panel.show_activations(packet.gestures)
        tracking = packet.state is TrackingState.TRACKING
        calibration = self.profile.calibration
        if tracking and packet.features is not None and calibration is not None:
            self.pointer.set_pointer(
                calibration.head.to_pointer(packet.features, self.config.calibration.reach)
            )
        else:
            self.pointer.set_pointer(None)
        if tracking and calibration is None and not self.wizard_offered:
            self.open_calibration()
            return
        for event in packet.gestures.events:
            if event.action is Action.RECALIBRATE:
                self.panel.log_event(event)
                self.start_recenter()
            else:
                self.panel.log_event(event, "(acción simulada; se ejecuta desde la Épica 3)")
        self._feed_recenter(packet)

    def _render_frame(self, packet: DisplayPacket) -> None:
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
        if self.wizard is not None:
            self.wizard.reject()
        self.recenterer = None
        self.pointer.set_pointer(None)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.camera_selector.setEnabled(True)
        self.calibrate_button.setEnabled(False)
        self.recenter_button.setEnabled(False)

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
