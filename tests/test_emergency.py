"""P3-66: gesto de auxilio con confirmación y mensaje por WhatsApp."""

from dataclasses import replace

import pytest

from gestia.emergency import (
    CONFIRM_TIMEOUT_MS,
    ConfirmOutcome,
    EmergencyConfirmation,
    EmergencySettings,
    EmergencyTrigger,
    SendResult,
    normalize_phone,
    open_chat,
    press_send,
    web_uri,
    whatsapp_uri,
)
from gestia.gestures import Action, GestureEvent, GestureId, default_gesture_settings
from tests.test_feedback_ui import NEUTRAL, window  # noqa: F401  # fixture
from tests.test_head_tilt import menu_window, show  # noqa: F401  # fixture

READY = EmergencySettings(enabled=True, phone="987 654 321", contact_name="Mamá")
SETTINGS = default_gesture_settings()
BROW = GestureId.BROW_RAISE
RECENTER = GestureEvent(BROW, Action.RECALIBRATE, 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("987 654 321", "51987654321"),
        ("+51 987-654-321", "51987654321"),
        ("0034 612 345 678", "34612345678"),
        ("12345", ""),
        ("", ""),
    ],
)
def test_normaliza_el_numero(text, expected):
    assert normalize_phone(text) == expected


def test_direcciones_de_whatsapp_codifican_el_mensaje():
    assert whatsapp_uri("51987654321", "Necesito ayuda & ven") == (
        "whatsapp://send?phone=51987654321&text=Necesito+ayuda+%26+ven"
    )
    assert web_uri("51987654321", "Hola").startswith("https://wa.me/51987654321?text=Hola")


@pytest.mark.parametrize(
    "raw",
    [{"phone": "123"}, {"message": ""}, {"message": "x" * 301}, {"hold_ms": 500}, {"enabled": 1}],
)
def test_ajustes_invalidos(raw):
    with pytest.raises(ValueError):
        EmergencySettings.from_dict(raw)


def test_sin_numero_no_esta_listo():
    assert not EmergencySettings(enabled=True).ready
    assert not replace(READY, enabled=False).ready and READY.ready


# --- Reconocer el gesto ----------------------------------------------------------------------


def run(trigger, value, start, duration, events_at=None, settings=READY, step=33):
    passed, fired, sent = [], [], False
    for ts in range(start, start + duration, step):
        # El motor de gestos emite el recentrado una sola vez por gesto sostenido.
        events = [] if sent or events_at is None or ts < events_at else [RECENTER]
        sent = sent or bool(events)
        out, fire = trigger.update({BROW: value}, events, SETTINGS, settings, ts)
        passed.extend(out)
        if fire:
            fired.append(ts)
    return passed, fired


def test_cejas_3_segundos_disparan_el_auxilio_y_no_recentran():
    trigger = EmergencyTrigger()
    passed, fired = run(trigger, 1.0, 0, 3500, events_at=1000)
    assert passed == [] and len(fired) == 1 and 3000 <= fired[0] < 3100
    passed, _ = run(trigger, 0.0, 3500, 300)
    assert passed == []  # el recentrado retenido se descartó


def test_soltar_antes_recentra_como_siempre():
    trigger = EmergencyTrigger()
    passed, fired = run(trigger, 1.0, 0, 1500, events_at=1000)
    assert passed == [] and fired == []
    passed, fired = run(trigger, 0.0, 1500, 100)
    assert [e.action for e in passed] == [Action.RECALIBRATE] and fired == []


def test_desactivado_no_retiene_nada():
    trigger = EmergencyTrigger()
    passed, fired = run(trigger, 1.0, 0, 4000, events_at=1000, settings=EmergencySettings())
    assert [e.action for e in passed] == [Action.RECALIBRATE] and fired == []


def test_otros_gestos_pasan_mientras_se_mantienen_las_cejas():
    trigger = EmergencyTrigger()
    wink = GestureEvent(GestureId.WINK_LEFT, Action.LEFT_CLICK, 0)
    out, _ = trigger.update({BROW: 1.0}, [wink], SETTINGS, READY, 0)
    assert out == [wink]


# --- Confirmación ----------------------------------------------------------------------------


def test_abrir_la_boca_confirma():
    confirmation = EmergencyConfirmation(0)
    mouth = GestureEvent(GestureId.MOUTH_OPEN, Action.DOUBLE_CLICK, 0)
    assert confirmation.feed([], 1000) is ConfirmOutcome.WAITING
    assert confirmation.feed([mouth], 2000) is ConfirmOutcome.CONFIRMED


def test_otro_gesto_no_confirma_y_a_los_10_s_se_cancela():
    confirmation = EmergencyConfirmation(0)
    wink = GestureEvent(GestureId.WINK_LEFT, Action.LEFT_CLICK, 0)
    assert confirmation.feed([wink], 5000) is ConfirmOutcome.WAITING
    assert confirmation.seconds_left(5000) == 5
    assert confirmation.feed([], CONFIRM_TIMEOUT_MS) is ConfirmOutcome.TIMED_OUT
    confirmation.confirm()
    assert confirmation.outcome is ConfirmOutcome.TIMED_OUT


def test_cancelar_con_el_boton():
    confirmation = EmergencyConfirmation(0)
    confirmation.cancel()
    assert confirmation.feed([], 100) is ConfirmOutcome.CANCELLED


# --- Envío -----------------------------------------------------------------------------------


class FakeMessenger:
    def __init__(self, app=True, web=True, title="WhatsApp") -> None:
        self.app, self.web, self.title = app, web, title
        self.opened, self.enters = [], 0

    def open_uri(self, uri):
        ok = self.app if uri.startswith("whatsapp:") else self.web
        if ok:
            self.opened.append(uri)
        return ok

    def foreground_title(self):
        return self.title

    def press_enter(self):
        self.enters += 1


def test_abre_whatsapp_desktop_con_el_mensaje():
    messenger = FakeMessenger()
    assert open_chat(messenger, READY) is SendResult.OPENED_APP
    assert messenger.opened[0].startswith("whatsapp://send?phone=51987654321&text=Necesito")


def test_sin_whatsapp_desktop_usa_whatsapp_web():
    messenger = FakeMessenger(app=False)
    assert open_chat(messenger, READY) is SendResult.OPENED_WEB
    assert messenger.opened == [web_uri("51987654321", READY.message)]


def test_enter_solo_si_whatsapp_esta_delante():
    assert not press_send(FakeMessenger(title="Documento - Bloc de notas"))
    messenger = FakeMessenger(title="WhatsApp")
    assert press_send(messenger) and messenger.enters == 1


# --- En la ventana principal -------------------------------------------------------------


@pytest.fixture
def sos_window(menu_window, monkeypatch):  # noqa: F811
    from gestia import ui

    menu_window.profile.emergency = replace(READY)
    menu_window.profile.calibration.gestures[BROW] = ui_range()
    menu_window.panel.set_profile(menu_window.profile)
    menu_window.messenger = FakeMessenger()
    singles = []
    monkeypatch.setattr(ui.QTimer, "singleShot", lambda ms, fn: singles.append(fn))
    menu_window.singles = singles
    return menu_window


def ui_range():
    from gestia.gestures import SignalRange

    return SignalRange(0.2, 0.3)


def brows(window, seconds, events=()):  # noqa: F811
    for _ in range(round(seconds / 0.033)):
        show(window, NEUTRAL, events, {BROW: 1.0})


def test_flujo_completo_con_confirmacion_por_la_boca(sos_window):
    brows(sos_window, 3.2)
    assert sos_window.emergency is not None and sos_window.emergency_window.isVisible()
    assert "Mamá" in sos_window.emergency_window.title.text()
    # Un guiño mientras se confirma no hace clic.
    show(sos_window, NEUTRAL, [GestureEvent(GestureId.WINK_LEFT, Action.LEFT_CLICK, 0)])
    assert sos_window.executed == []
    show(sos_window, NEUTRAL, [GestureEvent(GestureId.MOUTH_OPEN, Action.DOUBLE_CLICK, 0)])
    assert sos_window.emergency is None
    assert sos_window.messenger.opened[0].startswith("whatsapp://send?phone=51987654321")
    sos_window.singles.pop(0)()  # pasan los 4 s: WhatsApp está delante y se pulsa Enter
    assert sos_window.messenger.enters == 1
    assert sos_window.emergency_window.title.text() == "Mensaje enviado"


def test_sin_confirmar_se_cancela_a_los_10_segundos(sos_window):
    brows(sos_window, 3.2)
    sos_window.clock.now += 10.5
    sos_window._tick_emergency()
    assert sos_window.emergency is None and sos_window.messenger.opened == []
    assert sos_window.emergency_window.title.text() == "Auxilio cancelado"


def test_boton_cancelar(sos_window):
    brows(sos_window, 3.2)
    sos_window.emergency_window.cancel_button.click()
    assert sos_window.emergency is None and sos_window.messenger.opened == []


def test_funciona_en_pausa(sos_window):
    sos_window.toggle_pause()
    brows(sos_window, 3.2)
    sos_window.emergency_window.confirm_button.click()
    assert sos_window.messenger.opened


def test_la_prueba_no_envia_nada(sos_window):
    sos_window.panel.emergency_test_requested.emit()
    sos_window.emergency_window.confirm_button.click()
    assert sos_window.messenger.opened == []
    assert sos_window.emergency_window.title.text() == "Prueba correcta"


def test_ajustes_desde_el_panel_se_guardan(sos_window):
    panel = sos_window.panel
    panel.emergency_phone.setText("912 345 678")
    panel.emergency_phone.editingFinished.emit()
    saved = sos_window.store.load(sos_window.profile.id).emergency
    assert saved.phone == "912 345 678"
    panel.emergency_phone.setText("12")
    panel.emergency_phone.editingFinished.emit()
    assert sos_window.store.load(sos_window.profile.id).emergency.phone == "912 345 678"
    assert "no es válido" in panel.emergency_status.text()
