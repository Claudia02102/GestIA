import json

import pytest

from gestia.config import AppConfig


def test_invalid_confidence_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"vision": {"min_tracking_confidence": 1.5}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="seguimiento"):
        AppConfig.load(path)


def test_missing_config_uses_documented_defaults(tmp_path) -> None:
    config = AppConfig.load(tmp_path / "missing.json")
    assert (config.camera.width, config.camera.height) == (640, 480)
    assert config.camera.index == 0


def test_calibration_and_profile_sections_are_loaded(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"calibration": {"reach": 0.7}, "profiles": {"directory": "x"}}),
        encoding="utf-8",
    )
    config = AppConfig.load(path)
    assert config.calibration.reach == 0.7
    assert config.profiles.directory == "x"


def test_invalid_calibration_timing_is_rejected(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"calibration": {"recenter_hold_ms": 5000, "recenter_timeout_ms": 4000}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="calibración"):
        AppConfig.load(path)
