"""Pruebas de rendimiento: el trabajo por imagen debe caber de sobra en el presupuesto.

HU-05 pide al menos 15 imágenes por segundo, es decir, menos de 66 ms por imagen en total.
Se mide la mediana de muchas repeticiones para que una pausa aislada del equipo no la falsee.
"""

import os
import statistics
import time
from pathlib import Path

import pytest
from fakes import FakeMouse

from gestia.control import PointerController, PointerSettings, ScreenArea
from gestia.features import extract_features
from gestia.gestures import (
    DEFAULT_ACTIONS,
    GESTURES,
    GestureEngine,
    SignalRange,
    default_gesture_settings,
)

FRAME_BUDGET_MS = 1000 / 15
ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models" / "face_landmarker.task"
FACE_IMAGE = ROOT / "tests" / "system" / "data" / "rostro_prueba.jpg"


def median_ms(action, repeat: int) -> float:
    samples = []
    for index in range(repeat):
        started = time.perf_counter()
        action(index)
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples)


def landmarks(shift: float = 0.0) -> list[tuple[float, float, float]]:
    # Una malla de 478 puntos repartida por la cara; basta para ejercitar todos los cálculos.
    return [
        (0.3 + 0.4 * ((i * 37) % 100) / 100 + shift, 0.2 + 0.6 * ((i * 61) % 100) / 100, 0.0)
        for i in range(478)
    ]


def test_medidas_y_gestos_por_imagen_caben_en_el_presupuesto(record_property) -> None:
    engine = GestureEngine()
    engine.configure(
        default_gesture_settings(),
        {gesture: SignalRange(0.0, 1.0) for gesture in GESTURES},
        DEFAULT_ACTIONS,
    )
    frames = [landmarks(i * 0.0005) for i in range(10)]

    def step(index: int) -> None:
        features = extract_features(frames[index % 10], 4 / 3)
        assert features is not None
        engine.update(features, index * 33)

    elapsed = median_ms(step, 500)
    record_property("medidas_y_gestos_ms", round(elapsed, 3))
    # Debe ser una fracción mínima del presupuesto: el resto es para MediaPipe y la interfaz.
    assert elapsed < FRAME_BUDGET_MS * 0.05


def test_control_del_puntero_por_imagen_es_inmediato(record_property) -> None:
    controller = PointerController(FakeMouse(), ScreenArea(0, 0, 1920, 1080), PointerSettings())
    elapsed = median_ms(
        lambda i: controller.update((0.5 + (i % 7) * 0.01, 0.5), (), i * 33), 1000
    )
    record_property("control_puntero_ms", round(elapsed, 3))
    assert elapsed < FRAME_BUDGET_MS * 0.02


def test_inferencia_de_mediapipe_permite_15_imagenes_por_segundo(record_property) -> None:
    if not MODEL.is_file():
        if os.environ.get("GESTIA_REQUIRE_MODEL") == "1":
            pytest.fail("Falta el modelo: ejecute python tools/download_model.py")
        pytest.skip("Falta el modelo: ejecute python tools/download_model.py")
    import cv2

    from gestia.vision import FaceLandmarker

    image = cv2.imread(str(FACE_IMAGE))
    landmarker = FaceLandmarker(MODEL, 0.5, 0.5, 0.5)
    try:
        landmarker.analyze(image, 1)  # la primera llamada prepara el modelo
        elapsed = median_ms(lambda i: landmarker.analyze(image, 100 + i * 33), 30)
    finally:
        landmarker.close()
    record_property("inferencia_ms", round(elapsed, 2))
    assert elapsed < FRAME_BUDGET_MS
