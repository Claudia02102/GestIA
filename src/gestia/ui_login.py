"""Ventana de inicio de sesión y validación de la licencia (P3-62).

Aparece antes de la ventana principal solo cuando hace falta: la primera vez, o cuando pasaron
30 días desde la última validación. La lógica está en ``license.py``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gestia import theme
from gestia.license import (
    LANDING_URL,
    VALID_DAYS,
    LicenseError,
    LicenseErrorKind,
    LicenseManager,
    LicenseStatus,
)

FIELD_HEIGHT = 44


class LoginDialog(QDialog):
    def __init__(self, manager: LicenseManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("GestIA — Iniciar sesión")
        self.setStyleSheet(theme.stylesheet(theme.current()))
        self.setMinimumWidth(460)

        title = QLabel("<h2>Bienvenido a GestIA</h2>")
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_form())
        self.stack.addWidget(self._build_revalidate())
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {theme.current().danger}; font-size: 14px;")
        self.error.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(self.stack)
        layout.addWidget(self.error)
        if self.manager.state is not None:
            self.stack.setCurrentIndex(1)
            self.email.setText(self.manager.state.email)

    # --- Construcción -----------------------------------------------------------------------

    def _build_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        intro = QLabel(
            "Inicia sesión con la cuenta que usaste en la web para comprar GestIA. Después la app "
            f"funciona sin internet y solo pide validar la licencia una vez cada {VALID_DAYS} días."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Correo electrónico")
        self.email.setAccessibleName("Correo electrónico")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Contraseña")
        self.password.setAccessibleName("Contraseña")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self.submit)
        for field in (self.email, self.password):
            field.setMinimumHeight(FIELD_HEIGHT)
            layout.addWidget(field)

        self.login_button = QPushButton("Iniciar sesión")
        self.login_button.setProperty("primary", True)
        self.login_button.setMinimumHeight(FIELD_HEIGHT)
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self.submit)
        layout.addWidget(self.login_button)

        row = QHBoxLayout()
        if LANDING_URL:
            account = QPushButton("Crear cuenta o comprar")
            account.clicked.connect(lambda: self.open_web("/cuenta/ingresar?modo=registro"))
            row.addWidget(account)
        else:
            hint = QLabel("¿Aún no tienes cuenta? Créala en la web de GestIA.")
            hint.setWordWrap(True)
            row.addWidget(hint, 1)
        exit_button = QPushButton("Salir")
        exit_button.clicked.connect(self.reject)
        row.addWidget(exit_button)
        layout.addLayout(row)
        return page

    def _build_revalidate(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.revalidate_text = QLabel(
            f"Pasaron {VALID_DAYS} días desde la última validación. Conéctate a internet y pulsa "
            "«Validar ahora»; no hace falta volver a escribir la contraseña."
        )
        self.revalidate_text.setWordWrap(True)
        layout.addWidget(self.revalidate_text)
        self.validate_button = QPushButton("Validar ahora")
        self.validate_button.setProperty("primary", True)
        self.validate_button.setMinimumHeight(FIELD_HEIGHT)
        self.validate_button.clicked.connect(self.revalidate)
        layout.addWidget(self.validate_button)
        row = QHBoxLayout()
        other = QPushButton("Usar otra cuenta")
        other.clicked.connect(self.show_form)
        row.addWidget(other)
        exit_button = QPushButton("Salir")
        exit_button.clicked.connect(self.reject)
        row.addWidget(exit_button)
        layout.addLayout(row)
        return page

    # --- Acciones ---------------------------------------------------------------------------

    def open_web(self, path: str) -> None:
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(LANDING_URL.rstrip("/") + path))

    def show_form(self) -> None:
        self.stack.setCurrentIndex(0)
        self.password.setFocus()

    def show_error(self, error: LicenseError) -> None:
        self.error.setText(error.message)
        self.error.show()
        if error.kind is LicenseErrorKind.SESSION_EXPIRED:
            self.show_form()

    def _busy(self, busy: bool) -> None:
        for button in (self.login_button, self.validate_button):
            button.setEnabled(not busy)
        if busy:
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
        else:
            QGuiApplication.restoreOverrideCursor()

    def submit(self) -> None:
        email, password = self.email.text().strip(), self.password.text()
        if "@" not in email or not password:
            self.error.setText("Escribe tu correo y tu contraseña.")
            self.error.show()
            return
        self._busy(True)
        try:
            self.manager.login(email, password)
        except LicenseError as exc:
            self.show_error(exc)
            return
        finally:
            self._busy(False)
            self.password.clear()
        self.accept()

    def revalidate(self) -> None:
        self._busy(True)
        try:
            self.manager.revalidate()
        except LicenseError as exc:
            self.show_error(exc)
            return
        finally:
            self._busy(False)
        self.accept()


def ensure_license(manager: LicenseManager) -> bool:
    """Verdadero si la app puede abrirse: licencia vigente o validada ahora."""
    status = manager.status()
    if status is LicenseStatus.VALID:
        manager.try_renew()
        return True
    if status is LicenseStatus.REVALIDATE:
        try:
            manager.revalidate()
            return True
        except LicenseError:
            pass  # sin red o sesión caducada: la ventana lo explica
    return LoginDialog(manager).exec() == QDialog.DialogCode.Accepted
