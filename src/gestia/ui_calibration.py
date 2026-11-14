"""Asistente de calibración a pantalla completa: avanza solo con gestos (HU-06)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gestia import theme
from gestia.calibration import Calibration, CalibrationSession, SessionUpdate, Step, StepKind
from gestia.config import CalibrationConfig
from gestia.domain import DisplayPacket, TrackingState
from gestia.gestures import GESTURES, GestureId
from gestia.ui_widgets import PointerPreview

STEP_TITLES = {
    StepKind.NEUTRAL: "Posición de reposo",
    StepKind.HEAD_LEFT: "Giro a la izquierda",
    StepKind.HEAD_RIGHT: "Giro a la derecha",
    StepKind.HEAD_UP: "Inclinación hacia arriba",
    StepKind.HEAD_DOWN: "Inclinación hacia abajo",
    StepKind.CORNERS: "Verificación de esquinas",
    StepKind.DONE: "Fin",
}


def step_title(step: Step) -> str:
    if step.kind is StepKind.GESTURE and step.gesture is not None:
        return f"Gesto: {GESTURES[step.gesture].name}"
    return STEP_TITLES[step.kind]


class CalibrationDialog(QDialog):
    completed = Signal(object, list)

    def __init__(
        self, gestures: list[GestureId], config: CalibrationConfig, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.session = CalibrationSession(gestures, config)
        self._shown_index = -1
        self.setWindowTitle("GestIA — asistente de calibración")
        # Siempre oscuro: a pantalla completa ayuda a concentrarse en la instrucción.
        p = theme.DARK
        self.palette_ = p
        self.setStyleSheet(
            f"QDialog {{ background: {p.background}; }} QLabel {{ color: {p.text}; }}"
            f"QProgressBar {{ background: {p.border}; border: none; border-radius: 6px; }}"
            f"QProgressBar::chunk {{ background: {p.accent}; border-radius: 6px; }}"
            f"QPushButton {{ background: {p.surface_alt}; color: {p.text}; "
            f"border: 1px solid {p.border}; border-radius: 16px; padding: 8px 16px; }}"
        )
        layout = QHBoxLayout(self)

        self.steps_list = QListWidget()
        self.steps_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.steps_list.setMinimumWidth(240)
        self.steps_list.setMaximumWidth(320)
        self.steps_list.setStyleSheet(
            f"QListWidget {{ background: {p.surface}; color: {p.text}; font-size: 15px; "
            f"border: 1px solid {p.border}; border-radius: 12px; }}"
            f"QListWidget::item:selected {{ background: {p.accent_soft}; color: {p.accent}; }}"
        )
        for step in self.session.steps[:-1]:
            self.steps_list.addItem(QListWidgetItem(step_title(step)))
        layout.addWidget(self.steps_list)

        center = QVBoxLayout()
        self.counter = QLabel()
        self.counter.setStyleSheet(f"font-size: 16px; color: {p.accent}; font-weight: 700;")
        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setStyleSheet("font-size: 32px; font-weight: 700;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(22)
        self.feedback = QLabel(" ")
        self.feedback.setWordWrap(True)
        self.feedback.setStyleSheet(f"font-size: 20px; color: {p.warning};")
        self.pointer = PointerPreview(show_corners=True)
        self.pointer.setMinimumSize(480, 270)
        self.pointer.hide()
        hint = QLabel(
            "Cada paso avanza solo al mantener la posición. Si un paso no se logra, el "
            "asistente pide repetirlo. Un gesto que no pueda realizar se omite tras "
            f"{config.max_gesture_attempts} intentos."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size: 15px; color: {p.text_muted};")
        center.addWidget(self.counter)
        center.addWidget(self.instruction)
        center.addWidget(self.progress)
        center.addWidget(self.feedback)
        center.addWidget(self.pointer, 1)
        center.addStretch()
        center.addWidget(hint)
        layout.addLayout(center, 1)

        side = QVBoxLayout()
        self.camera = QLabel("Esperando cámara…")
        self.camera.setFixedSize(320, 240)
        self.camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera.setStyleSheet(f"background: {p.preview}; border-radius: 12px;")
        cancel = QPushButton("Cancelar (asistente)")
        cancel.clicked.connect(self.reject)
        side.addWidget(self.camera)
        side.addStretch()
        side.addWidget(cancel)
        layout.addLayout(side)
        self._show_step()

    def _show_step(self) -> None:
        session = self.session
        step = session.step
        total = len(session.steps) - 1
        if self._shown_index != session.index:
            self._shown_index = session.index
            for row in range(self.steps_list.count()):
                item = self.steps_list.item(row)
                prefix = "✔ " if row < session.index else ("➜ " if row == session.index else "   ")
                item.setText(prefix + step_title(session.steps[row]))
            if session.index < total:
                self.steps_list.setCurrentRow(session.index)
        number = min(session.index + 1, total)
        attempt = f" · intento {session.attempts}" if session.attempts > 1 else ""
        self.counter.setText(f"Paso {number} de {total} — {step_title(step)}{attempt}")
        self.instruction.setText(step.instruction)
        self.pointer.setVisible(step.kind is StepKind.CORNERS)

    def feed(self, packet: DisplayPacket) -> None:
        if self.session.finished:
            return
        features = packet.features if packet.state is TrackingState.TRACKING else None
        update = self.session.feed(features, packet.result.timestamp_ms)
        self._render(update)
        self._show_camera(packet)

    def _render(self, update: SessionUpdate) -> None:
        if update.step_completed or update.step_failed:
            QApplication.beep()
        if update.message:
            p = self.palette_
            color = p.danger if update.step_failed else (
                p.success if update.step_completed else p.warning
            )
            self.feedback.setStyleSheet(f"font-size: 20px; color: {color};")
            self.feedback.setText(update.message)
        self.progress.setValue(round(update.progress * 100))
        if update.pointer is not None or self.session.step.kind is not StepKind.CORNERS:
            self.pointer.set_pointer(update.pointer, update.corners_reached)
        self._show_step()
        if self.session.finished:
            self.instruction.setText("Calibración completada. Guardando el perfil…")
            QTimer.singleShot(1500, self._finish)

    def _finish(self) -> None:
        result: Calibration | None = self.session.result
        if result is not None:
            self.completed.emit(result, list(self.session.skipped))
        self.accept()

    def _show_camera(self, packet: DisplayPacket) -> None:
        import cv2

        frame = packet.frame_bgr
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, width, height, int(rgb.strides[0]), QImage.Format.Format_RGB888)
        self.camera.setPixmap(
            QPixmap.fromImage(image.copy()).scaled(
                self.camera.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
