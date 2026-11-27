"""Ventanas de privacidad (consentimiento de métricas) y de comentarios (P3-30)."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gestia.impact import FEEDBACK_CATEGORIES, MAX_MESSAGE, ImpactService

WHAT_IS_SENT = (
    "<b>Qué se envía</b> (una vez al día, solo con tu permiso): cuántas sesiones y minutos usaste "
    "GestIA, cuántas veces usaste cada acción (clic, desplazamiento…) y funciones como el teclado, "
    "la versión de la app y si es Windows 10 u 11. Va con un número aleatorio de esta "
    "instalación, que no está ligado a tu cuenta ni a tu equipo."
)
WHAT_IS_NOT_SENT = (
    "<b>Nunca se envía</b>: imágenes ni video de la cámara, tu rostro, tu nombre, tu correo, "
    "tus perfiles, lo que escribes, tus frases ni las aplicaciones que usas."
)
WHY = (
    "Estas métricas ayudan a las organizaciones aliadas a medir el impacto de GestIA y a "
    "decidir qué mejorar primero. Puedes cambiar de opinión cuando quieras desde «Privacidad»."
)


def _paragraph(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


class PrivacyDialog(QDialog):
    """Consentimiento de métricas. ``first_time`` muestra la pregunta con dos botones."""

    def __init__(
        self, service: ImpactService, first_time: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("GestIA — privacidad y métricas de impacto")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        title = QLabel(
            "¿Nos ayudas a mejorar GestIA?" if first_time else "Métricas de uso anónimas"
        )
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)
        for text in (WHY, WHAT_IS_SENT, WHAT_IS_NOT_SENT):
            layout.addWidget(_paragraph(text))

        self.preview_button = QPushButton("Ver exactamente qué se envía")
        self.preview_button.setCheckable(True)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(220)
        self.preview.hide()
        self.preview_button.toggled.connect(self._toggle_preview)
        layout.addWidget(self.preview_button)
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        buttons.addStretch()
        if first_time:
            self.consent_check = None
            no = QPushButton("No, gracias")
            no.clicked.connect(lambda: self._decide(False))
            yes = QPushButton("Sí, compartir métricas anónimas")
            yes.setProperty("primary", True)
            yes.clicked.connect(lambda: self._decide(True))
            buttons.addWidget(no)
            buttons.addWidget(yes)
        else:
            self.consent_check = QCheckBox("Compartir métricas de uso anónimas")
            self.consent_check.setChecked(service.enabled)
            self.consent_check.toggled.connect(self._decide_live)
            layout.addWidget(self.consent_check)
            self.status = QLabel()
            self.status.setObjectName("muted")
            layout.addWidget(self.status)
            self._show_status()
            close = QPushButton("Cerrar")
            close.clicked.connect(self.accept)
            buttons.addWidget(close)
        layout.addLayout(buttons)

    def _toggle_preview(self, show: bool) -> None:
        self.preview.setPlainText(json.dumps(self.service.preview(), ensure_ascii=False, indent=2))
        self.preview.setVisible(show)
        self.adjustSize()

    def _decide(self, consent: bool) -> None:
        self.service.set_consent(consent)
        self.accept()

    def _decide_live(self, consent: bool) -> None:
        self.service.set_consent(consent)
        self._show_status()
        if self.preview.isVisible():
            self._toggle_preview(True)

    def _show_status(self) -> None:
        pending = len(self.service.outbox.pending())
        text = (
            "Activado: los contadores del día se envían al día siguiente."
            if self.service.enabled
            else "Desactivado: no se registra ninguna métrica y se borró lo pendiente."
        )
        if pending:
            text += f" Pendientes de enviar (sin internet): {pending}."
        self.status.setText(text)


class FeedbackDialog(QDialog):
    """Comentario de la persona usuaria: tipo, mensaje y, si quiere, un correo de contacto."""

    def __init__(self, service: ImpactService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.item_id: str | None = None
        self.setWindowTitle("GestIA — enviar un comentario")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        title = QLabel("Cuéntanos cómo te va con GestIA")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(
            _paragraph(
                "Tu comentario llega al equipo de GestIA y a las organizaciones aliadas para "
                "priorizar mejoras. Se envía aunque no compartas métricas."
            )
        )
        kinds = QHBoxLayout()
        self.category_group = QButtonGroup(self)
        self.category_buttons: dict[str, QRadioButton] = {}
        for key, text in FEEDBACK_CATEGORIES.items():
            button = QRadioButton(text)
            self.category_group.addButton(button)
            self.category_buttons[key] = button
            kinds.addWidget(button)
        self.category_buttons["sugerencia"].setChecked(True)
        kinds.addStretch()
        layout.addLayout(kinds)
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText("Escribe aquí tu sugerencia, problema o experiencia…")
        self.message.setMinimumHeight(140)
        self.message.textChanged.connect(self._count)
        layout.addWidget(self.message)
        self.counter = QLabel()
        self.counter.setObjectName("muted")
        layout.addWidget(self.counter)
        self.contact = QLineEdit()
        self.contact.setPlaceholderText("Correo para responderte (opcional)")
        layout.addWidget(self.contact)
        layout.addWidget(
            _paragraph(
                "Si dejas tu correo, solo se usará para responderte. No escribas contraseñas ni "
                "datos de salud que no quieras compartir."
            )
        )
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #c0392b; font-weight: 600;")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        send = QPushButton("Enviar comentario")
        send.setProperty("primary", True)
        send.clicked.connect(self.submit)
        buttons.addWidget(cancel)
        buttons.addWidget(send)
        layout.addLayout(buttons)
        self._count()

    def category(self) -> str:
        return next(k for k, b in self.category_buttons.items() if b.isChecked())

    def _count(self) -> None:
        length = len(" ".join(self.message.toPlainText().split()))
        self.counter.setText(f"{length} / {MAX_MESSAGE} caracteres")

    def submit(self) -> None:
        try:
            self.item_id = self.service.submit_feedback(
                self.category(), self.message.toPlainText(), self.contact.text()
            )
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        except OSError as exc:
            self.error.setText(f"No se pudo guardar el comentario: {exc}")
            return
        self.accept()
