"""P3-27: la imagen de la cámara no se guarda ni se envía, y la app funciona sin internet.

Estas pruebas protegen la promesa de privacidad ante cambios futuros: si alguien agrega código
que guarde fotos o video, o que se conecte a internet desde otro módulo, el CI falla.
"""

from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

import pytest

from gestia.license import RENEW_BEFORE_DAYS, VALID_DAYS, LicenseStatus
from gestia.persistence import environment_metadata
from gestia.vision import FaceLandmarker, VisionError
from tests.test_license import START, Clock, FakeSupabase, make_manager

SRC = Path(__file__).resolve().parents[1] / "src" / "gestia"

# Único módulo que puede conectarse a internet: valida la licencia (correo, contraseña y
# un identificador cifrado del equipo). Los enlaces que abre la persona (YouTube, WhatsApp,
# la landing) los abre el navegador del sistema, no la app.
NETWORK_ALLOWED = {"license.py"}
NETWORK_MODULES = {
    "aiohttp",
    "ftplib",
    "http.client",
    "httpx",
    "PySide6.QtNetwork",
    "requests",
    "smtplib",
    "socket",
    "urllib.request",
    "urllib3",
    "websocket",
}
# Funciones que guardan o codifican imágenes y video.
IMAGE_WRITERS = {"imwrite", "imencode", "VideoWriter", "VideoWriter_fourcc", "grabWindow"}
# Lo único que la app puede mandar a Supabase.
ALLOWED_FIELDS = {"email", "password", "refresh_token", "p_device_hash", "p_label"}


def source_files() -> list[Path]:
    files = sorted(SRC.glob("*.py"))
    assert files, f"no se encontró el código en {SRC}"
    return files


def imported_modules(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def uses_module(imported: set[str], module: str) -> bool:
    return any(name == module or name.startswith(module + ".") for name in imported)


@pytest.mark.parametrize("path", source_files(), ids=lambda p: p.name)
def test_solo_la_licencia_se_conecta_a_internet(path: Path) -> None:
    if path.name in NETWORK_ALLOWED:
        return
    imported = imported_modules(ast.parse(path.read_text(encoding="utf-8")))
    network = sorted(m for m in NETWORK_MODULES if uses_module(imported, m))
    assert not network, f"{path.name} importa librerías de red: {network}"


@pytest.mark.parametrize("path", source_files(), ids=lambda p: p.name)
def test_ningun_modulo_guarda_imagenes_ni_video(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = sorted(
        {
            name
            for node in ast.walk(tree)
            # attr: cv2.imwrite(...); id: imwrite(...); name: from cv2 import imwrite
            for name in (
                getattr(node, "attr", None),
                getattr(node, "id", None),
                node.name if isinstance(node, ast.alias) else None,
            )
            if name in IMAGE_WRITERS
        }
    )
    assert not found, f"{path.name} usa funciones que guardan imágenes o video: {found}"


def test_a_supabase_solo_van_correo_contrasena_y_equipo(tmp_path) -> None:
    sent: list[dict] = []

    class RecordingSupabase(FakeSupabase):
        def post(self, url, headers, body):  # noqa: ANN001
            sent.append(body)
            return super().post(url, headers, body)

    server, clock = RecordingSupabase(), Clock()
    manager = make_manager(server, clock, tmp_path)
    manager.login("ana@example.com", "Clave1234")
    clock.now = START + timedelta(days=VALID_DAYS + 1)
    manager.revalidate()
    fields = {key for body in sent for key in body}
    assert fields <= ALLOWED_FIELDS, f"campos no permitidos: {fields - ALLOWED_FIELDS}"
    assert all(url.startswith("https://") for url, _ in server.calls)


def test_el_identificador_del_equipo_no_es_el_original(tmp_path) -> None:
    sent: list[dict] = []

    class RecordingSupabase(FakeSupabase):
        def post(self, url, headers, body):  # noqa: ANN001
            sent.append(body)
            return super().post(url, headers, body)

    make_manager(RecordingSupabase(), Clock(), tmp_path).login("ana@example.com", "Clave1234")
    hashes = [body["p_device_hash"] for body in sent if "p_device_hash" in body]
    assert hashes and all(len(h) == 64 for h in hashes)


def test_sin_internet_en_los_ultimos_dias_sigue_funcionando(tmp_path) -> None:
    """La renovación automática falla sin red, pero no borra la licencia ni bloquea la app."""
    server, clock = FakeSupabase(), Clock()
    make_manager(server, clock, tmp_path).login("ana@example.com", "Clave1234")
    clock.now = START + timedelta(days=VALID_DAYS - RENEW_BEFORE_DAYS + 1)
    server.offline = True
    manager = make_manager(server, clock, tmp_path)
    assert not manager.try_renew()
    assert manager.status() is LicenseStatus.VALID
    assert make_manager(server, clock, tmp_path).status() is LicenseStatus.VALID


def test_el_modelo_se_carga_del_equipo_y_no_se_descarga(tmp_path) -> None:
    with pytest.raises(VisionError, match="No se encontró el modelo"):
        FaceLandmarker(tmp_path / "no-existe.task", 0.5, 0.5, 0.5)


def test_las_metricas_no_guardan_datos_personales() -> None:
    metadata = environment_metadata()
    assert set(metadata) == {
        "os",
        "python",
        "architecture",
        "cpu",
        "logical_cpu_count",
        "ram_bytes",
        "session_type",
    }
