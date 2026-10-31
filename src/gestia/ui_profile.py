"""Panel del perfil: gestos (HU-07, HU-08), puntero, teclado (HU-22, HU-23), mapeo y eventos."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
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
from gestia.keyboard import (
    LAYOUT_TEXT,
    MAX_KEY_SIZE,
    MAX_PHRASE_LENGTH,
    MAX_PHRASES,
    MIN_KEY_SIZE,
    Layout,
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
            QLabel("La reasignación de gestos a acciones se implementa en la Épica 5.")
        )
        self.addTab(mapping_page, "Mapeo")

        self.addTab(self._build_pointer_page(), "Puntero")
        self.addTab(self._build_keyboard_page(), "Teclado")

        self.events = QListWidget()
        self.addTab(self.events, "Eventos")

    def _build_pointer_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(5, 30)
        self.speed_label = QLabel()
        self.smoothing = QSlider(Qt.Orientation.Horizontal)
        self.smoothing.setRange(0, 10)
        self.smoothing_label = QLabel()
        self.dead_zone = QSpinBox()
        self.dead_zone.setRange(0, 40)
        self.dead_zone.setSuffix(" px")
        self.dwell = QCheckBox("Clic al mantener el cursor quieto")
        self.dwell_ms = QSpinBox()
        self.dwell_ms.setRange(200, 5000)
        self.dwell_ms.setSingleStep(100)
        self.dwell_ms.setSuffix(" ms")
        self.dwell_radius = QSpinBox()
        self.dwell_radius.setRange(5, 150)
        self.dwell_radius.setSuffix(" px")
        self.scroll_speed = QSlider(Qt.Orientation.Horizontal)
        self.scroll_speed.setRange(1, 10)
        form.addRow("Velocidad:", self.speed)
        form.addRow("", self.speed_label)
        form.addRow("Suavizado:", self.smoothing)
        form.addRow("", self.smoothing_label)
        form.addRow("Zona muerta:", self.dead_zone)
        form.addRow(self.dwell)
        form.addRow("Tiempo de permanencia:", self.dwell_ms)
        form.addRow("Radio de permanencia:", self.dwell_radius)
        form.addRow("Velocidad de desplazamiento:", self.scroll_speed)
        note = QLabel(
            "Más velocidad = menos giro de cabeza para recorrer la pantalla. Más suavizado = "
            "menos temblor, algo más de retardo. La zona muerta evita que el cursor se mueva "
            "con la cabeza quieta. Modo desplazamiento: active su gesto y aleje la cabeza del "
            "centro; repita el gesto (o el de clic izquierdo) para salir."
        )
        note.setWordWrap(True)
        form.addRow(note)
        for slider in (self.speed, self.smoothing, self.scroll_speed):
            slider.valueChanged.connect(self._pointer_changed)
        for spin in (self.dead_zone, self.dwell_ms, self.dwell_radius):
            spin.valueChanged.connect(self._pointer_changed)
        self.dwell.toggled.connect(self._pointer_changed)
        return page

    def _build_keyboard_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.layout_selector = QComboBox()
        for layout in Layout:
            self.layout_selector.addItem(LAYOUT_TEXT[layout], str(layout))
        self.layout_selector.currentIndexChanged.connect(self._keyboard_changed)
        self.key_size = QSpinBox()
        self.key_size.setRange(MIN_KEY_SIZE, MAX_KEY_SIZE)
        self.key_size.setSingleStep(4)
        self.key_size.setSuffix(" px")
        self.key_size.valueChanged.connect(self._keyboard_changed)
        form.addRow("Distribución:", self.layout_selector)
        form.addRow("Tamaño de tecla:", self.key_size)

        self.phrases = QListWidget()
        self.phrases.setMaximumHeight(150)
        buttons = QHBoxLayout()
        for text, slot in (
            ("Añadir", self._add_phrase),
            ("Editar", self._edit_phrase),
            ("Eliminar", self._delete_phrase),
            ("Subir", self._raise_phrase),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        form.addRow(QLabel("Frases frecuentes (botón «Frases» del teclado):"))
        form.addRow(self.phrases)
        form.addRow(buttons)

        self.vocabulary_label = QLabel()
        forget = QPushButton("Olvidar palabras aprendidas")
        forget.clicked.connect(self._forget_words)
        form.addRow(self.vocabulary_label, forget)
        note = QLabel(
            "Si el tamaño no cabe en la pantalla, el teclado usa el mayor que cabe. Las "
            "sugerencias vienen de un diccionario local en español y de las palabras que "
            "escribe con el teclado (una palabra nueva se sugiere desde la segunda vez). "
            "Solo se guardan palabras sueltas y su conteo en el perfil."
        )
        note.setWordWrap(True)
        form.addRow(note)
        return page

    def _keyboard_changed(self) -> None:
        if self._loading or self.profile is None:
            return
        keyboard = self.profile.keyboard
        keyboard.layout = Layout(self.layout_selector.currentData())
        keyboard.key_size = self.key_size.value()
        self.changed.emit()

    def _load_keyboard(self) -> None:
        assert self.profile is not None
        keyboard = self.profile.keyboard
        self.layout_selector.setCurrentIndex(self.layout_selector.findData(str(keyboard.layout)))
        self.key_size.setValue(keyboard.key_size)
        self.refresh_keyboard()

    def refresh_keyboard(self) -> None:
        """Lista de frases y conteo de palabras aprendidas."""
        if self.profile is None:
            return
        keyboard = self.profile.keyboard
        row = self.phrases.currentRow()
        self.phrases.clear()
        self.phrases.addItems(keyboard.phrases)
        self.phrases.setCurrentRow(min(row, self.phrases.count() - 1))
        self.vocabulary_label.setText(f"Palabras aprendidas: {len(keyboard.vocabulary)}")

    def _ask_phrase(self, title: str, text: str = "") -> str | None:
        value, ok = QInputDialog.getText(self, title, "Frase:", text=text)
        value = value.strip()
        if not ok or not value:
            return None
        if len(value) > MAX_PHRASE_LENGTH:
            QMessageBox.warning(self, title, f"Máximo {MAX_PHRASE_LENGTH} caracteres.")
            return None
        return value

    def _phrases_changed(self) -> None:
        self.refresh_keyboard()
        self.changed.emit()

    def _add_phrase(self) -> None:
        if self.profile is None:
            return
        if len(self.profile.keyboard.phrases) >= MAX_PHRASES:
            QMessageBox.warning(self, "Frases", f"Se admiten hasta {MAX_PHRASES} frases.")
            return
        value = self._ask_phrase("Nueva frase")
        if value is not None:
            self.profile.keyboard.phrases.append(value)
            self.phrases.setCurrentRow(-1)
            self._phrases_changed()
            self.phrases.setCurrentRow(self.phrases.count() - 1)

    def _edit_phrase(self) -> None:
        row = self.phrases.currentRow()
        if self.profile is None or row < 0:
            return
        value = self._ask_phrase("Editar frase", self.profile.keyboard.phrases[row])
        if value is not None:
            self.profile.keyboard.phrases[row] = value
            self._phrases_changed()

    def _delete_phrase(self) -> None:
        row = self.phrases.currentRow()
        if self.profile is None or row < 0:
            return
        del self.profile.keyboard.phrases[row]
        self._phrases_changed()

    def _raise_phrase(self) -> None:
        row = self.phrases.currentRow()
        if self.profile is None or row < 1:
            return
        phrases = self.profile.keyboard.phrases
        phrases[row - 1], phrases[row] = phrases[row], phrases[row - 1]
        self.phrases.setCurrentRow(row - 1)
        self._phrases_changed()

    def _forget_words(self) -> None:
        if self.profile is None:
            return
        answer = QMessageBox.question(
            self,
            "Palabras aprendidas",
            "¿Olvidar todas las palabras aprendidas de este perfil?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.profile.keyboard.vocabulary.clear()
            self._phrases_changed()

    def _pointer_labels(self) -> None:
        self.speed_label.setText(f"× {self.speed.value() / 10:.1f}")
        level = self.smoothing.value()
        self.smoothing_label.setText("Sin suavizado" if level == 0 else f"Nivel {level}")
        for widget in (self.dwell_ms, self.dwell_radius):
            widget.setEnabled(self.dwell.isChecked())

    def _pointer_changed(self) -> None:
        self._pointer_labels()
        if self._loading or self.profile is None:
            return
        pointer = self.profile.pointer
        pointer.speed = self.speed.value() / 10
        pointer.smoothing = self.smoothing.value()
        pointer.dead_zone_px = self.dead_zone.value()
        pointer.dwell_enabled = self.dwell.isChecked()
        pointer.dwell_ms = self.dwell_ms.value()
        pointer.dwell_radius_px = self.dwell_radius.value()
        pointer.scroll_speed = self.scroll_speed.value()
        self.changed.emit()

    def set_profile(self, profile: Profile) -> None:
        self.profile = profile
        self._loading = True
        try:
            for gesture, settings in profile.gestures.items():
                self.checks[gesture].setChecked(settings.enabled)
                self.sliders[gesture].setValue(settings.sensitivity)
                self.holds[gesture].setValue(settings.hold_ms)
                self._update_label(gesture)
            pointer = profile.pointer
            self.speed.setValue(round(pointer.speed * 10))
            self.smoothing.setValue(pointer.smoothing)
            self.dead_zone.setValue(pointer.dead_zone_px)
            self.dwell.setChecked(pointer.dwell_enabled)
            self.dwell_ms.setValue(pointer.dwell_ms)
            self.dwell_radius.setValue(pointer.dwell_radius_px)
            self.scroll_speed.setValue(pointer.scroll_speed)
            self._pointer_labels()
            self._load_keyboard()
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
