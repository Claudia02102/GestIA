"""Teclado virtual en pantalla (Épica E4: HU-19 a HU-23).

``TypingSession`` es lógica pura: recibe las teclas pulsadas en el teclado de GestIA y da
órdenes a un ``KeyboardBackend``, que escribe en la aplicación que tiene el foco. Lleva la
palabra en curso para la predicción. El backend real usa pynput; las pruebas usan uno simulado.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from gestia.prediction import WordPredictor


class Layout(StrEnum):
    QWERTY = "qwerty"
    ABC = "abc"


LAYOUT_TEXT = {Layout.QWERTY: "QWERTY (español)", Layout.ABC: "Alfabética (ABC)"}

# Filas de caracteres. La fila de números y la de tildes son comunes a ambas distribuciones.
LAYOUTS: dict[Layout, tuple[str, ...]] = {
    Layout.QWERTY: (
        "1234567890",
        "qwertyuiop",
        "asdfghjklñ",
        "zxcvbnm,.-",
        "áéíóúü¿?¡!",
    ),
    Layout.ABC: (
        "1234567890",
        "abcdefghij",
        "klmnñopqrs",
        "tuvwxyz,.-",
        "áéíóúü¿?¡!",
    ),
}
COLUMNS = 10


class SpecialKey(StrEnum):
    ENTER = "enter"
    BACKSPACE = "backspace"
    DELETE = "delete"
    TAB = "tab"
    ESC = "esc"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    HOME = "home"
    END = "end"


SPECIAL_TEXT = {
    SpecialKey.ENTER: "Intro ⏎",
    SpecialKey.BACKSPACE: "⌫ Borrar",
    SpecialKey.DELETE: "Supr",
    SpecialKey.TAB: "Tab ⇥",
    SpecialKey.ESC: "Esc",
    SpecialKey.LEFT: "←",
    SpecialKey.RIGHT: "→",
    SpecialKey.UP: "↑",
    SpecialKey.DOWN: "↓",
    SpecialKey.HOME: "Inicio",
    SpecialKey.END: "Fin",
}


class Shortcut(StrEnum):
    COPY = "c"
    PASTE = "v"
    CUT = "x"
    UNDO = "z"
    SELECT_ALL = "a"


SHORTCUT_TEXT = {
    Shortcut.COPY: "Copiar",
    Shortcut.PASTE: "Pegar",
    Shortcut.CUT: "Cortar",
    Shortcut.UNDO: "Deshacer",
    Shortcut.SELECT_ALL: "Selec. todo",
}

DEFAULT_PHRASES = (
    "Hola, ¿cómo estás?",
    "Gracias.",
    "Necesito ayuda, por favor.",
    "Sí",
    "No",
    "Un momento, por favor.",
    "Tengo sed.",
    "Quiero descansar.",
)

MIN_KEY_SIZE, MAX_KEY_SIZE = 32, 140
MAX_PHRASES = 30
MAX_PHRASE_LENGTH = 200


@dataclass(slots=True)
class KeyboardSettings:
    layout: Layout = Layout.QWERTY
    key_size: int = 56
    phrases: list[str] = field(default_factory=lambda: list(DEFAULT_PHRASES))
    # Palabras aprendidas para la predicción (palabra → veces escrita).
    vocabulary: dict[str, int] = field(default_factory=dict)

    def validate(self) -> None:
        self.layout = Layout(self.layout)
        if not MIN_KEY_SIZE <= self.key_size <= MAX_KEY_SIZE:
            raise ValueError("Tamaño de tecla fuera de rango")
        if len(self.phrases) > MAX_PHRASES or any(
            not phrase.strip() or len(phrase) > MAX_PHRASE_LENGTH for phrase in self.phrases
        ):
            raise ValueError("Frases frecuentes no válidas")
        if any(not isinstance(count, int) or count < 1 for count in self.vocabulary.values()):
            raise ValueError("Vocabulario no válido")

    def to_dict(self) -> dict:
        return {
            "layout": str(self.layout),
            "key_size": self.key_size,
            "phrases": list(self.phrases),
            "vocabulary": dict(self.vocabulary),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> KeyboardSettings:
        settings = cls(
            layout=Layout(raw.get("layout", Layout.QWERTY)),
            key_size=int(raw.get("key_size", 56)),
            phrases=[str(item) for item in raw.get("phrases", DEFAULT_PHRASES)],
            vocabulary={str(k): int(v) for k, v in raw.get("vocabulary", {}).items()},
        )
        settings.validate()
        return settings


# Rejilla del teclado en unidades de tecla: filas de caracteres + sugerencias + especiales.
GRID_COLUMNS = COLUMNS + 3
GRID_ROWS = len(LAYOUTS[Layout.QWERTY]) + 3


def fit_key_size(requested: int, available_width: int, available_height: int,
                 spacing: int = 4, margin: int = 16) -> int:
    """Tamaño de tecla más cercano al pedido con el que el teclado cabe en la pantalla."""
    by_width = (available_width - margin * 2 - spacing * (GRID_COLUMNS - 1)) // GRID_COLUMNS
    by_height = (available_height - margin * 2 - spacing * (GRID_ROWS - 1)) // GRID_ROWS
    return max(MIN_KEY_SIZE, min(requested, by_width, by_height, MAX_KEY_SIZE))


class KeyboardBackend(Protocol):
    def type_text(self, text: str) -> None: ...
    def tap(self, key: SpecialKey) -> None: ...
    def shortcut(self, letter: str) -> None: ...


class TypingSession:
    """Escribe en la aplicación activa y lleva la palabra en curso para las sugerencias."""

    def __init__(
        self,
        backend: KeyboardBackend,
        predictor: WordPredictor,
        on_learn: Callable[[str], None] | None = None,
    ) -> None:
        self.backend, self.predictor = backend, predictor
        self.on_learn = on_learn
        self.word = ""
        self.shift = False
        self.caps = False

    @property
    def upper(self) -> bool:
        return self.shift != self.caps

    def suggestions(self, limit: int = 3) -> list[str]:
        return self.predictor.suggest(self.word, limit)

    def toggle_shift(self) -> None:
        self.shift = not self.shift

    def toggle_caps(self) -> None:
        self.caps = not self.caps
        self.shift = False

    def _end_word(self) -> None:
        if self.word and self.predictor.learn(self.word) and self.on_learn is not None:
            self.on_learn(self.word)
        self.word = ""

    def reset_word(self) -> None:
        """Olvida la palabra en curso sin aprenderla (el cursor de texto se movió)."""
        self.word = ""

    def press_char(self, char: str) -> None:
        if self.upper:
            char = char.upper()
        self.shift = False  # Mayús vale para una sola tecla.
        if char.isalpha():
            self.backend.type_text(char)
            self.word += char
        else:
            self._end_word()
            self.backend.type_text(char)

    def space(self) -> None:
        self._end_word()
        self.backend.type_text(" ")

    def press_special(self, key: SpecialKey) -> None:
        self.backend.tap(key)
        if key is SpecialKey.BACKSPACE:
            self.word = self.word[:-1]
        elif key in (SpecialKey.ENTER, SpecialKey.TAB):
            self._end_word()
        else:
            self.reset_word()

    def press_shortcut(self, shortcut: Shortcut) -> None:
        self.backend.shortcut(str(shortcut))
        self.reset_word()
        self.shift = False

    def choose(self, suggestion: str) -> None:
        """Completa la palabra en curso con la sugerencia y añade un espacio."""
        if suggestion.startswith(self.word):
            self.backend.type_text(suggestion[len(self.word):] + " ")
        else:
            # Difieren tildes o mayúsculas: se borra lo escrito y se escribe completa.
            for _ in self.word:
                self.backend.tap(SpecialKey.BACKSPACE)
            self.backend.type_text(suggestion + " ")
        self.word = suggestion
        self.shift = False
        self._end_word()

    def phrase(self, text: str) -> None:
        self._end_word()
        self.backend.type_text(text)


class PynputKeyboardBackend:
    """Backend real. En Windows pynput usa SendInput (también para ñ y tildes)."""

    def __init__(self) -> None:
        from pynput import keyboard

        self._controller = keyboard.Controller()
        self._ctrl = keyboard.Key.ctrl
        key = keyboard.Key
        self._keys = {
            SpecialKey.ENTER: key.enter,
            SpecialKey.BACKSPACE: key.backspace,
            SpecialKey.DELETE: key.delete,
            SpecialKey.TAB: key.tab,
            SpecialKey.ESC: key.esc,
            SpecialKey.LEFT: key.left,
            SpecialKey.RIGHT: key.right,
            SpecialKey.UP: key.up,
            SpecialKey.DOWN: key.down,
            SpecialKey.HOME: key.home,
            SpecialKey.END: key.end,
        }

    def type_text(self, text: str) -> None:
        self._controller.type(text)

    def tap(self, key: SpecialKey) -> None:
        self._controller.tap(self._keys[key])

    def shortcut(self, letter: str) -> None:
        with self._controller.pressed(self._ctrl):
            self._controller.tap(letter)
