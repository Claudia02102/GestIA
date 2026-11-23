"""Confirmación del gesto de auxilio (P3-66).

Ventana grande, siempre encima y sin tomar el foco (como el menú de acciones rápidas): así,
al confirmar, WhatsApp queda en primer plano para recibir el Enter que envía el mensaje.
Los botones son grandes para pulsarlos con el puntero de la cabeza; también se confirma
abriendo la boca. La lógica (tiempo límite, gestos) está en ``emergency.py``.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gestia import theme
from gestia.ui_keyboard import _no_activate

BUTTON_SIZE = (220, 72)


class EmergencyWindow(QWidget):
    confirm_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("GestIA — Auxilio")
        self._native_done = False
        p = theme.current()
        self.setStyleSheet(
            theme.keyboard_stylesheet(p)
            + f"QWidget#auxilio {{ background: {p.surface}; border: 3px solid {p.danger};"
            " border-radius: 16px; }"
            " QLabel { background: transparent; border: none; }"
            " QPushButton { font-size: 20px; font-weight: 700; }"
        )
        self.setObjectName("auxilio")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("font-size: 17px;")
        self.countdown = QLabel()
        self.countdown.setStyleSheet(f"font-size: 17px; color: {p.text_muted};")

        self.confirm_button = QPushButton("Sí, enviar")
        self.confirm_button.setProperty("role", "active")
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setProperty("role", "special")
        for button in (self.confirm_button, self.cancel_button):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setFixedSize(*BUTTON_SIZE)
        self.confirm_button.clicked.connect(self.confirm_clicked)
        self.cancel_button.clicked.connect(self.cancel_clicked)

        buttons = QHBoxLayout()
        buttons.addWidget(self.confirm_button)
        buttons.addWidget(self.cancel_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        for widget in (self.title, self.detail, self.countdown):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        self.setFixedWidth(560)

    def ask(self, contact: str, test: bool = False) -> None:
        prefix = "Prueba: " if test else ""
        self.title.setText(f"{prefix}¿Enviar mensaje de auxilio a {contact}?")
        self.detail.setText("Abra la boca o pulse «Sí, enviar» para confirmar.")
        self.confirm_button.show()
        self.cancel_button.setText("Cancelar")
        self.show()
        self.raise_()

    def set_seconds(self, seconds: int) -> None:
        self.countdown.setText(f"Se cancela sola en {seconds} s si no hace nada.")

    def inform(self, title: str, detail: str) -> None:
        """Resultado (enviado, cancelado o error): solo queda «Cerrar»."""
        self.title.setText(title)
        self.detail.setText(detail)
        self.countdown.clear()
        self.confirm_button.hide()
        self.cancel_button.setText("Cerrar")

    def _place(self) -> None:
        """Arriba y al centro: visible sin tapar la parte baja (teclado virtual)."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        size = self.sizeHint()
        self.move(QPoint(area.x() + (area.width() - size.width()) // 2, area.y() + 40))

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._native_done and sys.platform == "win32":
            self._native_done = True
            _no_activate(int(self.winId()))
        self._place()
