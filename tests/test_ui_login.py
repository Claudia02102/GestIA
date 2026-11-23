"""P3-62: ventana de inicio de sesión de la app (con el servidor simulado de test_license)."""

import os
from datetime import timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from gestia.license import VALID_DAYS, LicenseStatus  # noqa: E402
from gestia.ui_login import LoginDialog, ensure_license  # noqa: E402
from tests.test_license import START, Clock, FakeSupabase, make_manager  # noqa: E402


@pytest.fixture(autouse=True)
def app():
    return QApplication.instance() or QApplication([])


def test_inicio_de_sesion_correcto_cierra_la_ventana(tmp_path):
    manager = make_manager(FakeSupabase(), Clock(), tmp_path)
    dialog = LoginDialog(manager)
    dialog.email.setText("ana@example.com")
    dialog.password.setText("Clave1234")
    dialog.submit()
    assert dialog.result() == LoginDialog.DialogCode.Accepted
    assert manager.status() is LicenseStatus.VALID
    assert dialog.password.text() == ""


def test_error_en_espanol_y_la_ventana_sigue_abierta(tmp_path):
    dialog = LoginDialog(make_manager(FakeSupabase(), Clock(), tmp_path))
    dialog.email.setText("ana@example.com")
    dialog.password.setText("mala")
    dialog.submit()
    assert dialog.result() != LoginDialog.DialogCode.Accepted
    assert "no son correctos" in dialog.error.text()


def test_sin_internet_a_los_30_dias_ofrece_validar_sin_contrasena(tmp_path):
    server, clock = FakeSupabase(), Clock()
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    clock.now = START + timedelta(days=VALID_DAYS + 1)
    server.offline = True
    dialog = LoginDialog(make_manager(server, clock, tmp_path))
    assert dialog.stack.currentIndex() == 1  # pantalla «Validar ahora»
    dialog.revalidate()
    assert "internet" in dialog.error.text()
    server.offline = False
    dialog.revalidate()
    assert dialog.result() == LoginDialog.DialogCode.Accepted


def test_licencia_vigente_abre_sin_ventana(tmp_path):
    server, clock = FakeSupabase(), Clock()
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    server.offline = True
    assert ensure_license(make_manager(server, clock, tmp_path))
