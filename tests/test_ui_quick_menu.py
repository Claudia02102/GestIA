import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from gestia.quick_actions import QuickAction  # noqa: E402
from gestia.ui_quick_menu import QuickMenuWindow  # noqa: E402


class FakeSystem:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def hotkey(self, *keys: str) -> None:
        self.calls.append(("hotkey", keys))

    def launch(self, target: str) -> None:
        self.calls.append(("launch", target))

    def close_window(self) -> None:
        self.calls.append(("close",))


@pytest.fixture
def menu():
    app = QApplication.instance() or QApplication([])
    system = FakeSystem()
    window = QuickMenuWindow(system)
    yield window, system
    window.close()
    app.processEvents()


def test_menu_buttons_run_their_action(menu) -> None:
    window, system = menu
    window.buttons[QuickAction.SWITCH_WINDOW].click()
    window.buttons[QuickAction.OPEN_CALCULATOR].click()
    assert system.calls == [("hotkey", ("alt", "tab")), ("launch", "calc.exe")]


def test_closing_a_window_waits_for_confirmation(menu) -> None:
    window, system = menu
    window.buttons[QuickAction.CLOSE_WINDOW].click()
    assert window.confirming and system.calls == []
    window.confirm_button.click()
    assert not window.confirming
    assert system.calls == [("close",)]


def test_cancel_does_not_close_the_window(menu) -> None:
    window, system = menu
    window.buttons[QuickAction.CLOSE_WINDOW].click()
    window.cancel_button.click()
    assert not window.confirming and system.calls == []


def test_menu_floats_without_taking_focus(menu) -> None:
    from PySide6.QtCore import Qt

    window, _ = menu
    flags = window.windowFlags()
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
