"""Instalación sencilla (P3-24) e inicio automático (P3-25)."""

import argparse
import sys
from pathlib import Path

import pytest

from gestia import app, autostart, paths
from gestia.autostart import AUTOSTART_FLAG, Autostart
from gestia.config import AppConfig


class FakeRegistry:
    def __init__(self, value: str | None = None, fail: bool = False) -> None:
        self.value = value
        self.fail = fail

    def get(self) -> str | None:
        if self.fail:
            raise OSError("sin acceso")
        return self.value

    def set(self, command: str) -> None:
        if self.fail:
            raise OSError("sin acceso")
        self.value = command

    def delete(self) -> None:
        if self.fail:
            raise OSError("sin acceso")
        self.value = None


def args(**overrides) -> argparse.Namespace:
    values = {"config": None, "camera": None, "data_dir": None, "autostart": False}
    values.update(overrides)
    return argparse.Namespace(**values)


def test_installed_data_goes_to_local_appdata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root, config = app.resolve_locations(args())
    assert root == (tmp_path / "GestIA").resolve()
    assert root.is_dir()
    assert config == root / "config.json"


def test_development_keeps_project_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    root, config = app.resolve_locations(args())
    assert root == tmp_path.resolve()
    assert config == root / "config.json"


def test_data_dir_argument_wins(tmp_path) -> None:
    root, config = app.resolve_locations(args(data_dir=tmp_path / "datos"))
    assert root == (tmp_path / "datos").resolve() and root.is_dir()
    assert config == root / "config.json"


def test_installed_app_uses_bundled_model(tmp_path, monkeypatch) -> None:
    bundle = tmp_path / "programa"
    (bundle / "models").mkdir(parents=True)
    (bundle / "models" / "face_landmarker.task").write_bytes(b"modelo")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    config = AppConfig()
    app.use_bundled_model(config, tmp_path / "datos")
    assert Path(config.vision.model_path) == bundle / "models" / "face_landmarker.task"


def test_model_in_data_folder_takes_priority(tmp_path, monkeypatch) -> None:
    data = tmp_path / "datos"
    (data / "models").mkdir(parents=True)
    (data / "models" / "face_landmarker.task").write_bytes(b"propio")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    config = AppConfig()
    app.use_bundled_model(config, data)
    assert config.vision.model_path == "models/face_landmarker.task"


def test_user_data_dir_without_localappdata() -> None:
    assert paths.user_data_dir({}).name == "GestIA"


def test_enable_and_disable_autostart() -> None:
    registry = FakeRegistry()
    service = Autostart(registry, '"C:\\GestIA\\GestIA.exe" --autostart')
    assert service.available and not service.is_enabled()
    service.set_enabled(True)
    assert service.is_enabled()
    assert registry.value == '"C:\\GestIA\\GestIA.exe" --autostart'
    service.set_enabled(False)
    assert not service.is_enabled() and registry.value is None


def test_autostart_unavailable_outside_windows() -> None:
    service = Autostart(None, "gestia")
    assert not service.available and not service.is_enabled()
    with pytest.raises(OSError):
        service.set_enabled(True)


def test_registry_errors_are_reported() -> None:
    service = Autostart(FakeRegistry(fail=True), "gestia")
    assert not service.is_enabled()
    with pytest.raises(OSError):
        service.set_enabled(True)


def test_refresh_fixes_moved_installation(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    registry = FakeRegistry("C:\\viejo\\GestIA.exe --autostart")
    Autostart(registry, "C:\\nuevo\\GestIA.exe --autostart").refresh()
    assert registry.value == "C:\\nuevo\\GestIA.exe --autostart"


def test_refresh_does_not_enable_or_touch_from_development(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    registry = FakeRegistry("C:\\instalado\\GestIA.exe --autostart")
    Autostart(registry, "python -m gestia --autostart").refresh()
    assert registry.value == "C:\\instalado\\GestIA.exe --autostart"
    empty = FakeRegistry()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    Autostart(empty, "GestIA.exe --autostart").refresh()
    assert empty.value is None


def test_installed_launch_command_matches_installer(monkeypatch) -> None:
    exe = "C:\\Users\\Ana Pérez\\AppData\\Local\\Programs\\GestIA\\GestIA.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", exe)
    # Igual que ValueData en packaging/installer.iss: """{app}\GestIA.exe"" --autostart"
    assert autostart.launch_command() == f'"{exe}" {AUTOSTART_FLAG}'


def test_development_launch_command_keeps_data_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    command = autostart.launch_command(tmp_path)
    assert "-m gestia --autostart --data-dir" in command
    assert str(tmp_path) in command


def test_autostart_flag_is_parsed() -> None:
    parsed = app.build_parser().parse_args(["--autostart", "--data-dir", "x"])
    assert parsed.autostart and parsed.data_dir == Path("x")


def test_installer_and_app_use_same_registry_value() -> None:
    script = (Path(__file__).parents[1] / "packaging" / "installer.iss").read_text(
        encoding="utf-8-sig"
    )
    assert autostart.RUN_KEY in script
    assert f'ValueName: "{autostart.VALUE_NAME}"' in script
    assert f'{AUTOSTART_FLAG}"' in script
