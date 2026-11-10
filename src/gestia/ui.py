from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
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

from gestia.app_context import foreground_app
from gestia.calibration import Calibration, Recenterer, RecenterStatus
from gestia.config import AppConfig, resolve_from_project
from gestia.control import (
    ControlMode,
    ControlStatus,
    PointerController,
    PynputBackend,
    ScreenArea,
    apply_speed,
)
from gestia.domain import DisplayPacket, TrackingState
from gestia.gestures import (
    GESTURES,
    Action,
    GestureEvent,
    acts_while_paused,
    positional_gesture_forming,
    resume_hint,
)
from gestia.keyboard import PynputKeyboardBackend
from gestia.persistence import MetricsWriter
from gestia.profiles import Profile, ProfileStore
from gestia.quick_actions import PynputSystemBackend
from gestia.ui_calibration import CalibrationDialog
from gestia.ui_keyboard import KeyboardWindow
from gestia.ui_profile import GesturePanel
from gestia.ui_quick_menu import QuickMenuWindow
from gestia.ui_widgets import PauseIndicator, PointerPreview
from gestia.worker import PipelineWorker

LOGGER = logging.getLogger(__name__)
PAUSE_HOTKEY = "<ctrl>+<alt>+p"
ACTIVE_APP_POLL_MS = 1000
MODE_TEXT = {
    ControlMode.DISABLED: ("Cursor: control desactivado", "#64748b"),
    ControlMode.NO_FACE: ("Cursor: detenido (sin rostro)", "#ea580c"),
    ControlMode.NORMAL: ("Cursor: controlado por la cabeza", "#16a34a"),
    ControlMode.DRAGGING: ("Cursor: arrastrando", "#2563eb"),
    ControlMode.SCROLLING: ("Cursor: modo desplazamiento", "#7c3aed"),
    ControlMode.PAUSED: ("Cursor: EN PAUSA", "#ca8a04"),
}


class HotkeyBridge(QObject):
    """Atajo global de pausa; pynput llama desde su hilo y la señal llega al de la interfaz."""

    triggered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._listener = None
        try:
            from pynput import keyboard

            self._listener = keyboard.GlobalHotKeys({PAUSE_HOTKEY: self.triggered.emit})
            self._listener.start()
        except Exception:  # noqa: BLE001 - sin servidor gráfico o sin permisos
            LOGGER.warning("No se pudo registrar el atajo global de pausa", exc_info=True)
            self._listener = None

    @property
    def active(self) -> bool:
        return self._listener is not None

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None


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
        self.controller: PointerController | None = None
        self.keyboard: KeyboardWindow | None = None
        self.quick_menu: QuickMenuWindow | None = None
        self.pause_indicator = PauseIndicator()
        self.speaking = False
        self.action_app: str | None = None
        self.hotkeys = HotkeyBridge()
        self.hotkeys.triggered.connect(self.toggle_pause)
        self.setWindowTitle("GestIA — seguimiento facial")
        self.resize(1280, 760)
        self._build_ui()
        self._load_profiles()
        self._set_state(TrackingState.STOPPED)
        self.active_app_timer = QTimer(self)
        self.active_app_timer.setInterval(ACTIVE_APP_POLL_MS)
        self.active_app_timer.timeout.connect(self._show_active_app)
        self.active_app_timer.start()
        self._show_active_app()

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
        export_profile = QPushButton("Exportar")
        export_profile.clicked.connect(self.export_profile)
        import_profile = QPushButton("Importar")
        import_profile.clicked.connect(self.import_profile)
        restore = QPushButton("Restaurar valores")
        restore.setToolTip("Vuelve a los valores por defecto de gestos, mapeo, puntero y teclado")
        restore.clicked.connect(self.restore_defaults)
        self.calibrate_button = QPushButton("Calibrar")
        self.calibrate_button.setEnabled(False)
        self.calibrate_button.clicked.connect(self.open_calibration)
        self.recenter_button = QPushButton("Recentrar")
        self.recenter_button.setEnabled(False)
        self.recenter_button.clicked.connect(self.start_recenter)
        self.profile_status = QLabel()
        for widget in (
            QLabel("Perfil:"), self.profile_selector, new_profile, self.delete_button,
            export_profile, import_profile, restore, self.calibrate_button,
            self.recenter_button,
            self.profile_status,
        ):
            profile_bar.addWidget(widget)
        profile_bar.addStretch()
        layout.addLayout(profile_bar)

        control_bar = QHBoxLayout()
        self.control_check = QCheckBox("Controlar el cursor del sistema")
        self.control_check.toggled.connect(self._control_toggled)
        self.pause_button = QPushButton("Pausar control")
        self.pause_button.setEnabled(False)
        self.pause_button.setMinimumWidth(150)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.keyboard_button = QPushButton("Mostrar teclado")
        self.keyboard_button.setCheckable(True)
        self.keyboard_button.setMinimumWidth(150)
        self.keyboard_button.toggled.connect(self._keyboard_toggled)
        self.quick_menu_button = QPushButton("Acciones rápidas")
        self.quick_menu_button.setCheckable(True)
        self.quick_menu_button.setMinimumWidth(150)
        self.quick_menu_button.toggled.connect(self._quick_menu_toggled)
        self.mode_label = QLabel()
        hotkey = "Ctrl+Alt+P pausa o reanuda desde cualquier aplicación."
        hotkey_label = QLabel(hotkey if self.hotkeys.active else "")
        hotkey_label.setStyleSheet("color: #64748b;")
        for widget in (
            self.control_check, self.pause_button, self.keyboard_button,
            self.quick_menu_button, self.mode_label, hotkey_label,
        ):
            control_bar.addWidget(widget)
        control_bar.addStretch()
        layout.addLayout(control_bar)

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

        right.addWidget(QLabel("Puntero (vista previa de la pantalla):"))
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
        self._apply_pointer_settings()
        if self.keyboard is not None:
            self.keyboard.set_settings(profile.keyboard)
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
        self._apply_pointer_settings()

    def _apply_pointer_settings(self) -> None:
        self.control_check.blockSignals(True)
        self.control_check.setChecked(self.profile.pointer.enabled)
        self.control_check.blockSignals(False)
        if self.controller is not None:
            self.controller.configure(self.profile.pointer)

    @Slot(bool)
    def _control_toggled(self, enabled: bool) -> None:
        self.profile.pointer.enabled = enabled
        self._save_profile()

    @Slot()
    def toggle_pause(self) -> None:
        if self.controller is None:
            return
        self.controller.toggle_pause()
        self._pause_changed()

    def _pause_changed(self) -> None:
        """P3-19: el estado de pausa se ve y se oye, aunque GestIA esté detrás de otra ventana."""
        paused = self.controller is not None and self.controller.paused
        self.pause_button.setText("Reanudar control" if paused else "Pausar control")
        self.panel.log_message("Control en pausa." if paused else "Control reanudado.")
        QApplication.beep()
        if paused:
            self.pause_indicator.show_paused(
                resume_hint(self.profile.gestures, self.profile.actions)
            )
        else:
            self.pause_indicator.hide()

    def _create_controller(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geometry, ratio = screen.geometry(), screen.devicePixelRatio()
        # Qt trabaja en píxeles lógicos; SendInput, en físicos (escalado de Windows).
        area = ScreenArea(
            round(geometry.x() * ratio), round(geometry.y() * ratio),
            round(geometry.width() * ratio), round(geometry.height() * ratio),
        )
        try:
            backend = PynputBackend()
        except Exception as exc:  # noqa: BLE001 - p. ej. sin servidor gráfico
            QMessageBox.warning(
                self, "Control del cursor", f"No se puede controlar el cursor: {exc}"
            )
            return
        self.controller = PointerController(backend, area, self.profile.pointer)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Pausar control")

    def _show_control(self, status: ControlStatus) -> None:
        text, color = MODE_TEXT[status.mode]
        if status.dwell_progress > 0:
            text += f" · permanencia {status.dwell_progress:.0%}"
        self.mode_label.setText(text)
        self.mode_label.setStyleSheet(f"font-weight: 600; color: {color};")

    @Slot()
    def _profile_changed(self) -> None:
        self._save_profile()
        if self.keyboard is not None:
            self.keyboard.set_settings(self.profile.keyboard)

    # --- Teclado virtual (Épica E4) -------------------------------------------------------

    @Slot(bool)
    def _keyboard_toggled(self, show: bool) -> None:
        if not show:
            if self.keyboard is not None:
                self.keyboard.hide()
            self.keyboard_button.setText("Mostrar teclado")
            return
        if self.keyboard is None:
            try:
                backend = PynputKeyboardBackend()
            except Exception as exc:  # noqa: BLE001 - p. ej. sin servidor gráfico
                QMessageBox.warning(self, "Teclado", f"No se puede escribir en el sistema: {exc}")
                self.keyboard_button.setChecked(False)
                return
            self.keyboard = KeyboardWindow(self.profile.keyboard, backend)
            self.keyboard.learned.connect(self._word_learned)
            self.keyboard.closed.connect(lambda: self.keyboard_button.setChecked(False))
        self.keyboard.show()
        self.keyboard_button.setText("Ocultar teclado")

    @Slot(str)
    def _word_learned(self, _word: str) -> None:
        try:
            self.store.save(self.profile)
        except OSError as exc:
            LOGGER.warning("No se pudo guardar el vocabulario: %s", exc)
        self.panel.refresh_keyboard()

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

    # --- Exportar e importar (P3-17) ---------------------------------------------------------

    @Slot()
    def export_profile(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar perfil", f"{self.profile.id}.json", "Perfil de GestIA (*.json)"
        )
        if not path:
            return
        try:
            self.store.export_profile(self.profile, Path(path))
        except OSError as exc:
            QMessageBox.warning(self, "Exportar perfil", f"No se pudo exportar: {exc}")
            return
        self.panel.log_message(f"Perfil «{self.profile.name}» exportado.")

    @Slot()
    def import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar perfil", "", "Perfil de GestIA (*.json)"
        )
        if not path:
            return
        try:
            profile = self.store.import_profile(Path(path))
            self.store.set_active(profile.id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self, "Importar perfil",
                f"No se importó el archivo y la configuración actual no cambió.\n\n{exc}",
            )
            return
        self.profile = profile
        self.wizard_offered = False
        self._load_profiles()
        self.panel.log_message(f"Perfil «{profile.name}» importado.")

    # --- Restaurar valores por defecto (P3-18) ----------------------------------------------

    @Slot()
    def restore_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "Restaurar valores por defecto",
            f"¿Restaurar los valores por defecto del perfil «{self.profile.name}»?\n\n"
            "Vuelven a su valor inicial: gestos activos, sensibilidad y tiempo de cada gesto, "
            "mapeo de acciones (se borran los mapeos por aplicación), ajustes del puntero "
            "(incluido el control del cursor) y distribución y tamaño del teclado.\n\n"
            "Se conservan la calibración, las frases frecuentes y las palabras aprendidas.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.controller is not None:
            # Un arrastre o desplazamiento en curso usaba el mapeo que se va a reemplazar.
            self.controller.release_all(cancel=True)
        self.profile.restore_defaults()
        self._save_profile()
        self.panel.set_profile(self.profile)
        if self.keyboard is not None:
            self.keyboard.set_settings(self.profile.keyboard)
        self.panel.log_message("Valores por defecto restaurados.")
        missing = self.profile.uncalibrated_gestures() if self.profile.calibrated else []
        if missing:
            names = ", ".join(GESTURES[gesture].name for gesture in missing)
            QMessageBox.information(
                self,
                "Restaurar valores por defecto",
                f"Estos gestos quedaron activos pero no están calibrados: {names}. No se "
                "reconocerán hasta que pulse «Calibrar».",
            )

    # --- Mapeo por aplicación (P3-16) --------------------------------------------------------

    @Slot()
    def _show_active_app(self) -> None:
        self.panel.set_active_app(foreground_app())

    def _event_for_active_app(self, event: GestureEvent) -> GestureEvent:
        """Traduce el gesto con el mapeo de la ventana activa.

        Durante un arrastre o un desplazamiento se conserva el mapeo con el que empezaron, para
        poder terminarlos aunque el cursor pase sobre otra aplicación.
        """
        controller = self.controller
        locked = controller is not None and controller.mode in (
            ControlMode.DRAGGING, ControlMode.SCROLLING,
        )
        if not locked:
            self.action_app = foreground_app()
        paused = controller is not None and controller.paused
        action = self.profile.action_for(event.gesture, self.action_app, paused)
        return event if action is None else replace(event, action=action)

    # --- Menú de acciones rápidas (P3-11) ------------------------------------------------

    @Slot(bool)
    def _quick_menu_toggled(self, show: bool) -> None:
        if not show:
            if self.quick_menu is not None:
                self.quick_menu.hide()
            return
        if self.quick_menu is None:
            try:
                backend = PynputSystemBackend()
            except Exception as exc:  # noqa: BLE001 - p. ej. sin servidor gráfico
                QMessageBox.warning(
                    self, "Acciones rápidas", f"No se puede controlar el sistema: {exc}"
                )
                self.quick_menu_button.setChecked(False)
                return
            self.quick_menu = QuickMenuWindow(backend)
            self.quick_menu.closed.connect(lambda: self.quick_menu_button.setChecked(False))
        self.quick_menu.show()

    # --- Calibración y recentrado ---------------------------------------------------------

    @Slot()
    def open_calibration(self) -> None:
        if self.wizard is not None or self.worker is None:
            return
        self.wizard_offered = True
        self.recenterer = None
        # El teclado queda siempre encima: se oculta para no tapar el asistente.
        self.keyboard_button.setChecked(False)
        self.quick_menu_button.setChecked(False)
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
        self._create_controller()
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
        pointer = None
        if tracking and packet.features is not None and calibration is not None:
            pointer = calibration.head.to_pointer(packet.features, self.config.calibration.reach)
        self.pointer.set_pointer(
            None if pointer is None else apply_speed(pointer, self.profile.pointer.speed)
        )
        if tracking and calibration is None and not self.wizard_offered:
            self.open_calibration()
            return
        if packet.gestures.speaking != self.speaking:
            # P3-22: mientras la persona habla, abrir la boca o sonreír no ejecuta acciones.
            self.speaking = packet.gestures.speaking
            self.panel.log_message(
                "Hablando: los gestos de la boca esperan." if self.speaking
                else "Gestos de la boca disponibles otra vez."
            )
        os_events = []
        paused = self.controller is not None and self.controller.paused
        for event in packet.gestures.events:
            event = self._event_for_active_app(event)
            self.panel.log_event(event)
            if paused and not acts_while_paused(event.action):
                # P3-19: en pausa ningún gesto actúa, salvo el de reanudar.
                self.panel.log_message("Ignorado: el control está en pausa.")
            elif event.action is Action.RECALIBRATE:
                self.start_recenter()
            elif event.action is Action.QUICK_MENU:
                self.quick_menu_button.toggle()
            else:
                os_events.append(event)
        if self.controller is not None:
            hold = positional_gesture_forming(
                packet.gestures.activations,
                self.profile.gestures,
                self.profile.actions_for(self.action_app),
            )
            status = self.controller.update(
                pointer, os_events, packet.result.timestamp_ms, hold_position=hold
            )
            for item in status.executed:
                self.panel.log_message(f"Ejecutado: {item}")
            if self.controller.paused != paused:
                self._pause_changed()
            self._show_control(status)
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
        if self.controller is not None:
            self.controller.release_all(cancel=True)
            self.controller = None
        self.pause_indicator.hide()
        self.pause_button.setEnabled(False)
        self.mode_label.setText("")
        self.recenterer = None
        self.pointer.set_pointer(None)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.camera_selector.setEnabled(True)
        self.calibrate_button.setEnabled(False)
        self.recenter_button.setEnabled(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.controller is not None:
            self.controller.release_all(cancel=True)
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
        self.hotkeys.stop()
        if self.keyboard is not None:
            self.keyboard.close()
        if self.quick_menu is not None:
            self.quick_menu.close()
        self.pause_indicator.close()
        event.accept()
