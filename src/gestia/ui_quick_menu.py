"""Menú flotante de acciones rápidas (P3-11).

Como el teclado virtual, flota encima y no toma el foco: así Alt+Tab, Alt+← o cerrar ventana
actúan sobre la aplicación activa y no sobre GestIA. Cerrar una ventana se confirma dentro del
mismo menú, sin abrir un diálogo que robe el foco.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QShowEvent
from PySide6.QtWidgets import QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from gestia import theme
from gestia.quick_actions import (
    NEEDS_CONFIRMATION,
    QUICK_ACTION_TEXT,
    QuickAction,
    SystemBackend,
    run_quick_action,
)
from gestia.ui_keyboard import _no_activate

BUTTON_WIDTH, BUTTON_HEIGHT = 220, 48
WINDOW_ACTIONS = (
    QuickAction.SWITCH_WINDOW,
    QuickAction.BACK,
    QuickAction.SHOW_DESKTOP,
    QuickAction.CLOSE_WINDOW,
)
APP_ACTIONS = (
    QuickAction.OPEN_EXPLORER,
    QuickAction.OPEN_BROWSER,
    QuickAction.OPEN_NOTEPAD,
    QuickAction.OPEN_CALCULATOR,
)


class QuickMenuWindow(QWidget):
    closed = Signal()

    def __init__(self, backend: SystemBackend) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("GestIA — Acciones rápidas")
        self.setStyleSheet(theme.keyboard_stylesheet(theme.current()))
        self.backend = backend
        self._native_done = False
        self.buttons: dict[QuickAction, QPushButton] = {}
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_actions())
        self.stack.addWidget(self._build_confirm())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.stack)
        self.adjustSize()

    # --- Construcción -----------------------------------------------------------------------

    def _button(self, text: str, role: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        if role:
            button.setProperty("role", role)
        font = button.font()
        font.setPixelSize(16)
        button.setFont(font)
        return button

    def _build_actions(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        for title, actions in (("Ventanas", WINDOW_ACTIONS), ("Abrir", APP_ACTIONS)):
            layout.addWidget(QLabel(f"<b>{title}</b>"))
            for action in actions:
                button = self._button(QUICK_ACTION_TEXT[action])
                button.clicked.connect(lambda _=False, a=action: self.choose(a))
                layout.addWidget(button)
                self.buttons[action] = button
        hide = self._button("Ocultar", "special")
        hide.clicked.connect(self.close)
        layout.addWidget(hide)
        return page

    def _build_confirm(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        question = QLabel("¿Cerrar la ventana activa?")
        question.setWordWrap(True)
        layout.addWidget(question)
        self.confirm_button = self._button("Sí, cerrar", "active")
        self.confirm_button.clicked.connect(self._confirm)
        self.cancel_button = self._button("Cancelar", "special")
        self.cancel_button.clicked.connect(self._cancel)
        layout.addWidget(self.confirm_button)
        layout.addWidget(self.cancel_button)
        layout.addStretch(1)
        return page

    def _place(self) -> None:
        """A la derecha y centrado en vertical: no tapa el teclado, que va abajo."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        size = self.frameGeometry().size() if self.isVisible() else self.sizeHint()
        x = area.x() + max(0, area.width() - size.width() - 8)
        y = area.y() + max(0, (area.height() - size.height()) // 2)
        self.move(QPoint(x, y))

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._native_done and sys.platform == "win32":
            self._native_done = True
            _no_activate(int(self.winId()))
        self._cancel()
        self._place()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)

    # --- Acciones ---------------------------------------------------------------------------

    @property
    def confirming(self) -> bool:
        return self.stack.currentIndex() == 1

    def choose(self, action: QuickAction) -> None:
        if action in NEEDS_CONFIRMATION:
            self.stack.setCurrentIndex(1)
            return
        run_quick_action(action, self.backend)

    def _confirm(self) -> None:
        self.stack.setCurrentIndex(0)
        run_quick_action(QuickAction.CLOSE_WINDOW, self.backend)

    def _cancel(self) -> None:
        self.stack.setCurrentIndex(0)
