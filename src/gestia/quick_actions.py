"""Acciones rápidas del sistema operativo (P3-11).

``run_quick_action`` traduce cada acción del menú en atajos de teclado o en abrir una
aplicación mediante un ``SystemBackend``. El backend real usa pynput y ``os.startfile``; las
pruebas usan uno simulado.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class QuickAction(StrEnum):
    SWITCH_WINDOW = "switch_window"
    BACK = "back"
    CLOSE_WINDOW = "close_window"
    SHOW_DESKTOP = "show_desktop"
    OPEN_EXPLORER = "open_explorer"
    OPEN_BROWSER = "open_browser"
    OPEN_NOTEPAD = "open_notepad"
    OPEN_CALCULATOR = "open_calculator"


QUICK_ACTION_TEXT = {
    QuickAction.SWITCH_WINDOW: "Cambiar de ventana",
    QuickAction.BACK: "Volver atrás",
    QuickAction.CLOSE_WINDOW: "Cerrar ventana",
    QuickAction.SHOW_DESKTOP: "Mostrar escritorio",
    QuickAction.OPEN_EXPLORER: "Explorador de archivos",
    QuickAction.OPEN_BROWSER: "Navegador",
    QuickAction.OPEN_NOTEPAD: "Bloc de notas",
    QuickAction.OPEN_CALCULATOR: "Calculadora",
}

# Atajos de Windows; las teclas usan los nombres de ``pynput.keyboard.Key``.
HOTKEYS: dict[QuickAction, tuple[str, ...]] = {
    QuickAction.SWITCH_WINDOW: ("alt", "tab"),
    QuickAction.BACK: ("alt", "left"),
    QuickAction.CLOSE_WINDOW: ("alt", "f4"),
    QuickAction.SHOW_DESKTOP: ("cmd", "d"),
}
APPS: dict[QuickAction, str] = {
    QuickAction.OPEN_EXPLORER: "explorer.exe",
    QuickAction.OPEN_BROWSER: "https://www.google.com",
    QuickAction.OPEN_NOTEPAD: "notepad.exe",
    QuickAction.OPEN_CALCULATOR: "calc.exe",
}
# Un gesto involuntario no debe cerrar una ventana: se pide confirmación antes.
NEEDS_CONFIRMATION = frozenset({QuickAction.CLOSE_WINDOW})


class SystemBackend(Protocol):
    def hotkey(self, *keys: str) -> None: ...
    def launch(self, target: str) -> None: ...


def run_quick_action(action: QuickAction, backend: SystemBackend) -> None:
    if action in HOTKEYS:
        backend.hotkey(*HOTKEYS[action])
    else:
        backend.launch(APPS[action])


class PynputSystemBackend:
    """Backend real: atajos con pynput (SendInput en Windows) y apps con ``os.startfile``."""

    def __init__(self) -> None:
        from pynput import keyboard

        self._controller = keyboard.Controller()
        self._key = keyboard.Key

    def hotkey(self, *keys: str) -> None:
        *modifiers, last = (getattr(self._key, name) for name in keys)
        for modifier in modifiers:
            self._controller.press(modifier)
        try:
            self._controller.tap(last)
        finally:
            for modifier in reversed(modifiers):
                self._controller.release(modifier)

    def launch(self, target: str) -> None:
        import os

        os.startfile(target)  # type: ignore[attr-defined]  # solo existe en Windows
