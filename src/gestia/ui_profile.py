"""Panel de gestos del perfil: selección (HU-07), sensibilidad (HU-08), mapeo y eventos."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gestia.gestures import (
    ACTION_TEXT,
    GESTURES,
    MAX_SENSITIVITY,
    MIN_SENSITIVITY,
    GestureEvent,
    GestureFrame,
    GestureId,
)
from gestia.profiles import Profile

MAX_EVENTS = 50


class GesturePanel(QTabWidget):
    """Edita el perfil en memoria y emite ``changed`` para guardarlo y aplicarlo en vivo."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile: Profile | None = None
        self._loading = False
        self.checks: dict[GestureId, QCheckBox] = {}
        self.status: dict[GestureId, QLabel] = {}
        self.sliders: dict[GestureId, QSlider] = {}
        self.slider_labels: dict[GestureId, QLabel] = {}
        self.holds: dict[GestureId, QSpinBox] = {}
        self.bars: dict[GestureId, QProgressBar] = {}

        page = QWidget()
        grid = QGridLayout(page)
        for column, title in enumerate(
            ("Gesto", "Estado", "Sensibilidad", "", "Sostener (ms)", "Intensidad actual")
        ):
            grid.addWidget(QLabel(f"<b>{title}</b>"), 0, column)
        for row, gesture in enumerate(GESTURES, start=1):
            check = QCheckBox(GESTURES[gesture].name)
            check.toggled.connect(lambda on, g=gesture: self._toggle(g, on))
            status = QLabel()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(MIN_SENSITIVITY, MAX_SENSITIVITY)
            slider.setMinimumWidth(110)
            slider.valueChanged.connect(lambda value, g=gesture: self._sensitivity(g, value))
            label = QLabel()
            label.setMinimumWidth(110)
            hold = QSpinBox()
            hold.setRange(0, 3000)
            hold.setSingleStep(50)
            hold.valueChanged.connect(lambda value, g=gesture: self._hold(g, value))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(14)
            for column, widget in enumerate((check, status, slider, label, hold, bar)):
                grid.addWidget(widget, row, column)
            self.checks[gesture], self.status[gesture] = check, status
            self.sliders[gesture], self.slider_labels[gesture] = slider, label
            self.holds[gesture], self.bars[gesture] = hold, bar
        note = QLabel(
            "Mayor sensibilidad = basta una fracción menor del gesto calibrado. Los cambios se "
            "aplican al instante y se guardan en el perfil. La barra marca la intensidad "
            "respecto de su gesto calibrado (llena = 100 %)."
        )
        note.setWordWrap(True)
        grid.addWidget(note, len(GESTURES) + 1, 0, 1, 6)
        grid.setRowStretch(len(GESTURES) + 2, 1)
        self.addTab(page, "Gestos")

        mapping_page = QWidget()
        mapping_layout = QVBoxLayout(mapping_page)
        self.mapping = QListWidget()
        mapping_layout.addWidget(QLabel("Gestos activos y acción asignada:"))
        mapping_layout.addWidget(self.mapping)
        mapping_layout.addWidget(
            QLabel("Las acciones sobre el sistema operativo se implementan en la Épica 3.")
        )
        self.addTab(mapping_page, "Mapeo")

        self.events = QListWidget()
        self.addTab(self.events, "Eventos")

    def set_profile(self, profile: Profile) -> None:
        self.profile = profile
        self._loading = True
        try:
            for gesture, settings in profile.gestures.items():
                self.checks[gesture].setChecked(settings.enabled)
                self.sliders[gesture].setValue(settings.sensitivity)
                self.holds[gesture].setValue(settings.hold_ms)
                self._update_label(gesture)
        finally:
            self._loading = False
        self.refresh()

    def refresh(self) -> None:
        if self.profile is None:
            return
        for gesture, settings in self.profile.gestures.items():
            if not settings.enabled:
                text = "Desactivado"
            elif self.profile.is_gesture_calibrated(gesture):
                text = "Calibrado"
            else:
                text = "Sin calibrar"
            self.status[gesture].setText(text)
            for widget in (self.sliders[gesture], self.holds[gesture], self.bars[gesture]):
                widget.setEnabled(settings.enabled)
        self.mapping.clear()
        for gesture, settings in self.profile.gestures.items():
            action = self.profile.actions.get(gesture)
            if settings.enabled and action is not None:
                self.mapping.addItem(f"{GESTURES[gesture].name}  →  {ACTION_TEXT[action]}")

    def _update_label(self, gesture: GestureId) -> None:
        assert self.profile is not None
        settings = self.profile.gestures[gesture]
        self.slider_labels[gesture].setText(
            f"{settings.sensitivity} (umbral {settings.threshold:.0%})"
        )

    def _toggle(self, gesture: GestureId, enabled: bool) -> None:
        if self._loading or self.profile is None:
            return
        settings = self.profile.gestures[gesture]
        settings.enabled = enabled
        if not enabled and not self.profile.selection_gestures():
            settings.enabled = True
            self._loading = True
            self.checks[gesture].setChecked(True)
            self._loading = False
            QMessageBox.warning(
                self,
                "Gestos de selección",
                "Debe quedar al menos un gesto de selección activo (clic, doble clic o "
                "arrastre). Active otro antes de desactivar este.",
            )
            return
        self.refresh()
        self.changed.emit()

    def _sensitivity(self, gesture: GestureId, value: int) -> None:
        if self._loading or self.profile is None:
            return
        self.profile.gestures[gesture].sensitivity = value
        self._update_label(gesture)
        self.changed.emit()

    def _hold(self, gesture: GestureId, value: int) -> None:
        if self._loading or self.profile is None:
            return
        self.profile.gestures[gesture].hold_ms = value
        self.changed.emit()

    def show_activations(self, frame: GestureFrame) -> None:
        for gesture, bar in self.bars.items():
            bar.setValue(round(min(frame.activations.get(gesture, 0.0), 1.0) * 100))

    def log_event(self, event: GestureEvent, note: str = "") -> None:
        text = f"{time.strftime('%H:%M:%S')}  {GESTURES[event.gesture].name} → " \
               f"{ACTION_TEXT[event.action]}"
        self.events.insertItem(0, f"{text}  {note}".rstrip())
        while self.events.count() > MAX_EVENTS:
            self.events.takeItem(self.events.count() - 1)

    def log_message(self, message: str) -> None:
        self.events.insertItem(0, f"{time.strftime('%H:%M:%S')}  {message}")
