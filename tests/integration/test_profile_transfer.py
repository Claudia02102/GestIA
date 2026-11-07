"""Exportar e importar perfiles (P3-17)."""

import json

import pytest

from gestia.calibration import AxisRange, Calibration, HeadCalibration
from gestia.gestures import Action, GestureId, SignalRange, remap_action
from gestia.profiles import EXPORT_FORMAT, Profile, ProfileStore


def customized(store: ProfileStore) -> Profile:
    profile = store.create("Ana")
    profile.gestures[GestureId.SMILE].sensitivity = 9
    profile.pointer.speed = 2.0
    profile.keyboard.phrases.append("Llama a mi hermana")
    profile.actions = remap_action(profile.actions, GestureId.SMILE, Action.DOUBLE_CLICK)
    profile.app_actions["chrome.exe"] = remap_action(
        profile.actions, GestureId.PUCKER, Action.QUICK_MENU
    )
    profile.calibration = Calibration(
        HeadCalibration(AxisRange(0.5, 0.6, 0.4), AxisRange(0.55, 0.48, 0.62)),
        {GestureId.MOUTH_OPEN: SignalRange(0.05, 0.4)},
    )
    store.save(profile)
    return profile


def snapshot(store: ProfileStore) -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8") for path in store.directory.glob("*.json")
    }


def wrap(profile: dict) -> str:
    return json.dumps({"format": EXPORT_FORMAT, "format_version": 1, "profile": profile})


def test_exported_profile_matches_on_another_computer(tmp_path) -> None:
    source = ProfileStore(tmp_path / "equipo1")
    profile = customized(source)
    file = tmp_path / "ana.json"
    source.export_profile(profile, file)

    target = ProfileStore(tmp_path / "equipo2")
    imported = target.import_profile(file)
    reopened = ProfileStore(tmp_path / "equipo2").load(imported.id)
    for loaded in (imported, reopened):
        assert loaded.name == "Ana"
        assert loaded.gestures == profile.gestures
        assert loaded.actions == profile.actions
        assert loaded.app_actions == profile.app_actions
        assert loaded.pointer == profile.pointer
        assert loaded.keyboard == profile.keyboard
        assert loaded.calibration == profile.calibration


def test_import_never_overwrites_an_existing_profile(tmp_path) -> None:
    store = ProfileStore(tmp_path / "datos")
    profile = customized(store)
    file = tmp_path / "ana.json"
    store.export_profile(profile, file)
    before = store.load(profile.id)

    imported = store.import_profile(file)
    assert imported.id != profile.id
    assert imported.name == "Ana (2)"
    assert store.load(profile.id) == before


def test_id_in_file_is_never_used_as_a_path(tmp_path) -> None:
    store = ProfileStore(tmp_path / "datos")
    raw = Profile("x", "Intruso").to_dict()
    raw["id"] = "../../fuera"
    file = tmp_path / "malo.json"
    file.write_text(wrap(raw), encoding="utf-8")
    imported = store.import_profile(file)
    assert imported.id == "intruso"
    assert not (tmp_path / "fuera.json").exists()


@pytest.mark.parametrize(
    "content",
    [
        "{no es json",
        "[]",
        '{"id": "x", "name": "Perfil interno sin formato"}',
        '{"format": "otro", "format_version": 1, "profile": {}}',
        f'{{"format": "{EXPORT_FORMAT}", "format_version": 99, "profile": {{"name": "A"}}}}',
        f'{{"format": "{EXPORT_FORMAT}", "format_version": 1, "profile": []}}',
        f'{{"format": "{EXPORT_FORMAT}", "format_version": 1, "profile": {{"name": "  "}}}}',
    ],
)
def test_invalid_file_reports_error_and_changes_nothing(tmp_path, content: str) -> None:
    store = ProfileStore(tmp_path / "datos")
    customized(store)
    store.set_active("ana")
    before = snapshot(store)
    file = tmp_path / "malo.json"
    file.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        store.import_profile(file)
    assert snapshot(store) == before


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("pointer", "speed", 99),
        ("pointer", "smoothing", 2.5),
        ("pointer", "enabled", "sí"),
        ("actions", "smile", "accion_inexistente"),
        ("app_actions", "a*b.exe", {}),
        ("keyboard", "phrases", "no es una lista"),
    ],
)
def test_out_of_range_values_are_rejected(tmp_path, section, key, value) -> None:
    store = ProfileStore(tmp_path / "datos")
    raw = Profile("x", "X").to_dict()
    raw[section][key] = value
    file = tmp_path / "malo.json"
    file.write_text(wrap(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        store.import_profile(file)
    assert not store.directory.exists()


def test_non_finite_numbers_are_rejected(tmp_path) -> None:
    store = ProfileStore(tmp_path / "datos")
    file = tmp_path / "malo.json"
    text = wrap(Profile("x", "X").to_dict()).replace('"speed": 1.0', '"speed": NaN')
    file.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        store.import_profile(file)
