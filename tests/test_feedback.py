"""P3-44 (retroalimentación e indicador de estado) y P3-45 (recordatorios de descanso)."""

import pytest

from gestia.control import ControlMode
from gestia.domain import TrackingState
from gestia.feedback import (
    BreakTimer,
    Feedback,
    FeedbackSettings,
    Sound,
    StatusKind,
    break_message,
    status_for,
)
from gestia.profiles import Profile, ProfileStore


class FakeSound:
    def __init__(self) -> None:
        self.played: list[Sound] = []

    def play(self, sound: Sound) -> None:
        self.played.append(sound)


TRACKING = TrackingState.TRACKING


@pytest.mark.parametrize(
    ("running", "tracking", "mode", "paused", "expected"),
    [
        (False, TrackingState.STOPPED, None, False, StatusKind.STOPPED),
        (True, TrackingState.ERROR, None, False, StatusKind.STOPPED),
        (True, TRACKING, ControlMode.NORMAL, False, StatusKind.ACTIVE),
        (True, TRACKING, ControlMode.DRAGGING, False, StatusKind.ACTIVE),
        (True, TRACKING, ControlMode.NORMAL, True, StatusKind.PAUSED),
        (True, TrackingState.SEARCHING, None, False, StatusKind.NO_FACE),
        (True, TrackingState.LOST, ControlMode.NO_FACE, False, StatusKind.NO_FACE),
        (True, TRACKING, ControlMode.DISABLED, False, StatusKind.CURSOR_OFF),
    ],
)
def test_indicador_muestra_activo_pausa_y_sin_rostro(running, tracking, mode, paused, expected):
    assert status_for(running, tracking, mode, paused) is expected


def test_en_pausa_sigue_indicando_pausa_aunque_se_pierda_el_rostro() -> None:
    assert status_for(True, TrackingState.LOST, ControlMode.PAUSED, True) is StatusKind.PAUSED


def test_sonido_suena_solo_si_esta_activado() -> None:
    sound, settings = FakeSound(), FeedbackSettings()
    feedback = Feedback(sound, settings)
    assert feedback.play(Sound.GESTURE)
    settings.sound = False
    assert not feedback.play(Sound.GESTURE)
    assert sound.played == [Sound.GESTURE]


def ticks(timer: BreakTimer, start: float, end: float, active: bool, step: float = 1.0) -> int:
    fired, now = 0, start
    while now <= end:
        fired += timer.tick(now, active)
        now += step
    return fired


def test_aviso_aparece_al_cumplirse_el_intervalo_y_vuelve_a_contar() -> None:
    timer = BreakTimer(FeedbackSettings(break_minutes=1))
    assert ticks(timer, 0, 59, active=True) == 0
    assert ticks(timer, 60, 61, active=True) == 1
    assert ticks(timer, 62, 119, active=True) == 0
    assert ticks(timer, 120, 122, active=True) == 1


def test_el_tiempo_en_pausa_o_sin_rostro_no_cuenta() -> None:
    timer = BreakTimer(FeedbackSettings(break_minutes=1), rest_reset_s=600)
    ticks(timer, 0, 40, active=True)
    assert ticks(timer, 41, 300, active=False) == 0
    # Solo faltaban ~20 s de uso activo, no 60.
    assert ticks(timer, 301, 330, active=True) == 1


def test_un_descanso_largo_reinicia_la_cuenta() -> None:
    timer = BreakTimer(FeedbackSettings(break_minutes=1), rest_reset_s=120)
    ticks(timer, 0, 50, active=True)
    ticks(timer, 51, 200, active=False)
    assert ticks(timer, 201, 255, active=True) == 0
    assert ticks(timer, 256, 265, active=True) == 1


def test_recordatorios_desactivados_no_aparecen() -> None:
    timer = BreakTimer(FeedbackSettings(breaks=False, break_minutes=1))
    assert ticks(timer, 0, 3600, active=True) == 0


def test_cambiar_el_intervalo_se_aplica_sin_reiniciar() -> None:
    settings = FeedbackSettings(break_minutes=30)
    timer = BreakTimer(settings)
    ticks(timer, 0, 100, active=True)
    timer.configure(FeedbackSettings(break_minutes=2))
    assert ticks(timer, 101, 125, active=True) == 1


@pytest.mark.parametrize(
    "raw",
    [{"break_minutes": 0}, {"break_minutes": 500}, {"break_minutes": "30"},
     {"sound": "sí"}, {"desconocido": 1}, "x"],
)
def test_ajustes_de_avisos_invalidos_se_rechazan(raw) -> None:
    with pytest.raises((ValueError, TypeError)):
        FeedbackSettings.from_dict(raw)


def test_los_avisos_se_guardan_en_el_perfil(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = store.load_active()
    profile.feedback = FeedbackSettings(sound=False, indicator=False, break_minutes=45)
    store.save(profile)
    assert ProfileStore(tmp_path).load_active().feedback == profile.feedback


def test_perfil_anterior_sin_avisos_carga_valores_por_defecto() -> None:
    raw = Profile("viejo", "Viejo").to_dict()
    del raw["feedback"]
    assert Profile.from_dict(raw).feedback == FeedbackSettings()


def test_perfil_con_avisos_invalidos_se_rechaza() -> None:
    raw = Profile("p", "P").to_dict()
    raw["feedback"]["break_minutes"] = -5
    with pytest.raises(ValueError):
        Profile.from_dict(raw)


def test_restaurar_valores_tambien_restaura_los_avisos() -> None:
    profile = Profile("p", "P")
    profile.feedback = FeedbackSettings(sound=False, breaks=False, break_minutes=5)
    profile.restore_defaults()
    assert profile.feedback == FeedbackSettings()


def test_mensaje_de_descanso_menciona_el_intervalo() -> None:
    assert "45 min" in break_message(45)
