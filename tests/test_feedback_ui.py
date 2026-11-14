"""P3-44 y P3-45 en la ventana principal: cada prueba sigue un criterio de aceptación."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gestia.calibration import AxisRange, Calibration, HeadCalibration  # noqa: E402
from gestia.config import AppConfig  # noqa: E402
from gestia.domain import (  # noqa: E402
    DisplayPacket,
    FaceResult,
    PerformanceSnapshot,
    TrackingState,
)
from gestia.features import FaceFeatures  # noqa: E402
from gestia.feedback import Sound, StatusKind  # noqa: E402
from gestia.gestures import Action, GestureEvent, GestureFrame, GestureId  # noqa: E402

NEUTRAL = FaceFeatures(0.5, 0.55, 0.3, 0.3, 0.05, 0.2, 0.4)
FRAME = np.zeros((48, 64, 3), np.uint8)


class FakeSound:
    def __init__(self) -> None:
        self.played: list[Sound] = []

    def play(self, sound: Sound) -> None:
        self.played.append(sound)


class FakeMouse:
    position = None

    def move(self, x, y):
        self.position = (x, y)

    def press(self, button):
        pass

    def release(self, button):
        pass

    def click(self, button, count=1):
        pass

    def scroll(self, dx, dy):
        pass

    def escape(self):
        pass


class FakeWorker:
    def apply_profile(self, profile):
        pass

    def request_stop(self):
        pass


class FakeThread:
    """Simula la cámara en marcha sin abrir ninguna."""

    def wait(self, timeout=0):
        return True

    def deleteLater(self):  # noqa: N802
        pass


class Clock:
    now = 1000.0

    def monotonic(self) -> float:
        return self.now


@pytest.fixture
def window(tmp_path, monkeypatch):
    from gestia import ui

    app = QApplication.instance() or QApplication([])
    clock = Clock()
    monkeypatch.setattr(ui, "PynputBackend", FakeMouse)
    monkeypatch.setattr(ui.time, "monotonic", clock.monotonic)
    win = ui.MainWindow(AppConfig(), tmp_path)
    win.feedback.backend = sound = FakeSound()
    win.wizard_offered = True
    win.profile.calibration = Calibration(
        HeadCalibration(AxisRange(0.5, 0.6, 0.4), AxisRange(0.55, 0.48, 0.62))
    )
    win.worker, win.thread = FakeWorker(), FakeThread()
    win._create_controller()
    win.clock, win.sound = clock, sound
    yield win
    win.worker = win.thread = None
    win.hotkeys.stop()
    win.close()
    app.processEvents()


def packet(window, events=(), state=TrackingState.TRACKING):
    window.clock.now += 0.033
    timestamp = int(window.clock.now * 1000)
    features = NEUTRAL if state is TrackingState.TRACKING else None
    landmarks = ((0.5, 0.5, 0.0),) * 478 if features else ()
    window._set_state(state)
    window._show_packet(
        DisplayPacket(
            FRAME, FaceResult(timestamp, landmarks, 5.0), state,
            PerformanceSnapshot(30, 30, 5, 0, 0), features, GestureFrame({}, tuple(events)),
        )
    )


def event(action: Action, gesture=GestureId.WINK_LEFT) -> GestureEvent:
    return GestureEvent(gesture, action, 0)


# --- P3-44: retroalimentación e indicador de estado -----------------------------------------


def test_un_gesto_da_senal_visual_y_sonora(window) -> None:
    packet(window)
    packet(window, [event(Action.LEFT_CLICK)])
    assert window.status_indicator.flashing == "Clic izquierdo"
    assert window.status_indicator.isVisible()
    assert window.sound.played == [Sound.GESTURE]


def test_el_indicador_muestra_activo_en_pausa_y_sin_rostro(window) -> None:
    packet(window)
    assert window.status_indicator.status is StatusKind.ACTIVE
    window.toggle_pause()
    assert window.status_indicator.status is StatusKind.PAUSED
    window.toggle_pause()
    packet(window, state=TrackingState.LOST)
    assert window.status_indicator.status is StatusKind.NO_FACE
    packet(window)
    assert window.status_indicator.status is StatusKind.ACTIVE


def test_sin_sonido_la_senal_visual_se_mantiene(window) -> None:
    window.panel.sound_check.setChecked(False)
    assert not window.store.load(window.profile.id).feedback.sound
    packet(window)
    packet(window, [event(Action.RIGHT_CLICK, GestureId.WINK_RIGHT)])
    window.toggle_pause()
    assert window.sound.played == []
    assert window.status_indicator.flashing == "Clic derecho"
    assert window.pause_indicator.isVisible()


def test_el_destello_vuelve_al_estado_al_terminar(window) -> None:
    packet(window, [event(Action.LEFT_CLICK)])
    window.status_indicator._end_flash()
    assert window.status_indicator.flashing == ""
    assert "Activo" in window.status_indicator.label.text()


def test_los_gestos_ignorados_en_pausa_no_dan_senal_de_gesto(window) -> None:
    packet(window)
    window.toggle_pause()
    window.sound.played.clear()
    packet(window, [event(Action.LEFT_CLICK)])
    assert window.status_indicator.flashing == ""
    assert window.sound.played == []


def test_el_indicador_se_puede_ocultar_y_no_roba_el_foco(window) -> None:
    flags = window.status_indicator.windowFlags()
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    window.panel.indicator_check.setChecked(False)
    assert not window.status_indicator.isVisible()


# --- P3-45: recordatorios de descanso --------------------------------------------------------


def use_for(window, seconds: float) -> None:
    for _ in range(int(seconds)):
        window.clock.now += 1
        window._tick_breaks()


def test_el_aviso_aparece_al_cumplirse_el_intervalo(window) -> None:
    window.panel.break_minutes.setValue(1)
    packet(window)
    use_for(window, 30)
    assert not window.break_reminder.isVisible()
    use_for(window, 31)
    assert window.break_reminder.isVisible()
    assert "1 min" in window.break_reminder.message.text()
    assert Sound.REMINDER in window.sound.played


def test_recordatorios_desactivados_no_aparecen(window) -> None:
    window.panel.break_minutes.setValue(1)
    window.panel.breaks_check.setChecked(False)
    packet(window)
    use_for(window, 600)
    assert not window.break_reminder.isVisible()


def test_el_aviso_no_interrumpe_la_tarea(window) -> None:
    window.panel.break_minutes.setValue(1)
    packet(window)
    use_for(window, 61)
    reminder = window.break_reminder
    assert reminder.isVisible()
    assert reminder.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert reminder.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert not window.controller.paused  # el control sigue funcionando
    packet(window, [event(Action.LEFT_CLICK)])
    assert window.status_indicator.flashing == "Clic izquierdo"


def test_en_pausa_no_cuenta_el_tiempo_de_uso(window) -> None:
    window.panel.break_minutes.setValue(1)
    packet(window)
    window.toggle_pause()
    use_for(window, 90)
    assert not window.break_reminder.isVisible()


def test_boton_probar_muestra_el_aviso(window) -> None:
    window.panel.reminder_test_requested.emit()
    assert window.break_reminder.isVisible()
