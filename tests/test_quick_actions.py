import pytest

from gestia.quick_actions import (
    APPS,
    HOTKEYS,
    NEEDS_CONFIRMATION,
    QUICK_ACTION_TEXT,
    QuickAction,
    run_quick_action,
)


class FakeSystem:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def hotkey(self, *keys: str) -> None:
        self.calls.append(("hotkey", keys))

    def launch(self, target: str) -> None:
        self.calls.append(("launch", target))

    def close_window(self) -> None:
        self.calls.append(("close",))


@pytest.mark.parametrize(
    ("action", "keys"),
    [
        (QuickAction.SWITCH_WINDOW, ("alt", "tab")),
        (QuickAction.BACK, ("alt", "left")),
        (QuickAction.SHOW_DESKTOP, ("cmd", "d")),
    ],
)
def test_window_actions_send_windows_shortcuts(action, keys) -> None:
    system = FakeSystem()
    run_quick_action(action, system)
    assert system.calls == [("hotkey", keys)]


def test_close_window_closes_the_active_window() -> None:
    system = FakeSystem()
    run_quick_action(QuickAction.CLOSE_WINDOW, system)
    assert system.calls == [("close",)]


def test_app_actions_launch_the_application() -> None:
    system = FakeSystem()
    run_quick_action(QuickAction.OPEN_NOTEPAD, system)
    assert system.calls == [("launch", "notepad.exe")]


def test_every_action_has_a_label_and_a_single_way_to_run() -> None:
    for action in QuickAction:
        assert QUICK_ACTION_TEXT[action]
        ways = (action in HOTKEYS, action in APPS, action is QuickAction.CLOSE_WINDOW)
        assert sum(ways) == 1


def test_only_closing_a_window_asks_for_confirmation() -> None:
    assert frozenset({QuickAction.CLOSE_WINDOW}) == NEEDS_CONFIRMATION
