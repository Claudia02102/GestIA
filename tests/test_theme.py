"""Estilo visual y modo oscuro: paleta de marca, contraste accesible y cambio en vivo."""

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from gestia import theme  # noqa: E402
from gestia.config import AppConfig  # noqa: E402
from gestia.profiles import Profile, ProfileStore  # noqa: E402
from gestia.theme import DARK, LIGHT, AppearanceSettings  # noqa: E402

PALETTES = [LIGHT, DARK]


def luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_la_paleta_usa_los_colores_de_marca() -> None:
    assert (LIGHT.accent, LIGHT.background, LIGHT.surface, LIGHT.text) == (
        "#ff6a2b", "#f3efe6", "#ffffff", "#13171c"
    )
    assert (DARK.accent, DARK.background, DARK.text) == ("#ff6a2b", "#13171c", "#f3efe6")


# Pares de texto que aparecen en la interfaz: WCAG 2.1 AA exige 4,5:1.
TEXT_PAIRS = [
    ("text", "background"), ("text", "surface"), ("text", "surface_alt"),
    ("text_muted", "background"), ("text_muted", "surface"),
    ("accent_text", "background"), ("accent_text", "surface"),
    ("accent_text", "surface_alt"), ("accent_text", "accent_soft"),
    ("on_accent", "accent"), ("text", "accent_soft"),
    ("success", "surface"), ("warning", "surface"), ("danger", "surface"),
    ("info", "surface"), ("special", "surface"),
]


@pytest.mark.parametrize("palette", PALETTES, ids=lambda p: p.name)
@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_contraste_de_texto_cumple_wcag_aa(palette, foreground, background) -> None:
    ratio = contrast(getattr(palette, foreground), getattr(palette, background))
    assert ratio >= 4.5, f"{foreground} sobre {background} en modo {palette.name}: {ratio:.2f}"


@pytest.mark.parametrize("palette", PALETTES, ids=lambda p: p.name)
def test_el_naranja_se_distingue_del_fondo_como_elemento_grafico(palette) -> None:
    # Bordes, casillas y pestañas activas: WCAG 1.4.11 pide 3:1 frente a lo que los rodea;
    # en modo claro el naranja de marca da 2,9:1, por eso siempre va con texto o marca en tinta.
    assert contrast(palette.accent, palette.background) >= 2.4
    assert contrast(theme.INK, palette.accent) >= 4.5


@pytest.mark.parametrize("palette", PALETTES, ids=lambda p: p.name)
def test_la_hoja_de_estilo_solo_usa_colores_de_la_paleta(palette) -> None:
    allowed = {value.lower() for value in vars_of(palette).values()} | {"#cbd2d9"}
    for sheet in (theme.stylesheet(palette), theme.keyboard_stylesheet(palette)):
        used = {color.lower() for color in re.findall(r"#[0-9a-fA-F]{6}", sheet)}
        assert used <= allowed, used - allowed


def vars_of(palette) -> dict:
    return {name: getattr(palette, name) for name in palette.__dataclass_fields__
            if name != "name"}


def test_el_icono_de_la_casilla_existe() -> None:
    assert os.path.isfile(theme.CHECK_ICON)


def test_el_modo_oscuro_se_guarda_en_el_perfil(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = store.load_active()
    profile.appearance.dark_mode = True
    store.save(profile)
    assert ProfileStore(tmp_path).load_active().appearance.dark_mode


def test_perfil_anterior_sin_apariencia_abre_en_modo_claro() -> None:
    raw = Profile("viejo", "Viejo").to_dict()
    del raw["appearance"]
    assert Profile.from_dict(raw).appearance == AppearanceSettings()


@pytest.mark.parametrize("raw", [{"dark_mode": "sí"}, {"tema": 1}, "oscuro"])
def test_apariencia_invalida_se_rechaza(raw) -> None:
    with pytest.raises((ValueError, TypeError)):
        AppearanceSettings.from_dict(raw)


def test_restaurar_valores_conserva_el_modo_oscuro() -> None:
    profile = Profile("p", "P")
    profile.appearance.dark_mode = True
    profile.restore_defaults()
    assert profile.appearance.dark_mode


@pytest.fixture
def window(tmp_path):
    from gestia import ui

    app = QApplication.instance() or QApplication([])
    win = ui.MainWindow(AppConfig(), tmp_path)
    yield win, app
    win.hotkeys.stop()
    win.close()
    theme.apply(False)
    app.processEvents()


def test_el_interruptor_cambia_el_tema_al_momento_y_lo_guarda(window) -> None:
    win, app = window
    assert not win.dark_switch.isChecked() and theme.current() is LIGHT
    assert LIGHT.background in app.styleSheet()
    win.dark_switch.click()
    assert theme.current() is DARK
    assert DARK.surface in app.styleSheet()
    assert win.store.load(win.profile.id).appearance.dark_mode
    assert DARK.accent_text in win.brand_label.text()
    win.dark_switch.click()
    assert theme.current() is LIGHT


def test_al_abrir_se_aplica_el_tema_del_perfil(tmp_path) -> None:
    from gestia import ui

    app = QApplication.instance() or QApplication([])
    store = ProfileStore(tmp_path / "data" / "profiles")
    profile = store.load_active()
    profile.appearance.dark_mode = True
    store.save(profile)
    win = ui.MainWindow(AppConfig(), tmp_path)
    try:
        assert win.dark_switch.isChecked() and theme.current() is DARK
    finally:
        win.hotkeys.stop()
        win.close()
        theme.apply(False)
        app.processEvents()


def test_cambiar_de_perfil_aplica_su_tema(window) -> None:
    win, _ = window
    oscuro = win.store.create("Oscuro")
    oscuro.appearance.dark_mode = True
    win.store.save(oscuro)
    win._load_profiles()
    win._profile_selected(win.profile_selector.findData(oscuro.id))
    assert theme.current() is DARK and win.dark_switch.isChecked()


def test_el_estado_se_repinta_con_la_paleta_nueva(window) -> None:
    win, _ = window
    win.dark_switch.click()
    assert DARK.text_muted in win.state_label.styleSheet()
