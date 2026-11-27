"""Métricas de impacto y retroalimentación (P3-30)."""

import json
import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gestia.gestures import Action  # noqa: E402
from gestia.impact import (  # noqa: E402
    FEATURES,
    FEEDBACK_KEYS,
    OUTBOX_FILE,
    REPORT_KEYS,
    SETTINGS_FILE,
    USAGE_FILE,
    ImpactService,
    build_feedback,
)
from gestia.license import LicenseError, LicenseErrorKind  # noqa: E402
from gestia.ui_impact import FeedbackDialog, PrivacyDialog  # noqa: E402

TODAY = date(2026, 11, 26)


class FakeClient:
    def __init__(self, fail: LicenseError | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail = fail

    def rpc(self, function: str, body: dict) -> None:
        if self.fail is not None:
            raise self.fail
        self.calls.append((function, body))


class Clock:
    def __init__(self, day: date = TODAY) -> None:
        self.day = day

    def __call__(self) -> date:
        return self.day


def service(tmp_path, client=None, clock=None) -> ImpactService:
    return ImpactService(tmp_path, client or FakeClient(), clock or Clock(), version="0.7.0")


def use_app(impact: ImpactService) -> None:
    impact.tracker.record_session()
    impact.tracker.add_active_seconds(125, save=True)
    impact.tracker.record_action(Action.LEFT_CLICK)
    impact.tracker.record_action(Action.LEFT_CLICK)
    impact.tracker.record_action(Action.SCROLL)
    impact.tracker.record_feature("teclado")
    impact.tracker.record_feature("no_existe")


# --- Prueba de aceptación 1: sin consentimiento no se registra nada -------------------------


def test_without_consent_nothing_is_recorded(tmp_path) -> None:
    client = FakeClient()
    clock = Clock()
    impact = service(tmp_path, client, clock)
    assert not impact.asked and not impact.enabled
    use_app(impact)
    clock.day += timedelta(days=1)
    assert impact.queue_finished_days() == 0
    assert impact.flush() == (0, 0)
    assert client.calls == []
    assert not (tmp_path / USAGE_FILE).exists()
    assert not (tmp_path / OUTBOX_FILE).exists()


def test_refusing_consent_also_records_nothing(tmp_path) -> None:
    impact = service(tmp_path)
    impact.set_consent(False)
    use_app(impact)
    assert impact.asked and not impact.enabled
    assert not (tmp_path / USAGE_FILE).exists()
    saved = json.loads((tmp_path / SETTINGS_FILE).read_text(encoding="utf-8"))
    assert saved == {"consent": False, "install_id": None}


# --- Prueba de aceptación 2: el reporte no contiene datos personales ni imágenes -------------


def test_report_contains_only_anonymous_counts(tmp_path) -> None:
    client = FakeClient()
    clock = Clock()
    impact = service(tmp_path, client, clock)
    impact.set_consent(True)
    use_app(impact)
    clock.day += timedelta(days=1)
    assert impact.queue_finished_days() == 1
    assert impact.flush() == (1, 0)
    function, body = client.calls[0]
    report = body["p_report"]
    assert function == "submit_usage_report"
    assert set(report) == REPORT_KEYS
    assert report["day"] == TODAY.isoformat()
    assert report["sessions"] == 1 and report["active_minutes"] == 2
    assert report["actions"] == {"left_click": 2, "scroll": 1}
    assert report["features"] == {name: int(name == "teclado") for name in FEATURES}
    assert report["install_id"] == impact.settings.install_id
    text = json.dumps(report).lower()
    for forbidden in ("@", "nombre", "perfil", "landmark", "imagen", "frame", "\\\\", "/"):
        assert forbidden not in text


def test_profile_and_device_data_never_reach_the_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("USERNAME", "ana.perez")
    monkeypatch.setenv("COMPUTERNAME", "PC-DE-ANA")
    impact = service(tmp_path)
    impact.set_consent(True)
    use_app(impact)
    text = json.dumps(impact.preview())
    assert "ana" not in text.lower() and "PC-DE-ANA" not in text
    assert tmp_path.name not in text


def test_install_id_is_random_and_removed_with_consent(tmp_path) -> None:
    impact = service(tmp_path)
    impact.set_consent(True)
    first = impact.settings.install_id
    assert first and len(first) == 36
    impact.set_consent(False)
    assert impact.settings.install_id is None
    impact.set_consent(True)
    assert impact.settings.install_id != first


def test_withdrawing_consent_deletes_pending_usage(tmp_path) -> None:
    clock = Clock()
    impact = service(tmp_path, FakeClient(fail=LicenseError(LicenseErrorKind.NETWORK)), clock)
    impact.set_consent(True)
    use_app(impact)
    impact.submit_feedback("sugerencia", "Más gestos, por favor")
    clock.day += timedelta(days=1)
    impact.queue_finished_days()
    assert {item["kind"] for item in impact.outbox.pending()} == {"usage", "feedback"}
    impact.set_consent(False)
    assert [item["kind"] for item in impact.outbox.pending()] == ["feedback"]
    assert not (tmp_path / USAGE_FILE).exists()


def test_counters_survive_restart_and_today_is_not_sent(tmp_path) -> None:
    clock = Clock()
    impact = service(tmp_path, clock=clock)
    impact.set_consent(True)
    use_app(impact)
    reopened = service(tmp_path, clock=clock)
    assert reopened.enabled
    assert reopened.queue_finished_days() == 0  # el día aún no terminó
    assert reopened.preview()["actions"] == {"left_click": 2, "scroll": 1}


# --- Prueba de aceptación 3: un comentario queda registrado ----------------------------------


def test_feedback_is_sent_without_metrics_consent(tmp_path) -> None:
    client = FakeClient()
    impact = service(tmp_path, client)
    item = impact.submit_feedback("problema", "  El guiño   no hace clic  ", "ana@correo.pe")
    assert impact.outbox.has(item)
    assert impact.flush() == (1, 0)
    function, body = client.calls[0]
    assert function == "submit_feedback"
    assert set(body["p_feedback"]) == FEEDBACK_KEYS
    assert body["p_feedback"]["message"] == "El guiño no hace clic"
    assert body["p_feedback"]["contact"] == "ana@correo.pe"


def test_feedback_waits_offline_and_is_sent_later(tmp_path) -> None:
    offline = service(tmp_path, FakeClient(fail=LicenseError(LicenseErrorKind.NETWORK)))
    offline.submit_feedback("agradecimiento", "Me ayudó a escribir sola")
    assert offline.flush() == (0, 1)
    online_client = FakeClient()
    online = service(tmp_path, online_client)
    assert online.flush() == (1, 0)
    assert online_client.calls[0][1]["p_feedback"]["message"] == "Me ayudó a escribir sola"
    assert not (tmp_path / OUTBOX_FILE).exists()


def test_rejected_item_does_not_block_the_outbox(tmp_path) -> None:
    impact = service(tmp_path, FakeClient(fail=LicenseError(LicenseErrorKind.SERVER, "HTTP 422")))
    impact.submit_feedback("sugerencia", "uno")
    assert impact.flush() == (0, 0)


def test_missing_server_function_keeps_items(tmp_path) -> None:
    # Si la migración aún no está aplicada, Supabase responde 404: se reintenta más tarde.
    impact = service(tmp_path, FakeClient(fail=LicenseError(LicenseErrorKind.SERVER, "HTTP 404")))
    impact.submit_feedback("sugerencia", "Un comentario")
    assert impact.flush() == (0, 1)


@pytest.mark.parametrize(
    ("category", "message", "contact"),
    [
        ("otro", "Hola equipo", ""),
        ("sugerencia", "  ", ""),
        ("sugerencia", "x" * 1001, ""),
        ("sugerencia", "Hola equipo", "no-es-un-correo"),
    ],
)
def test_invalid_feedback_is_rejected(category, message, contact) -> None:
    with pytest.raises(ValueError):
        build_feedback(category, message, contact, "0.7.0")


def test_corrupt_files_are_ignored(tmp_path) -> None:
    (tmp_path / SETTINGS_FILE).write_text("{roto", encoding="utf-8")
    (tmp_path / OUTBOX_FILE).write_text('[{"kind": "otro"}]', encoding="utf-8")
    impact = service(tmp_path)
    assert not impact.asked and impact.outbox.pending() == []


# --- Ventanas ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_first_time_dialog_records_the_choice(qt_app, tmp_path) -> None:
    impact = service(tmp_path)
    dialog = PrivacyDialog(impact, first_time=True)
    dialog.preview_button.setChecked(True)
    assert '"install_id"' in dialog.preview.toPlainText()
    dialog._decide(True)
    assert impact.enabled


def test_settings_dialog_can_withdraw_consent(qt_app, tmp_path) -> None:
    impact = service(tmp_path)
    impact.set_consent(True)
    dialog = PrivacyDialog(impact)
    dialog.consent_check.setChecked(False)
    assert not impact.enabled and "Desactivado" in dialog.status.text()


def test_feedback_dialog_validates_and_queues(qt_app, tmp_path) -> None:
    impact = service(tmp_path)
    dialog = FeedbackDialog(impact)
    dialog.submit()
    assert "Escribe" in dialog.error.text() and dialog.item_id is None
    dialog.category_buttons["problema"].setChecked(True)
    dialog.message.setPlainText("La cámara tarda en abrir")
    dialog.submit()
    assert dialog.item_id is not None and impact.outbox.has(dialog.item_id)
    assert impact.outbox.pending()[0]["payload"]["category"] == "problema"


def test_every_action_is_accepted_by_the_server() -> None:
    from gestia.impact import _ACTION_NAMES

    # Si falla: sume la acción nueva en impact.py y en submit_usage_report (migración P3-30).
    assert {str(action) for action in Action} == _ACTION_NAMES
