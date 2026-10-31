"""Ventana del teclado virtual (HU-19 a HU-23).

Flota siempre encima y no toma el foco: las teclas se pulsan con el cursor de la cabeza y los
gestos de clic (o el clic por permanencia), y el texto llega a la aplicación activa.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QShowEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gestia.keyboard import (
    COLUMNS,
    LAYOUTS,
    SHORTCUT_TEXT,
    SPECIAL_TEXT,
    KeyboardBackend,
    KeyboardSettings,
    Shortcut,
    SpecialKey,
    TypingSession,
    fit_key_size,
)
from gestia.prediction import WordPredictor

SPACING = 4
SUGGESTIONS = 3
STYLE = """
QPushButton { background: #f1f5f9; color: #0f172a; border: 1px solid #94a3b8;
              border-radius: 6px; }
QPushButton:hover { background: #bfdbfe; border-color: #2563eb; }
QPushButton:pressed { background: #60a5fa; }
QPushButton[role="special"] { background: #e2e8f0; }
QPushButton[role="suggestion"] { background: #dcfce7; font-weight: 600; }
QPushButton[role="active"] { background: #fde68a; border-color: #ca8a04; }
QPushButton:disabled { color: #94a3b8; background: #f8fafc; }
"""

# Teclas especiales a la derecha de las filas de caracteres: (fila, columna, ancho).
SIDE_KEYS: tuple[tuple[SpecialKey, int, int, int], ...] = (
    (SpecialKey.BACKSPACE, 0, COLUMNS, 3),
    (SpecialKey.TAB, 1, COLUMNS, 1),
    (SpecialKey.ESC, 1, COLUMNS + 1, 1),
    (SpecialKey.DELETE, 1, COLUMNS + 2, 1),
    (SpecialKey.ENTER, 2, COLUMNS, 3),
    (SpecialKey.HOME, 3, COLUMNS, 1),
    (SpecialKey.UP, 3, COLUMNS + 1, 1),
    (SpecialKey.END, 3, COLUMNS + 2, 1),
    (SpecialKey.LEFT, 4, COLUMNS, 1),
    (SpecialKey.DOWN, 4, COLUMNS + 1, 1),
    (SpecialKey.RIGHT, 4, COLUMNS + 2, 1),
)


class KeyboardWindow(QWidget):
    learned = Signal(str)
    closed = Signal()

    def __init__(self, settings: KeyboardSettings, backend: KeyboardBackend) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("GestIA — Teclado")
        self.setStyleSheet(STYLE)
        self.backend = backend
        self.settings = settings
        self.session = TypingSession(backend, WordPredictor(settings.vocabulary), self.learned.emit)
        self.key_size = settings.key_size
        self._char_buttons: list[tuple[QPushButton, str]] = []
        self._suggestions: list[QPushButton] = []
        self._native_done = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._content: QWidget | None = None
        self._build()

    # --- Construcción -----------------------------------------------------------------------

    def _button(self, text: str, span: int = 1, role: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFixedSize(self.key_size * span + SPACING * (span - 1), self.key_size)
        if role:
            button.setProperty("role", role)
        font = button.font()
        font.setPixelSize(max(12, round(self.key_size * 0.36)))
        button.setFont(font)
        return button

    def _available(self) -> tuple[int, int]:
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        return area.width(), area.height()

    def _build(self) -> None:
        # HU-23: el tamaño pedido se reduce si el teclado no cabe en la pantalla.
        self.key_size = fit_key_size(self.settings.key_size, *self._available(), SPACING)
        if self._content is not None:
            self.layout().removeWidget(self._content)
            self._content.deleteLater()
        self._char_buttons, self._suggestions = [], []
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(SPACING)

        top = QGridLayout()
        top.setSpacing(SPACING)
        for index in range(SUGGESTIONS):
            button = self._button("", 3, "suggestion")
            button.clicked.connect(lambda _=False, i=index: self._choose(i))
            top.addWidget(button, 0, index * 3, 1, 3)
            self._suggestions.append(button)
        self.phrases_button = self._button("Frases", 2, "special")
        self.phrases_button.clicked.connect(self._toggle_phrases)
        top.addWidget(self.phrases_button, 0, 9, 1, 2)
        hide = self._button("Ocultar", 2, "special")
        hide.clicked.connect(self.close)
        top.addWidget(hide, 0, 11, 1, 2)
        outer.addLayout(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_keys())
        self.stack.addWidget(self._build_phrases())
        outer.addWidget(self.stack)
        self.layout().addWidget(content)
        self._content = content
        self._refresh()
        self.adjustSize()
        self._place()

    def _build_keys(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(SPACING)
        rows = LAYOUTS[self.settings.layout]
        for row, chars in enumerate(rows):
            for column, char in enumerate(chars):
                button = self._button(char)
                button.clicked.connect(lambda _=False, c=char: self._char(c))
                grid.addWidget(button, row, column)
                self._char_buttons.append((button, char))
        for key, row, column, span in SIDE_KEYS:
            button = self._button(SPECIAL_TEXT[key], span, "special")
            button.clicked.connect(lambda _=False, k=key: self._special(k))
            grid.addWidget(button, row, column, 1, span)

        row = len(rows)
        self.shift_button = self._button("⇧ Mayús", 2, "special")
        self.shift_button.clicked.connect(self._shift)
        self.caps_button = self._button("Bloq Mayús", 2, "special")
        self.caps_button.clicked.connect(self._caps)
        space = self._button("Espacio", 9, "special")
        space.clicked.connect(self._space)
        grid.addWidget(self.shift_button, row, 0, 1, 2)
        grid.addWidget(self.caps_button, row, 2, 1, 2)
        grid.addWidget(space, row, 4, 1, 9)
        for index, shortcut in enumerate(Shortcut):
            button = self._button(SHORTCUT_TEXT[shortcut], 2, "special")
            button.setToolTip(f"Ctrl+{str(shortcut).upper()}")
            button.clicked.connect(lambda _=False, s=shortcut: self._shortcut(s))
            grid.addWidget(button, row + 1, index * 2, 1, 2)
        return page

    def _build_phrases(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setSpacing(SPACING)
        for index, phrase in enumerate(self.settings.phrases):
            button = self._button(phrase, 6)
            button.setFixedWidth(self.key_size * 6 + SPACING * 5)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _=False, p=phrase: self._phrase(p))
            grid.addWidget(button, index // 2, index % 2)
        grid.setRowStretch(len(self.settings.phrases) // 2 + 1, 1)
        scroll = QScrollArea()
        scroll.setWidget(page)
        scroll.setWidgetResizable(True)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return scroll

    def _place(self) -> None:
        """Abajo y centrado, siempre dentro del área disponible de la pantalla."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        size = self.frameGeometry().size() if self.isVisible() else self.sizeHint()
        x = area.x() + max(0, (area.width() - size.width()) // 2)
        y = area.y() + max(0, area.height() - size.height() - 8)
        self.move(QPoint(x, y))

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._native_done and sys.platform == "win32":
            self._native_done = True
            _no_activate(int(self.winId()))
        self._place()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)

    # --- Ajustes ----------------------------------------------------------------------------

    def set_settings(self, settings: KeyboardSettings) -> None:
        """Aplica distribución, tamaño, frases o un perfil nuevo sin cerrar el teclado."""
        if settings is not self.settings:
            self.session = TypingSession(
                self.backend, WordPredictor(settings.vocabulary), self.learned.emit
            )
        self.settings = settings
        page = self.stack.currentIndex()
        self._build()
        self.stack.setCurrentIndex(page)

    # --- Acciones ---------------------------------------------------------------------------

    def _char(self, char: str) -> None:
        self.session.press_char(char)
        self._refresh()

    def _space(self) -> None:
        self.session.space()
        self._refresh()

    def _special(self, key: SpecialKey) -> None:
        self.session.press_special(key)
        self._refresh()

    def _shortcut(self, shortcut: Shortcut) -> None:
        self.session.press_shortcut(shortcut)
        self._refresh()

    def _shift(self) -> None:
        self.session.toggle_shift()
        self._refresh()

    def _caps(self) -> None:
        self.session.toggle_caps()
        self._refresh()

    def _choose(self, index: int) -> None:
        text = self._suggestions[index].text()
        if text:
            self.session.choose(text)
            self._refresh()

    def _phrase(self, phrase: str) -> None:
        self.session.phrase(phrase)
        self.stack.setCurrentIndex(0)
        self._refresh()

    def _toggle_phrases(self) -> None:
        self.stack.setCurrentIndex(1 - self.stack.currentIndex())
        self._refresh()

    def _refresh(self) -> None:
        upper = self.session.upper
        for button, char in self._char_buttons:
            button.setText(char.upper() if upper else char)
        suggestions = self.session.suggestions(SUGGESTIONS)
        for index, button in enumerate(self._suggestions):
            text = suggestions[index] if index < len(suggestions) else ""
            button.setText(text)
            button.setEnabled(bool(text))
        if hasattr(self, "shift_button"):
            for button, on in (
                (self.shift_button, self.session.shift),
                (self.caps_button, self.session.caps),
            ):
                button.setProperty("role", "active" if on else "special")
                button.style().unpolish(button)
                button.style().polish(button)
        on_phrases = self.stack.currentIndex() == 1
        self.phrases_button.setText("Teclas" if on_phrases else "Frases")


def _no_activate(hwnd: int) -> None:
    """Windows: la ventana no se activa al hacer clic, así el foco sigue en la otra app."""
    import ctypes

    gwl_exstyle, ws_ex_noactivate = -20, 0x08000000
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    style = user32.GetWindowLongW(hwnd, gwl_exstyle)
    user32.SetWindowLongW(hwnd, gwl_exstyle, style | ws_ex_noactivate)
