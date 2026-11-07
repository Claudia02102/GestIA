import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from gestia.calibration import AxisRange, Calibration, HeadCalibration  # noqa: E402
from gestia.config import AppConfig  # noqa: E402
from gestia.control import PointerSettings  # noqa: E402
from gestia.gestures import (  # noqa: E402
    DEFAULT_ACTIONS,
    Action,
    GestureId,
    SignalRange,
    default_gesture_settings,
)
from gestia.keyboard import KeyboardSettings, Layout  # noqa: E402
from gestia.profiles import Profile, ProfileStore  # noqa: E402


def customized(profile: Profile) -> Profile:
    profile.calibration = Calibration(
        HeadCalibration(AxisRange(0.5, 0.6, 0.4), AxisRange(0.55, 0.48, 0.62)),
        {GestureId.MOUTH_OPEN: SignalRange(0.05, 0.4)},
    )
    profile.gestures[GestureId.MOUTH_OPEN].sensitivity = 10
    profile.gestures[GestureId.SMILE].enabled = False
    profile.gestures[GestureId.BLINK].hold_ms = 100
    profile.actions[GestureId.MOUTH_OPEN] = Action.QUICK_MENU
    profile.app_actions["chrome.exe"] = dict(profile.actions)
    profile.pointer.speed, profile.pointer.dwell_enabled = 2.5, True
    profile.keyboard.layout, profile.keyboard.key_size = Layout.ABC, 80
    profile.keyboard.phrases = ["Hola, ¿cómo estás?"]
    profile.keyboard.vocabulary = {"gestia": 3}
    return profile


def test_restore_returns_mapping_and_sensitivity_to_initial_values() -> None:
    profile = customized(Profile("ana", "Ana"))
    profile.restore_defaults()
    assert profile.gestures == default_gesture_settings()
    assert profile.actions == DEFAULT_ACTIONS
    assert profile.app_actions == {}
    assert profile.pointer == PointerSettings()
    assert profile.keyboard.layout is KeyboardSettings().layout
    assert profile.keyboard.key_size == KeyboardSettings().key_size


def test_restore_keeps_personal_data() -> None:
    profile = customized(Profile("ana", "Ana"))
    calibration = profile.calibration
    profile.restore_defaults()
    assert profile.name == "Ana"
    assert profile.calibration == calibration
    assert profile.keyboard.phrases == ["Hola, ¿cómo estás?"]
    assert profile.keyboard.vocabulary == {"gestia": 3}


def test_restored_profile_survives_restart(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = customized(store.load_active())
    store.save(profile)
    profile.restore_defaults()
    store.save(profile)
    reopened = ProfileStore(tmp_path).load_active()
    assert reopened.actions == DEFAULT_ACTIONS
    assert reopened.gestures == default_gesture_settings()


def test_uncalibrated_gestures_lists_only_enabled_ones() -> None:
    profile = customized(Profile("ana", "Ana"))
    profile.restore_defaults()
    missing = profile.uncalibrated_gestures()
    assert GestureId.MOUTH_OPEN not in missing
    assert all(profile.gestures[gesture].enabled for gesture in missing)


@pytest.fixture
def window(tmp_path, monkeypatch):
    from gestia import ui

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    win = ui.MainWindow(AppConfig(), tmp_path)
    customized(win.profile)
    win.store.save(win.profile)
    yield win
    win.hotkeys.stop()
    win.close()
    app.processEvents()


def test_restore_asks_for_confirmation_and_no_keeps_everything(window, monkeypatch) -> None:
    asked = []

    def answer(*args, **kwargs):
        asked.append(args)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", answer)
    window.restore_defaults()
    assert asked
    assert window.profile.actions[GestureId.MOUTH_OPEN] is Action.QUICK_MENU
    assert window.store.load(window.profile.id).gestures[GestureId.MOUTH_OPEN].sensitivity == 10


def test_restore_after_confirmation_updates_profile_and_panel(window, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    window.restore_defaults()
    saved = window.store.load(window.profile.id)
    assert saved.actions == DEFAULT_ACTIONS and saved.app_actions == {}
    assert saved.gestures == default_gesture_settings()
    assert saved.calibration is not None
    mouth = window.panel.sliders[GestureId.MOUTH_OPEN].value()
    assert mouth == default_gesture_settings()[GestureId.MOUTH_OPEN].sensitivity
    box = window.panel.action_boxes[GestureId.MOUTH_OPEN]
    assert box.currentData() == str(DEFAULT_ACTIONS[GestureId.MOUTH_OPEN])
    assert window.panel.app_selector.count() == 1
