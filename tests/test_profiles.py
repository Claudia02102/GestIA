import json

import pytest

from gestia.calibration import AxisRange, Calibration, HeadCalibration
from gestia.gestures import GestureId, SignalRange
from gestia.profiles import Profile, ProfileStore


def calibration(yaw: float) -> Calibration:
    return Calibration(
        HeadCalibration(AxisRange(yaw, yaw + 0.1, yaw - 0.1), AxisRange(0.55, 0.48, 0.62)),
        {GestureId.MOUTH_OPEN: SignalRange(0.05, 0.4)},
    )


def test_first_launch_creates_default_profile(tmp_path) -> None:
    store = ProfileStore(tmp_path / "profiles")
    profile = store.load_active()
    assert profile.name == "Perfil 1"
    assert not profile.calibrated
    assert store.active_id() == profile.id


def test_calibration_and_settings_survive_restart(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = store.load_active()
    profile.calibration = calibration(0.5)
    profile.gestures[GestureId.MOUTH_OPEN].sensitivity = 8
    profile.gestures[GestureId.SMILE].enabled = False
    store.save(profile)

    reopened = ProfileStore(tmp_path).load_active()
    assert reopened.calibration == profile.calibration
    assert reopened.gestures[GestureId.MOUTH_OPEN].sensitivity == 8
    assert not reopened.gestures[GestureId.SMILE].enabled


def test_profiles_keep_their_own_calibration_and_active_choice(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    ana = store.create("Ana María")
    luis = store.create("Luis")
    ana.calibration, luis.calibration = calibration(0.5), calibration(0.45)
    store.save(ana)
    store.save(luis)
    store.set_active(luis.id)
    assert ana.id == "ana-maria"
    assert ProfileStore(tmp_path).load_active().calibration == calibration(0.45)
    assert store.load(ana.id).calibration == calibration(0.5)
    assert [p.name for p in store.list()] == ["Ana María", "Luis"]


def test_duplicate_or_empty_names_are_rejected(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    store.create("Ana")
    with pytest.raises(ValueError, match="Ya existe"):
        store.create("ana")
    with pytest.raises(ValueError, match="vacío"):
        store.create("  ")


def test_deleting_active_profile_falls_back_to_remaining(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    first = store.create("A")
    second = store.create("B")
    store.set_active(second.id)
    store.delete(second.id)
    assert store.active_id() is None
    assert store.load_active().id == first.id


def test_corrupt_or_invalid_profiles_are_skipped(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    good = store.create("Válido")
    (tmp_path / "roto.json").write_text("{no es json", encoding="utf-8")
    bad = Profile("malo", "Malo").to_dict()
    bad["gestures"]["mouth_open"]["sensitivity"] = 99
    (tmp_path / "malo.json").write_text(json.dumps(bad), encoding="utf-8")
    assert [p.id for p in store.list()] == [good.id]


def test_profile_file_contains_no_images_or_landmarks(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = store.load_active()
    profile.calibration = calibration(0.5)
    store.save(profile)
    raw = json.loads((tmp_path / f"{profile.id}.json").read_text(encoding="utf-8"))
    assert set(raw) == {
        "schema_version", "id", "name", "created_at", "updated_at", "gestures", "actions",
        "calibration", "pointer", "keyboard",
    }
    assert "landmarks" not in json.dumps(raw)


def test_sprint_2_profile_without_pointer_section_still_loads(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    raw = Profile("viejo", "Viejo").to_dict()
    del raw["pointer"]
    del raw["gestures"]["pucker"]
    raw["schema_version"] = 1
    (tmp_path / "viejo.json").write_text(json.dumps(raw), encoding="utf-8")
    profile = store.load("viejo")
    assert profile.pointer.enabled and profile.pointer.speed == 1.0
    assert GestureId.PUCKER in profile.gestures


def test_pointer_settings_round_trip_and_validation(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = store.load_active()
    profile.pointer.speed, profile.pointer.dwell_enabled = 2.5, True
    store.save(profile)
    assert store.load(profile.id).pointer == profile.pointer
    raw = profile.to_dict()
    raw["pointer"]["speed"] = 9
    with pytest.raises(ValueError):
        Profile.from_dict(raw)


def test_keyboard_settings_survive_restart(tmp_path) -> None:
    from gestia.keyboard import Layout

    store = ProfileStore(tmp_path)
    profile = store.load_active()
    profile.keyboard.layout = Layout.ABC
    profile.keyboard.key_size = 80
    profile.keyboard.phrases.append("Llama a mi hermana")
    profile.keyboard.vocabulary["gestia"] = 2
    store.save(profile)
    reopened = ProfileStore(tmp_path).load_active()
    assert reopened.keyboard == profile.keyboard


def test_sprint3_profile_loads_with_default_keyboard(tmp_path) -> None:
    from gestia.keyboard import DEFAULT_PHRASES, Layout

    store = ProfileStore(tmp_path)
    raw = store.load_active().to_dict()
    del raw["keyboard"]
    raw["schema_version"] = 2
    (tmp_path / f"{raw['id']}.json").write_text(json.dumps(raw), encoding="utf-8")
    profile = ProfileStore(tmp_path).load_active()
    assert profile.keyboard.layout is Layout.QWERTY
    assert profile.keyboard.phrases == list(DEFAULT_PHRASES)
