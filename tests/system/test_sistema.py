"""Pruebas de sistema: la aplicación completa, de extremo a extremo, con MediaPipe real.

Solo se simula el hardware: la cámara entrega una foto con un rostro (dominio público, NASA)
y el ratón registra las órdenes en vez de moverse. Necesitan el modelo de Face Landmarker
(``python tools/download_model.py``). Sin él se omiten, salvo que ``GESTIA_REQUIRE_MODEL=1``
(el CI lo activa para que no pasen en silencio).
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fakes import FakeMouse, ImageCamera  # noqa: E402

from gestia.config import AppConfig  # noqa: E402
from gestia.domain import TrackingState  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models" / "face_landmarker.task"
FACE_IMAGE = Path(__file__).parent / "data" / "rostro_prueba.jpg"


@pytest.fixture(scope="module")
def face_image():
    import cv2

    image = cv2.imread(str(FACE_IMAGE))
    assert image is not None, f"No se pudo leer {FACE_IMAGE}"
    return image


@pytest.fixture(scope="module")
def model_path() -> Path:
    if not MODEL.is_file():
        message = "Falta el modelo: ejecute python tools/download_model.py"
        if os.environ.get("GESTIA_REQUIRE_MODEL") == "1":
            pytest.fail(message)
        pytest.skip(message)
    return MODEL


def config_for(tmp_path: Path, model_path: Path) -> AppConfig:
    config = AppConfig()
    config.vision.model_path = str(model_path)
    config.metrics.path = str(tmp_path / "metrics.jsonl")
    config.profiles.directory = str(tmp_path / "profiles")
    return config


def run_gestia(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "gestia", *args],
        cwd=cwd, capture_output=True, text=True, timeout=60,
    )


def test_smoke_la_aplicacion_arranca_y_muestra_su_ayuda(tmp_path) -> None:
    result = run_gestia("--help", cwd=tmp_path)
    assert result.returncode == 0
    assert "GestIA" in result.stdout and "--camera" in result.stdout


def test_configuracion_invalida_termina_con_error_claro(tmp_path) -> None:
    bad = tmp_path / "config.json"
    bad.write_text(json.dumps({"vision": {"min_tracking_confidence": 3}}), encoding="utf-8")
    result = run_gestia("--config", str(bad), cwd=tmp_path)
    assert result.returncode == 2
    assert "seguimiento" in result.stderr


def test_pipeline_detecta_el_rostro_y_calcula_medidas(tmp_path, model_path, face_image,
                                                       monkeypatch) -> None:
    from gestia import worker as worker_module

    monkeypatch.setattr(worker_module, "OpenCVCamera", lambda *args: ImageCamera(face_image))
    worker = worker_module.PipelineWorker(config_for(tmp_path, model_path), tmp_path)
    packets, summaries, errors = [], [], []
    worker.packet_ready.connect(packets.append)
    worker.finished.connect(summaries.append)
    worker.error_occurred.connect(errors.append)
    stopper = threading.Timer(4.0, worker.request_stop)
    stopper.start()
    try:
        worker.run()
    finally:
        stopper.cancel()

    assert not errors
    tracked = [packet for packet in packets if packet.state is TrackingState.TRACKING]
    assert tracked, "El rostro de la imagen debe detectarse y seguirse"
    features = tracked[-1].features
    assert features is not None
    assert 0.3 < features.yaw < 0.7 and 0.3 < features.pitch < 0.8
    assert 0.15 < features.eye_left < 0.5 and 0.15 < features.eye_right < 0.5
    assert len(tracked[-1].result.landmarks) == 478
    summary = summaries[-1]
    assert summary["processed_results"] > 0
    assert summary["final_state"] == str(TrackingState.STOPPED)


def test_aplicacion_completa_calibra_y_mueve_el_cursor(tmp_path, model_path, face_image,
                                                        monkeypatch) -> None:
    """Iniciar → rostro detectado → asistente → perfil calibrado → el cursor va al centro."""
    from PySide6.QtWidgets import QApplication

    from gestia import ui
    from gestia import worker as worker_module
    from gestia.calibration import AxisRange, Calibration, HeadCalibration

    app = QApplication.instance() or QApplication([])
    mouse = FakeMouse()
    monkeypatch.setattr(worker_module, "OpenCVCamera", lambda *args: ImageCamera(face_image))
    monkeypatch.setattr(ui, "PynputBackend", lambda: mouse)
    window = ui.MainWindow(config_for(tmp_path, model_path), tmp_path)
    packets = []

    def wait_until(condition, seconds: float = 20.0) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        return False

    try:
        window.start_tracking()
        window.worker.packet_ready.connect(packets.append)
        # HU-06: con un perfil sin calibrar, el asistente se abre solo al detectar el rostro.
        assert wait_until(lambda: window.wizard is not None), "El asistente no se abrió"
        assert mouse.calls == [], "Durante la calibración no se controla el ratón"
        window.wizard.reject()
        assert wait_until(lambda: window.wizard is None)

        # Se calibra con la pose actual como reposo: el cursor debe ir al centro de la pantalla.
        features = next(p.features for p in reversed(packets) if p.features is not None)
        window.profile.calibration = Calibration(HeadCalibration(
            AxisRange(features.yaw, features.yaw + 0.1, features.yaw - 0.1),
            AxisRange(features.pitch, features.pitch - 0.08, features.pitch + 0.08),
        ))
        window._save_profile()
        assert wait_until(lambda: mouse.position is not None), "El cursor no se movió"
        screen = window.controller.screen
        center = (screen.left + screen.width // 2, screen.top + screen.height // 2)
        assert abs(mouse.position[0] - center[0]) <= screen.width * 0.05
        assert abs(mouse.position[1] - center[1]) <= screen.height * 0.05
        assert mouse.of("click") == [], "Una cara quieta no debe hacer clics"

        window.stop_tracking()
        assert wait_until(lambda: window.thread is None), "La cámara no se liberó"
    finally:
        if window.worker is not None:
            window.worker.request_stop()
        if window.thread is not None:
            window.thread.wait(5000)
        window.hotkeys.stop()
        window.close()
        app.processEvents()

    # Privacidad (HU-36): se guardan métricas técnicas y el perfil, nunca imágenes.
    saved = window.store.load(window.profile.id)
    assert saved.calibration is not None
    metrics = (tmp_path / "metrics.jsonl").read_text(encoding="utf-8")
    assert "processed_results" in metrics and "landmarks" not in metrics
    images = [p for p in tmp_path.rglob("*") if p.suffix.lower() in {".jpg", ".png", ".mp4"}]
    assert images == []
