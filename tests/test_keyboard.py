import pytest

from gestia.keyboard import (
    GRID_COLUMNS,
    GRID_ROWS,
    LAYOUTS,
    MIN_KEY_SIZE,
    KeyboardSettings,
    Layout,
    Shortcut,
    SpecialKey,
    TypingSession,
    fit_key_size,
)
from gestia.prediction import WordPredictor


class FakeKeyboard:
    def __init__(self) -> None:
        self.text = ""
        self.calls: list[tuple] = []

    def type_text(self, text: str) -> None:
        self.text += text
        self.calls.append(("type", text))

    def tap(self, key: SpecialKey) -> None:
        if key is SpecialKey.BACKSPACE:
            self.text = self.text[:-1]
        elif key is SpecialKey.ENTER:
            self.text += "\n"
        self.calls.append(("tap", key))

    def shortcut(self, letter: str) -> None:
        self.calls.append(("ctrl", letter))


def session(vocabulary: dict | None = None) -> tuple[TypingSession, FakeKeyboard, list]:
    backend, learned = FakeKeyboard(), []
    return TypingSession(backend, WordPredictor(vocabulary), learned.append), backend, learned


def write(typing: TypingSession, text: str) -> None:
    for char in text:
        typing.space() if char == " " else typing.press_char(char)


def test_keys_write_into_the_active_application() -> None:
    typing, backend, _ = session()
    write(typing, "hola, año 2")
    typing.press_special(SpecialKey.ENTER)
    assert backend.text == "hola, año 2\n"


def test_suggestion_completes_the_word() -> None:
    typing, backend, learned = session()
    write(typing, "gra")
    assert "gracias" in typing.suggestions()
    typing.choose("gracias")
    assert backend.text == "gracias "
    assert typing.word == "" and learned == ["gracias"]


def test_suggestion_with_accent_rewrites_the_word() -> None:
    typing, backend, _ = session()
    write(typing, "mie")
    typing.choose("miércoles")
    assert backend.text == "miércoles "
    assert backend.calls.count(("tap", SpecialKey.BACKSPACE)) == 3


def test_written_word_is_learned_and_then_suggested() -> None:
    vocabulary: dict[str, int] = {}
    typing, _, _ = session(vocabulary)
    write(typing, "zumbido zumbido ")
    write(typing, "zum")
    assert typing.suggestions()[0] == "zumbido"


def test_backspace_and_cursor_keys_update_the_current_word() -> None:
    typing, backend, learned = session()
    write(typing, "hoka")
    typing.press_special(SpecialKey.BACKSPACE)
    typing.press_special(SpecialKey.BACKSPACE)
    write(typing, "la")
    assert typing.word == "hola"
    typing.press_special(SpecialKey.LEFT)
    assert typing.word == ""
    typing.space()
    assert learned == []  # Tras mover el cursor no se aprende un trozo de palabra.


def test_shift_is_one_shot_and_caps_lock_persists() -> None:
    typing, backend, _ = session()
    typing.toggle_shift()
    write(typing, "ab")
    typing.toggle_caps()
    write(typing, "cd")
    typing.toggle_shift()  # Con Bloq Mayús, Mayús escribe una minúscula.
    write(typing, "e")
    typing.toggle_caps()
    write(typing, "f")
    assert backend.text == "AbCDef"


def test_shortcuts_send_ctrl_combinations() -> None:
    typing, backend, _ = session()
    write(typing, "ho")
    for shortcut in (Shortcut.SELECT_ALL, Shortcut.COPY, Shortcut.PASTE, Shortcut.CUT,
                     Shortcut.UNDO):
        typing.press_shortcut(shortcut)
    assert [call[1] for call in backend.calls if call[0] == "ctrl"] == list("acvxz")
    assert typing.word == ""


def test_frequent_phrase_is_written_in_one_selection() -> None:
    typing, backend, learned = session()
    write(typing, "casa")
    typing.phrase(" Necesito ayuda, por favor.")
    assert backend.text == "casa Necesito ayuda, por favor."
    assert learned == ["casa"]


def test_layouts_have_the_same_shape_and_all_spanish_letters() -> None:
    for layout in Layout:
        rows = LAYOUTS[layout]
        assert all(len(row) == 10 for row in rows)
        letters = set("".join(rows))
        assert set("abcdefghijklmnñopqrstuvwxyzáéíóú") <= letters
    assert len(LAYOUTS[Layout.QWERTY]) == len(LAYOUTS[Layout.ABC])


def test_key_size_shrinks_to_fit_the_screen() -> None:
    assert fit_key_size(56, 1920, 1040) == 56
    size = fit_key_size(140, 1366, 728)
    assert size < 140
    assert size * GRID_COLUMNS + 4 * (GRID_COLUMNS - 1) + 32 <= 1366
    assert size * GRID_ROWS + 4 * (GRID_ROWS - 1) + 32 <= 728
    assert fit_key_size(80, 300, 200) == MIN_KEY_SIZE


def test_settings_round_trip_and_validation() -> None:
    settings = KeyboardSettings(Layout.ABC, 72, ["Hola"], {"gestia": 3})
    assert KeyboardSettings.from_dict(settings.to_dict()) == settings
    assert KeyboardSettings.from_dict({}).layout is Layout.QWERTY
    with pytest.raises(ValueError):
        KeyboardSettings.from_dict({"key_size": 5})
    with pytest.raises(ValueError):
        KeyboardSettings.from_dict({"layout": "dvorak"})
    with pytest.raises(ValueError):
        KeyboardSettings.from_dict({"phrases": ["  "]})
