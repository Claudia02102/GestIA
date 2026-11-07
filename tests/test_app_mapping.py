"""Mapeo por aplicación (P3-16)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from gestia.app_context import normalize_app_name  # noqa: E402
from gestia.gestures import Action, GestureId, remap_action  # noqa: E402
from gestia.profiles import Profile, ProfileStore  # noqa: E402
from gestia.ui_profile import GesturePanel  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qt_app):
    widget = GesturePanel()
    widget.set_profile(Profile("p", "P"))
    return widget


def choose(panel: GesturePanel, gesture: GestureId, action: Action) -> None:
    box = panel.action_boxes[gesture]
    box.setCurrentIndex(box.findData(str(action)))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Chrome.EXE", "chrome.exe"),
        ("winword", "winword.exe"),
        (r"C:\Program Files\Mozilla Firefox\firefox.exe", "firefox.exe"),
    ],
)
def test_app_names_are_normalized(text: str, expected: str) -> None:
    assert normalize_app_name(text) == expected


@pytest.mark.parametrize("text", ["", "   ", ".exe", "a*b.exe", "..\\"])
def test_invalid_app_names_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        normalize_app_name(text)


def test_each_app_uses_its_own_mapping_and_others_use_general() -> None:
    profile = Profile("p", "P")
    profile.app_actions["chrome.exe"] = remap_action(
        profile.actions, GestureId.SMILE, Action.DOUBLE_CLICK
    )
    profile.app_actions["winword.exe"] = remap_action(
        profile.actions, GestureId.SMILE, Action.SCROLL
    )
    assert profile.action_for(GestureId.SMILE, "chrome.exe") is Action.DOUBLE_CLICK
    assert profile.action_for(GestureId.SMILE, "winword.exe") is Action.SCROLL
    assert profile.action_for(GestureId.SMILE, "notepad.exe") is Action.DRAG
    assert profile.action_for(GestureId.SMILE, None) is Action.DRAG


def test_general_pause_gesture_resumes_in_any_app() -> None:
    profile = Profile("p", "P")
    profile.app_actions["chrome.exe"] = remap_action(
        profile.actions, GestureId.BLINK, Action.RIGHT_CLICK
    )
    assert profile.action_for(GestureId.BLINK, "chrome.exe") is Action.RIGHT_CLICK
    assert profile.action_for(GestureId.BLINK, "chrome.exe", paused=True) is Action.PAUSE


def test_app_mappings_survive_restart(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = store.load_active()
    profile.app_actions["chrome.exe"] = remap_action(
        profile.actions, GestureId.SMILE, Action.QUICK_MENU
    )
    store.save(profile)
    reopened = ProfileStore(tmp_path).load_active()
    assert reopened.app_actions == profile.app_actions


def test_profile_without_app_section_loads_with_general_only() -> None:
    raw = Profile("p", "P").to_dict()
    del raw["app_actions"]
    raw["schema_version"] = 3
    assert Profile.from_dict(raw).app_actions == {}


def test_panel_edits_app_mapping_without_touching_general(panel) -> None:
    general = dict(panel.profile.actions)
    panel.add_app("Chrome")
    assert panel.selected_app == "chrome.exe"
    choose(panel, GestureId.SMILE, Action.DOUBLE_CLICK)
    assert panel.profile.app_actions["chrome.exe"][GestureId.SMILE] is Action.DOUBLE_CLICK
    assert panel.profile.actions == general


def test_panel_keeps_left_click_in_app_mapping(panel, monkeypatch) -> None:
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    panel.add_app("chrome.exe")
    # Sonreír pasa a clic izquierdo y el guiño recibe el arrastre: sigue habiendo clic activo.
    choose(panel, GestureId.SMILE, Action.LEFT_CLICK)
    assert not warnings
    # Con el gesto desactivado, llevarle el clic izquierdo lo dejaría sin gesto activo.
    panel.profile.gestures[GestureId.PUCKER].enabled = False
    choose(panel, GestureId.PUCKER, Action.LEFT_CLICK)
    assert warnings
    assert panel.profile.app_actions["chrome.exe"][GestureId.SMILE] is Action.LEFT_CLICK


def test_gesture_with_left_click_in_app_mapping_cannot_be_disabled(panel, monkeypatch) -> None:
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    panel.add_app("chrome.exe")
    choose(panel, GestureId.SMILE, Action.LEFT_CLICK)
    panel.checks[GestureId.SMILE].setChecked(False)
    assert warnings
    assert panel.profile.gestures[GestureId.SMILE].enabled
