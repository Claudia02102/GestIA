"""P3-62: inicio de sesión, activación del equipo y validación cada 30 días (sin red real)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from gestia.license import (
    VALID_DAYS,
    LicenseError,
    LicenseErrorKind,
    LicenseManager,
    LicenseState,
    LicenseStatus,
    LicenseStore,
    PlainProtector,
    SupabaseClient,
    UrllibTransport,
    device_hash,
    license_required,
)

START = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


class FakeSupabase:
    """Responde como GoTrue y PostgREST; ``offline`` simula no tener internet."""

    def __init__(self) -> None:
        self.users = {"ana@example.com": "Clave1234"}
        self.purchased = {"ana@example.com"}
        self.devices: dict[str, set[str]] = {}
        self.tokens: dict[str, str] = {}
        self.offline = False
        self.calls: list[tuple[str, dict]] = []

    def _session(self, email: str) -> tuple[int, dict]:
        refresh = f"r-{len(self.tokens)}"
        self.tokens[refresh] = email
        return 200, {
            "access_token": f"a-{email}",
            "refresh_token": refresh,
            "user": {"email": email},
        }

    def post(self, url: str, headers: dict[str, str], body: dict) -> tuple[int, object]:
        self.calls.append((url, headers))
        if self.offline:
            raise OSError("sin conexión")
        assert headers["apikey"].startswith("sb_publishable_")
        if url.endswith("grant_type=password"):
            if self.users.get(body["email"]) != body["password"]:
                return 400, {"error_code": "invalid_credentials"}
            return self._session(body["email"])
        if url.endswith("grant_type=refresh_token"):
            email = self.tokens.pop(body["refresh_token"], None)
            if email is None:
                return 400, {"error_code": "refresh_token_not_found"}
            return self._session(email)
        if url.endswith("/rpc/activate_device"):
            email = headers["Authorization"].removeprefix("Bearer a-")
            if email not in self.purchased:
                return 200, {"licensed": False}
            devices = self.devices.setdefault(email, set())
            if body["p_device_hash"] not in devices and len(devices) >= 3:
                return 400, {"message": "La licencia ya está activada en 3 equipos"}
            devices.add(body["p_device_hash"])
            return 200, {"licensed": True, "valid_days": 30}
        return 404, {}


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def server() -> FakeSupabase:
    return FakeSupabase()


@pytest.fixture
def clock() -> Clock:
    return Clock()


def make_manager(server: FakeSupabase, clock: Clock, path: Path, device: str = "a" * 64):
    store = LicenseStore(path / "licencia.bin", PlainProtector())
    return LicenseManager(SupabaseClient(server), store, device, "PC de prueba", clock)


def test_primera_vez_pide_iniciar_sesion(server, clock, tmp_path):
    assert make_manager(server, clock, tmp_path).status() is LicenseStatus.LOGIN


def test_login_activa_el_equipo_y_guarda_sin_contrasena(server, clock, tmp_path):
    manager = make_manager(server, clock, tmp_path)
    state = manager.login("  Ana@Example.com ", "Clave1234")
    assert state.email == "ana@example.com"
    assert manager.status() is LicenseStatus.VALID
    assert server.devices["ana@example.com"] == {"a" * 64}
    saved = (tmp_path / "licencia.bin").read_bytes()
    assert b"Clave1234" not in PlainProtector().unprotect(saved)


def test_credenciales_incorrectas(server, clock, tmp_path):
    with pytest.raises(LicenseError) as error:
        make_manager(server, clock, tmp_path).login("ana@example.com", "otra")
    assert error.value.kind is LicenseErrorKind.CREDENTIALS
    assert not (tmp_path / "licencia.bin").exists()


def test_cuenta_sin_compra_no_entra(server, clock, tmp_path):
    server.users["luis@example.com"] = "Clave1234"
    with pytest.raises(LicenseError) as error:
        make_manager(server, clock, tmp_path).login("luis@example.com", "Clave1234")
    assert error.value.kind is LicenseErrorKind.NO_PURCHASE
    assert "Mi cuenta" in error.value.message


def test_maximo_tres_equipos(server, clock, tmp_path):
    for index, letter in enumerate("abc"):
        folder = tmp_path / str(index)
        make_manager(server, clock, folder, letter * 64).login("ana@example.com", "Clave1234")
    with pytest.raises(LicenseError) as error:
        make_manager(server, clock, tmp_path / "d", "d" * 64).login("ana@example.com", "Clave1234")
    assert error.value.kind is LicenseErrorKind.DEVICE_LIMIT


def test_funciona_sin_internet_durante_30_dias(server, clock, tmp_path):
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    server.offline = True
    clock.now = START + timedelta(days=VALID_DAYS - 1)
    calls = len(server.calls)
    manager = make_manager(server, clock, tmp_path)  # se abre de nuevo la app
    assert manager.status() is LicenseStatus.VALID
    assert len(server.calls) == calls  # sin ninguna llamada a la red


def test_a_los_30_dias_pide_validar_y_sin_red_no_borra_la_sesion(server, clock, tmp_path):
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    clock.now = START + timedelta(days=VALID_DAYS)
    server.offline = True
    manager = make_manager(server, clock, tmp_path)
    assert manager.status() is LicenseStatus.REVALIDATE
    with pytest.raises(LicenseError) as error:
        manager.revalidate()
    assert error.value.kind is LicenseErrorKind.NETWORK
    assert manager.state is not None  # con internet podrá validar sin la contraseña

    server.offline = False
    manager.revalidate()
    assert manager.status() is LicenseStatus.VALID
    assert manager.state.validated_at == clock.now


def test_sesion_revocada_pide_iniciar_sesion(server, clock, tmp_path):
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    server.tokens.clear()
    clock.now = START + timedelta(days=VALID_DAYS + 3)
    manager = make_manager(server, clock, tmp_path)
    with pytest.raises(LicenseError) as error:
        manager.revalidate()
    assert error.value.kind is LicenseErrorKind.SESSION_EXPIRED
    assert manager.status() is LicenseStatus.LOGIN


def test_licencia_retirada_al_revalidar(server, clock, tmp_path):
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    server.purchased.clear()
    clock.now = START + timedelta(days=VALID_DAYS)
    manager = make_manager(server, clock, tmp_path)
    with pytest.raises(LicenseError):
        manager.revalidate()
    assert manager.status() is LicenseStatus.LOGIN


def test_renueva_sola_en_los_ultimos_dias(server, clock, tmp_path):
    manager = make_manager(server, clock, tmp_path)
    manager.login("ana@example.com", "Clave1234")
    clock.now = START + timedelta(days=10)
    assert not manager.try_renew()  # aún falta mucho: no usa la red
    clock.now = START + timedelta(days=25)
    assert manager.try_renew()
    assert manager.state.validated_at == clock.now
    server.offline = True
    clock.now = START + timedelta(days=50)
    assert not manager.try_renew()


def test_reloj_atrasado_obliga_a_validar(server, clock, tmp_path):
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    clock.now = START - timedelta(days=2)
    assert make_manager(server, clock, tmp_path).status() is LicenseStatus.REVALIDATE


@pytest.mark.parametrize("content", [b"", b"basura", b"bm8gZXMganNvbg=="])
def test_archivo_danado_pide_iniciar_sesion(server, clock, tmp_path, content):
    (tmp_path / "licencia.bin").write_bytes(content)
    assert make_manager(server, clock, tmp_path).status() is LicenseStatus.LOGIN


def test_estado_rechaza_fechas_sin_zona():
    with pytest.raises(ValueError):
        LicenseState.from_dict(
            {"email": "a@b.c", "refresh_token": "r", "validated_at": "2026-11-23T12:00:00"}
        )


def test_hash_del_equipo_no_revela_el_identificador():
    value = device_hash("1234-ABCD")
    assert len(value) == 64 and "1234" not in value
    assert value == device_hash("1234-ABCD") != device_hash("otro")


def test_solo_la_version_instalada_exige_licencia():
    assert license_required(True, {})
    assert not license_required(False, {})
    assert license_required(False, {"GESTIA_REQUIRE_LICENSE": "1"})


def test_transporte_rechaza_http_sin_cifrar():
    with pytest.raises(ValueError):
        UrllibTransport().post("http://example.com", {}, {})


def test_la_app_no_contiene_la_clave_service_role():
    source = (Path(__file__).parents[1] / "src" / "gestia" / "license.py").read_text("utf-8")
    assert "sb_secret_" not in source
    assert "sb_publishable_" in source  # solo la clave publicable
