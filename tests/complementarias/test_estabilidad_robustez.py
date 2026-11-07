"""Pruebas de estabilidad y robustez.

- Estabilidad: minutos de uso simulado con temblor y parpadeos naturales no deben producir
  acciones (criterio de HU-30: «parpadear de forma natural durante un minuto no genera clics»).
- Robustez: datos de entrada erróneos se rechazan con un error claro, sin romper la app.
"""

import contextlib
import json
import random

import pytest

from gestia.features import FaceFeatures, extract_features
from gestia.gestures import (
    DEFAULT_ACTIONS,
    GESTURES,
    GestureEngine,
    GestureId,
    SignalRange,
    default_gesture_settings,
)
from gestia.profiles import Profile, ProfileStore

FPS = 30
NEUTRAL = dict(yaw=0.5, pitch=0.55, eye_left=0.3, eye_right=0.3, mouth_open=0.05,
               brow_raise=0.2, smile=0.4)
RANGES = {
    GestureId.MOUTH_OPEN: SignalRange(0.05, 0.45),
    GestureId.BLINK: SignalRange(0.3, 0.08),
    GestureId.WINK_LEFT: SignalRange(0.0, -0.2),
    GestureId.WINK_RIGHT: SignalRange(0.0, -0.2),
    GestureId.BROW_RAISE: SignalRange(0.2, 0.26),
    GestureId.SMILE: SignalRange(0.4, 0.47),
    GestureId.PUCKER: SignalRange(0.4, 0.33),
}


def simulate(minutes: float, seed: int, blink_every_s: float = 4.0) -> list:
    """Cara en reposo con temblor de medición y parpadeos naturales de ~150 ms."""
    rng = random.Random(seed)
    engine = GestureEngine()
    engine.configure(default_gesture_settings(), RANGES, DEFAULT_ACTIONS)
    events, next_blink, blink_until = [], blink_every_s * FPS, -1
    for frame in range(int(minutes * 60 * FPS)):
        if frame >= next_blink:
            blink_until = frame + rng.randint(3, 5)  # 100–170 ms con ambos ojos cerrados
            next_blink = frame + rng.uniform(2.0, 2 * blink_every_s) * FPS
        eye = 0.08 if frame < blink_until else 0.3
        values = {name: value + rng.gauss(0, 0.004) for name, value in NEUTRAL.items()}
        values["eye_left"] = eye + rng.gauss(0, 0.01)
        values["eye_right"] = eye + rng.gauss(0, 0.01)
        events.extend(engine.update(FaceFeatures(**values), frame * 1000 // FPS).events)
    return events


def test_estabilidad_cinco_minutos_de_reposo_con_parpadeos_no_generan_acciones() -> None:
    assert simulate(minutes=5, seed=7) == []


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_estabilidad_parpadeos_frecuentes_tampoco_hacen_clic(seed: int) -> None:
    assert simulate(minutes=1, seed=seed, blink_every_s=1.5) == []


@pytest.mark.parametrize(
    "points",
    [
        [],
        [(0.5, 0.5, 0.0)] * 10,
        [(0.5, 0.5, 0.0)] * 478,  # todos los puntos iguales: divisiones entre cero
        [(float("nan"), 0.5, 0.0)] * 478,
    ],
)
def test_robustez_landmarks_degenerados_no_rompen_las_medidas(points) -> None:
    features = extract_features(points, 4 / 3)
    if features is not None:
        assert all(isinstance(features.metric(name), float) for name in NEUTRAL)


def test_robustez_perfiles_con_datos_erroneos_se_rechazan_con_valueerror() -> None:
    rng = random.Random(42)
    base = Profile("p", "P").to_dict()
    junk = [None, -1, 99, "x", [], {}, 1e308, True]
    for _ in range(300):
        raw = json.loads(json.dumps(base))
        section = rng.choice(["gestures", "actions", "pointer", "keyboard", "calibration"])
        if section == "gestures":
            gesture = rng.choice(list(raw["gestures"]))
            field = rng.choice(["sensitivity", "hold_ms"])
            raw["gestures"][gesture][field] = rng.choice(junk)
        elif section == "actions":
            raw["actions"][rng.choice(list(raw["actions"]))] = rng.choice(junk)
        elif section == "pointer":
            raw["pointer"][rng.choice(list(raw["pointer"]))] = rng.choice(junk)
        elif section == "keyboard":
            raw["keyboard"][rng.choice(list(raw["keyboard"]))] = rng.choice(junk)
        else:
            raw["calibration"] = rng.choice([{"head": None}, {"head": {}}, "x", 5])
        # Un dato erróneo debe rechazarse con ValueError, nunca con otra excepción.
        with contextlib.suppress(ValueError):
            Profile.from_dict(raw)


def test_robustez_un_perfil_danado_no_impide_abrir_los_demas(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    good = store.create("Válido")
    (tmp_path / "danado.json").write_bytes(b"\x00\xff no es json")
    (tmp_path / "vacio.json").write_text("", encoding="utf-8")
    assert [profile.id for profile in store.list()] == [good.id]


def test_robustez_todas_las_acciones_tienen_texto_y_todos_los_gestos_nombre() -> None:
    from gestia.gestures import ACTION_TEXT, Action

    assert set(ACTION_TEXT) == set(Action)
    assert all(spec.name and spec.instruction for spec in GESTURES.values())
