"""Gesto de auxilio con confirmación por WhatsApp (P3-66).

1. La persona mantiene las cejas levantadas ``hold_ms`` (3 s por defecto).
2. Aparece una confirmación grande: se confirma abriendo la boca o con el botón «Enviar»; se
   cancela con «Cancelar» o sola a los ``CONFIRM_TIMEOUT_MS`` (10 s). Así un gesto involuntario
   nunca envía nada.
3. Se abre WhatsApp Desktop en el chat del contacto de emergencia con el mensaje escrito y se
   envía. Sin WhatsApp Desktop, se abre WhatsApp Web con el mensaje listo para enviar.

Levantar las cejas sigue haciendo su acción normal (recentrar) si se sueltan antes de los 3 s:
mientras se mantienen, esa acción espera para no dispararse durante el gesto de auxilio.
No se llama por teléfono: solo se envía el mensaje (decisión del equipo).
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any, Protocol

from gestia.gestures import RELEASE_RATIO, GestureEvent, GestureId, GestureSettings

LOGGER = logging.getLogger(__name__)

TRIGGER_GESTURE = GestureId.BROW_RAISE
CONFIRM_GESTURE = GestureId.MOUTH_OPEN
DEFAULT_HOLD_MS = 3000
MIN_HOLD_MS, MAX_HOLD_MS = 2000, 6000
CONFIRM_TIMEOUT_MS = 10_000
MAX_MESSAGE = 300
DEFAULT_MESSAGE = (
    "Necesito ayuda. Este es un mensaje de auxilio enviado con GestIA. Por favor, comunícate "
    "conmigo o ven a verme."
)
# Perú: un celular de 9 dígitos que empieza en 9 recibe el código de país 51.
DEFAULT_COUNTRY_CODE = "51"


def normalize_phone(text: str) -> str:
    """Solo dígitos, con código de país. Vacío si no parece un número válido."""
    digits = re.sub(r"\D", "", text or "")
    if text.strip().startswith("00"):
        digits = digits[2:]
    if len(digits) == 9 and digits.startswith("9"):
        digits = DEFAULT_COUNTRY_CODE + digits
    return digits if 10 <= len(digits) <= 15 else ""


def whatsapp_uri(phone: str, message: str) -> str:
    return "whatsapp://send?" + urllib.parse.urlencode({"phone": phone, "text": message})


def web_uri(phone: str, message: str) -> str:
    return f"https://wa.me/{phone}?" + urllib.parse.urlencode({"text": message})


@dataclass(slots=True)
class EmergencySettings:
    enabled: bool = False
    phone: str = ""
    contact_name: str = ""
    message: str = DEFAULT_MESSAGE
    hold_ms: int = DEFAULT_HOLD_MS

    @property
    def ready(self) -> bool:
        return self.enabled and bool(normalize_phone(self.phone))

    def validate(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("El ajuste de auxilio debe ser verdadero o falso")
        for value in (self.phone, self.contact_name, self.message):
            if not isinstance(value, str):
                raise ValueError("Los datos del contacto de emergencia deben ser texto")
        if self.phone and not normalize_phone(self.phone):
            raise ValueError("El número de emergencia no es válido (incluye el código de país)")
        if len(self.contact_name) > 60:
            raise ValueError("El nombre del contacto admite hasta 60 caracteres")
        if not self.message.strip() or len(self.message) > MAX_MESSAGE:
            raise ValueError(f"El mensaje de auxilio debe tener entre 1 y {MAX_MESSAGE} caracteres")
        hold = self.hold_ms
        if isinstance(hold, bool) or not isinstance(hold, int):
            raise ValueError("El tiempo del gesto de auxilio debe ser un número entero")
        if not MIN_HOLD_MS <= hold <= MAX_HOLD_MS:
            raise ValueError(
                f"El gesto de auxilio debe sostenerse entre {MIN_HOLD_MS} y {MAX_HOLD_MS} ms"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EmergencySettings:
        if not isinstance(raw, dict):
            raise ValueError("Ajustes de auxilio no válidos")
        settings = cls(**raw)
        settings.validate()
        return settings


class EmergencyTrigger:
    """Reconoce las cejas sostenidas y retiene la acción normal de ese gesto mientras tanto."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._since_ms: int | None = None
        self._pending: GestureEvent | None = None
        self._fired = False

    @property
    def holding(self) -> bool:
        return self._since_ms is not None

    def update(
        self,
        activations: Mapping[GestureId, float],
        events: Iterable[GestureEvent],
        settings: Mapping[GestureId, GestureSettings],
        emergency: EmergencySettings,
        timestamp_ms: int,
    ) -> tuple[list[GestureEvent], bool]:
        """Devuelve los eventos que siguen su curso y si se completó el gesto de auxilio."""
        events = list(events)
        gesture_settings = settings.get(TRIGGER_GESTURE)
        if not emergency.ready or gesture_settings is None or TRIGGER_GESTURE not in activations:
            pending, self._pending = self._pending, None
            self._since_ms, self._fired = None, False
            return ([pending] if pending else []) + events, False

        passed: list[GestureEvent] = []
        for event in events:
            if event.gesture is TRIGGER_GESTURE:
                self._pending = event  # espera a saber si es auxilio o la acción normal
            else:
                passed.append(event)

        value, threshold = activations[TRIGGER_GESTURE], gesture_settings.threshold
        if value >= threshold:
            if self._since_ms is None:
                self._since_ms = timestamp_ms
            if not self._fired and timestamp_ms - self._since_ms >= emergency.hold_ms:
                self._fired, self._pending = True, None
                return passed, True
        elif value < threshold * RELEASE_RATIO:
            self._since_ms, self._fired = None, False
            if self._pending is not None:
                # Se soltó antes de tiempo: era el gesto normal (recentrar).
                passed.insert(0, replace(self._pending, timestamp_ms=timestamp_ms))
                self._pending = None
        return passed, False


class ConfirmOutcome(StrEnum):
    WAITING = "waiting"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class EmergencyConfirmation:
    """Segunda comprobación: abrir la boca o pulsar «Enviar»; si no, se cancela a los 10 s."""

    def __init__(self, started_ms: int, timeout_ms: int = CONFIRM_TIMEOUT_MS) -> None:
        self.started_ms, self.timeout_ms = started_ms, timeout_ms
        self.outcome = ConfirmOutcome.WAITING

    def seconds_left(self, now_ms: int) -> int:
        return max(0, -(-(self.timeout_ms - (now_ms - self.started_ms)) // 1000))

    def feed(self, events: Iterable[GestureEvent], now_ms: int) -> ConfirmOutcome:
        """Consume los gestos: mientras se confirma, ninguno hace clic ni otra acción."""
        if self.outcome is not ConfirmOutcome.WAITING:
            return self.outcome
        if any(event.gesture is CONFIRM_GESTURE for event in events):
            self.outcome = ConfirmOutcome.CONFIRMED
        elif now_ms - self.started_ms >= self.timeout_ms:
            self.outcome = ConfirmOutcome.TIMED_OUT
        return self.outcome

    def confirm(self) -> None:
        if self.outcome is ConfirmOutcome.WAITING:
            self.outcome = ConfirmOutcome.CONFIRMED

    def cancel(self) -> None:
        if self.outcome is ConfirmOutcome.WAITING:
            self.outcome = ConfirmOutcome.CANCELLED


# --- Envío -----------------------------------------------------------------------------------


class MessengerBackend(Protocol):
    def open_uri(self, uri: str) -> bool:
        """Abre la dirección con su aplicación; falso si no hay ninguna registrada."""
        ...

    def foreground_title(self) -> str: ...
    def press_enter(self) -> None: ...


class SendResult(StrEnum):
    OPENED_APP = "opened_app"  # WhatsApp Desktop con el chat y el mensaje
    OPENED_WEB = "opened_web"  # sin WhatsApp Desktop: WhatsApp Web, falta pulsar enviar
    FAILED = "failed"


def open_chat(backend: MessengerBackend, settings: EmergencySettings) -> SendResult:
    phone = normalize_phone(settings.phone)
    if not phone:
        return SendResult.FAILED
    if backend.open_uri(whatsapp_uri(phone, settings.message)):
        return SendResult.OPENED_APP
    if backend.open_uri(web_uri(phone, settings.message)):
        return SendResult.OPENED_WEB
    return SendResult.FAILED


def press_send(backend: MessengerBackend) -> bool:
    """Pulsa Enter solo si WhatsApp está en primer plano (nunca en otra ventana)."""
    if "whatsapp" not in backend.foreground_title().lower():
        return False
    backend.press_enter()
    return True


class WindowsMessenger:
    """Backend real: ``os.startfile`` para la dirección, la API de Windows y pynput."""

    def open_uri(self, uri: str) -> bool:
        import os

        if not uri.startswith(("whatsapp://send?", "https://wa.me/")):
            raise ValueError("Dirección no permitida")
        if uri.startswith("whatsapp://") and not self._has_whatsapp():
            return False
        try:
            # Seguro: la dirección se arma solo con whatsapp_uri/web_uri (validada arriba).
            os.startfile(uri)  # type: ignore[attr-defined]  # noqa: S606  # solo en Windows
        except OSError:
            LOGGER.info("No hay aplicación para %s", uri.split("?")[0])
            return False
        return True

    @staticmethod
    def _has_whatsapp() -> bool:
        """WhatsApp Desktop registra el protocolo «whatsapp:»; sin él Windows abriría la Tienda."""
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "whatsapp"):
                return True
        except OSError:
            return False

    def foreground_title(self) -> str:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def press_enter(self) -> None:
        from pynput import keyboard

        keyboard.Controller().tap(keyboard.Key.enter)
