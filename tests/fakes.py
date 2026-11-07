"""Dobles de prueba compartidos: sustituyen el hardware (ratón y cámara) en todas las fases.

Son los *stubs* de la integración bottom-up: registran o entregan datos sin tocar el sistema.
"""

from __future__ import annotations

import time

from gestia.control import Button


class FakeMouse:
    """Ratón simulado: registra cada orden en vez de moverse por la pantalla."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.position: tuple[int, int] | None = None

    def move(self, x: int, y: int) -> None:
        self.position = (x, y)
        self.calls.append(("move", x, y))

    def press(self, button: Button) -> None:
        self.calls.append(("press", button, self.position))

    def release(self, button: Button) -> None:
        self.calls.append(("release", button, self.position))

    def click(self, button: Button, count: int = 1) -> None:
        self.calls.append(("click", button, count, self.position))

    def scroll(self, dx: int, dy: int) -> None:
        self.calls.append(("scroll", dx, dy))

    def escape(self) -> None:
        self.calls.append(("escape",))

    def of(self, kind: str) -> list[tuple]:
        return [call for call in self.calls if call[0] == kind]


class ImageCamera:
    """Cámara simulada que entrega siempre la misma imagen a ~30 fps."""

    def __init__(self, image: object) -> None:
        self.image = image
        height, width = image.shape[:2]  # type: ignore[attr-defined]
        self.actual_width, self.actual_height = width, height
        self.actual_fps = 30.0
        self.backend = "simulada"
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def read(self) -> tuple[bool, object]:
        time.sleep(0.03)
        return True, self.image.copy()  # type: ignore[attr-defined]

    def close(self) -> None:
        self.opened = False
