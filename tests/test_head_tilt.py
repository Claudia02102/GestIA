"""P3-64: inclinar la cabeza abre y cierra las acciones rápidas sin interferir."""

import math
from dataclasses import replace

import pytest

from gestia.control import ControlMode, ControlStatus
from gestia.domain import DisplayPacket, FaceResult, PerformanceSnapshot, TrackingState
from gestia.features import roll_angle
from gestia.gestures import Action, GestureEvent, GestureFrame, GestureId
from gestia.head_tilt import HOLD_MS, HeadTiltDetector, TiltSettings
from tests.test_feedback_ui import FRAME, NEUTRAL, window  # noqa: F401  # «window» es fixture

TILT = math.radians(25)


def feed(detector: HeadTiltDetector, roll: float, start: int, duration: int, step: int = 33):
    fired = []
    for ts in range(start, start + duration, step):
        if detector.update(roll, ts):
            fired.append(ts)
    return fired


def test_roll_es_cero_con_la_cabeza_derecha_y_tiene_signo():
    assert roll_angle((0.4, 0.5), (0.6, 0.5)) == 0.0
    assert roll_angle((0.4, 0.5), (0.6, 0.6)) > 0 > roll_angle((0.4, 0.5), (0.6, 0.4))
    # Imagen espejada: mismo ángulo.
    assert roll_angle((0.6, 0.6), (0.4, 0.5)) == pytest.approx(roll_angle((0.4, 0.5), (0.6, 0.6)))


def test_inclinar_y_mantener_dispara_una_sola_vez():
    detector = HeadTiltDetector()
    assert feed(detector, 0.0, 0, 1000) == []
    fired = feed(detector, TILT, 1000, 2000)
    assert len(fired) == 1 and fired[0] - 1000 >= HOLD_MS


def test_una_inclinacion_breve_no_dispara():
    detector = HeadTiltDetector()
    feed(detector, 0.0, 0, 500)
    assert feed(detector, TILT, 500, HOLD_MS - 100) == []
    assert feed(detector, 0.0, 1000, 500) == []


def test_hay_que_volver_al_centro_para_repetir():
    detector = HeadTiltDetector()
    feed(detector, 0.0, 0, 300)
    assert len(feed(detector, TILT, 300, 1000)) == 1
    assert feed(detector, TILT * 0.8, 1300, 1000) == []  # sigue inclinada
    feed(detector, 0.0, 2300, 300)
    assert len(feed(detector, -TILT, 2600, 1000)) == 1  # hacia el otro hombro también


def test_inclinaciones_naturales_no_cuentan_y_la_postura_se_aprende():
    detector = HeadTiltDetector()
    # Persona que se sienta con la cabeza algo ladeada (7°): no dispara nada.
    assert feed(detector, math.radians(7), 0, 5000) == []
    assert not detector.forming


def test_mientras_se_inclina_fija_el_cursor():
    detector = HeadTiltDetector()
    feed(detector, 0.0, 0, 300)
    detector.update(math.radians(12), 400)
    assert detector.forming


def test_desactivado_no_hace_nada():
    detector = HeadTiltDetector(TiltSettings(enabled=False))
    feed(detector, 0.0, 0, 300)
    assert feed(detector, TILT, 300, 2000) == [] and not detector.forming


@pytest.mark.parametrize("raw", [{"enabled": "si"}, {"angle_deg": 5}, {"angle_deg": 50}, []])
def test_ajustes_invalidos(raw):
    with pytest.raises((ValueError, TypeError)):
        TiltSettings.from_dict(raw)


# --- En la ventana principal --------------------------------------------------------------


class FakeSystem:
    def __init__(self) -> None:
        self.calls = []

    def hotkey(self, *keys):
        self.calls.append(keys)

    def launch(self, target):
        self.calls.append(target)

    def close_window(self):
        self.calls.append("close")


def show(window, features, events=(), activations=None):  # noqa: F811
    window.clock.now += 0.033
    ts = int(window.clock.now * 1000)
    window._show_packet(
        DisplayPacket(
            FRAME,
            FaceResult(ts, ((0.5, 0.5, 0.0),) * 478, 5.0),
            TrackingState.TRACKING,
            PerformanceSnapshot(30, 30, 5, 0, 0),
            features,
            GestureFrame(activations or {}, tuple(events)),
        )
    )


def hold(window, roll, seconds):  # noqa: F811
    for _ in range(round(seconds / 0.033)):
        show(window, replace(NEUTRAL, roll=roll))


@pytest.fixture
def menu_window(window, monkeypatch):  # noqa: F811
    from gestia import ui

    monkeypatch.setattr(ui, "PynputSystemBackend", FakeSystem)
    executed = []

    def update(pointer, events, timestamp_ms, hold_position=False):
        executed.extend(events)
        return ControlStatus(ControlMode.NORMAL)

    monkeypatch.setattr(window.controller, "update", update)
    window.executed = executed
    return window


def test_inclinar_la_cabeza_abre_y_cierra_el_menu(menu_window):
    hold(menu_window, 0.0, 0.5)
    hold(menu_window, TILT, 1.0)
    assert menu_window.quick_menu_button.isChecked() and menu_window.quick_menu.isVisible()
    assert menu_window.status_indicator.flashing == "Acciones rápidas"
    hold(menu_window, 0.0, 0.5)
    hold(menu_window, -TILT, 1.0)
    assert not menu_window.quick_menu_button.isChecked()


def test_con_la_cabeza_inclinada_un_guino_no_hace_clic(menu_window):
    wink = GestureEvent(GestureId.WINK_LEFT, Action.LEFT_CLICK, 0)
    hold(menu_window, 0.0, 0.5)
    show(menu_window, replace(NEUTRAL, roll=TILT), [wink])
    assert menu_window.executed == []
    hold(menu_window, 0.0, 0.5)
    show(menu_window, NEUTRAL, [wink])
    assert menu_window.executed == [wink]


def test_en_pausa_inclinar_no_abre_el_menu(menu_window):
    menu_window.toggle_pause()
    hold(menu_window, 0.0, 0.5)
    hold(menu_window, TILT, 1.0)
    assert not menu_window.quick_menu_button.isChecked()
