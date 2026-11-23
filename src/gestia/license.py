"""Inicio de sesión y licencia (P3-62).

La cuenta es la misma de la landing (un solo proyecto de Supabase). Al iniciar sesión, la app
activa el equipo con ``activate_device``, que exige la compra (P3-63). Después funciona sin
internet: solo vuelve a validar la licencia cuando pasan ``VALID_DAYS`` días.

Se guarda, cifrado con DPAPI de Windows (solo la misma cuenta de Windows puede leerlo):
el correo, el token de renovación y la fecha de la última validación. Nunca la contraseña.

La URL y la clave publicable de Supabase son públicas por diseño (RLS decide qué ve cada
cuenta). La clave ``service_role`` nunca va en la app.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
import platform
import sys
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

LOGGER = logging.getLogger(__name__)

SUPABASE_URL = "https://xrifigexqggmbswmljqy.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_25IBM6E74kTVKZbKrqmKww_ZLBZcb69"
# Dirección de la landing, para los enlaces «Crear cuenta» y «Comprar». Vacía: solo texto.
LANDING_URL = os.environ.get("GESTIA_LANDING_URL", "")
VALID_DAYS = 30
# En los últimos días del plazo, la app intenta renovar sola al abrirse (si hay internet).
RENEW_BEFORE_DAYS = 7
TIMEOUT_S = 8
LICENSE_FILE = "licencia.bin"


class LicenseErrorKind(StrEnum):
    CREDENTIALS = "credentials"
    NOT_CONFIRMED = "not_confirmed"
    NO_PURCHASE = "no_purchase"
    DEVICE_LIMIT = "device_limit"
    SESSION_EXPIRED = "session_expired"
    NETWORK = "network"
    SERVER = "server"


ERROR_TEXT = {
    LicenseErrorKind.CREDENTIALS: "El correo o la contraseña no son correctos.",
    LicenseErrorKind.NOT_CONFIRMED: (
        "Todavía no confirmaste tu correo. Abre el enlace que te enviamos y vuelve a intentarlo."
    ),
    LicenseErrorKind.NO_PURCHASE: (
        "Tu cuenta aún no tiene licencia. Cómprala en la web de GestIA (Mi cuenta) y vuelve a "
        "iniciar sesión."
    ),
    LicenseErrorKind.DEVICE_LIMIT: (
        "Tu licencia ya está activada en 3 computadoras. Quita una desde «Mi cuenta» en la web."
    ),
    LicenseErrorKind.SESSION_EXPIRED: "Tu sesión caducó. Vuelve a iniciar sesión.",
    LicenseErrorKind.NETWORK: (
        "No hay conexión a internet. Conéctate para validar la licencia (solo hace falta una vez "
        f"cada {VALID_DAYS} días)."
    ),
    LicenseErrorKind.SERVER: "El servicio de licencias no responde. Inténtalo en unos minutos.",
}


class LicenseError(Exception):
    def __init__(self, kind: LicenseErrorKind, detail: str = "") -> None:
        super().__init__(detail or ERROR_TEXT[kind])
        self.kind = kind

    @property
    def message(self) -> str:
        return ERROR_TEXT[self.kind]


# --- Transporte HTTP -------------------------------------------------------------------------


class Transport(Protocol):
    def post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> tuple[int, Any]:
        """Devuelve el código HTTP y el JSON de la respuesta; lanza OSError sin conexión."""
        ...


class UrllibTransport:
    """Transporte real con la biblioteca estándar (sin dependencias nuevas)."""

    def post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> tuple[int, Any]:
        if not url.startswith("https://"):
            raise ValueError("Solo se permiten conexiones HTTPS")
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310  # esquema validado arriba
            url, data=data, method="POST", headers={**headers, "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
                return response.status, _json(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _json(exc.read())


def _json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


# --- Cliente de Supabase ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Session:
    access_token: str
    refresh_token: str
    email: str


class SupabaseClient:
    def __init__(
        self,
        transport: Transport,
        url: str = SUPABASE_URL,
        key: str = SUPABASE_PUBLISHABLE_KEY,
    ) -> None:
        self.transport, self.url, self.key = transport, url.rstrip("/"), key

    def _post(self, path: str, body: dict[str, Any], token: str | None = None) -> Any:
        headers = {"apikey": self.key, "Authorization": f"Bearer {token or self.key}"}
        try:
            status, payload = self.transport.post(f"{self.url}{path}", headers, body)
        except OSError as exc:  # sin red, DNS, tiempo agotado, TLS
            raise LicenseError(LicenseErrorKind.NETWORK, str(exc)) from exc
        if 200 <= status < 300:
            return payload
        text = json.dumps(payload).lower() if payload else ""
        if "email_not_confirmed" in text or "email not confirmed" in text:
            raise LicenseError(LicenseErrorKind.NOT_CONFIRMED)
        if "3 equipos" in text:
            raise LicenseError(LicenseErrorKind.DEVICE_LIMIT)
        if status in (400, 401, 403):
            kind = (
                LicenseErrorKind.CREDENTIALS
                if "grant_type=password" in path
                else LicenseErrorKind.SESSION_EXPIRED
            )
            raise LicenseError(kind, f"HTTP {status}")
        raise LicenseError(LicenseErrorKind.SERVER, f"HTTP {status}")

    @staticmethod
    def _session(payload: Any) -> Session:
        try:
            return Session(
                str(payload["access_token"]),
                str(payload["refresh_token"]),
                str(payload.get("user", {}).get("email", "")),
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise LicenseError(LicenseErrorKind.SERVER, "respuesta sin sesión") from exc

    def sign_in(self, email: str, password: str) -> Session:
        payload = self._post(
            "/auth/v1/token?grant_type=password", {"email": email, "password": password}
        )
        return self._session(payload)

    def refresh(self, refresh_token: str) -> Session:
        payload = self._post(
            "/auth/v1/token?grant_type=refresh_token", {"refresh_token": refresh_token}
        )
        return self._session(payload)

    def activate_device(self, access_token: str, device_hash: str, label: str) -> dict[str, Any]:
        payload = self._post(
            "/rest/v1/rpc/activate_device",
            {"p_device_hash": device_hash, "p_label": label[:80]},
            token=access_token,
        )
        if not isinstance(payload, dict):
            raise LicenseError(LicenseErrorKind.SERVER, "respuesta inesperada")
        if not payload.get("licensed"):
            raise LicenseError(LicenseErrorKind.NO_PURCHASE)
        return payload


# --- Estado guardado -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LicenseState:
    email: str
    refresh_token: str
    validated_at: datetime

    def expires_at(self) -> datetime:
        return self.validated_at + timedelta(days=VALID_DAYS)

    def is_valid(self, now: datetime) -> bool:
        # Un reloj atrasado por debajo de la última validación también obliga a validar.
        return self.validated_at - timedelta(minutes=5) <= now < self.expires_at()

    def days_left(self, now: datetime) -> int:
        return max(0, (self.expires_at() - now).days)

    def to_dict(self) -> dict[str, str]:
        return {
            "email": self.email,
            "refresh_token": self.refresh_token,
            "validated_at": self.validated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LicenseState:
        validated_at = datetime.fromisoformat(str(raw["validated_at"]))
        if validated_at.tzinfo is None:
            raise ValueError("fecha sin zona horaria")
        return cls(str(raw["email"]), str(raw["refresh_token"]), validated_at)


class Protector(Protocol):
    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, data: bytes) -> bytes: ...


class DpapiProtector:
    """Cifra con la cuenta de Windows (CryptProtectData): otro usuario o equipo no lo lee."""

    _ENTROPY = b"GestIA-licencia-v1"

    def _call(self, function: str, data: bytes) -> bytes:
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        def blob(raw: bytes) -> tuple[Blob, Any]:
            buffer = ctypes.create_string_buffer(raw, len(raw))
            return Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        source, _keep = blob(data)
        entropy, _keep_entropy = blob(self._ENTROPY)
        result = Blob()
        ok = getattr(crypt32, function)(
            ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0, ctypes.byref(result)
        )
        if not ok:
            raise OSError("DPAPI no pudo procesar la licencia")
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            kernel32.LocalFree(result.pbData)

    def protect(self, data: bytes) -> bytes:
        return self._call("CryptProtectData", data)

    def unprotect(self, data: bytes) -> bytes:
        return self._call("CryptUnprotectData", data)


class PlainProtector:
    """Fuera de Windows (desarrollo y pruebas): sin cifrado, solo codificado."""

    def protect(self, data: bytes) -> bytes:
        return base64.b64encode(data)

    def unprotect(self, data: bytes) -> bytes:
        return base64.b64decode(data, validate=True)


def default_protector() -> Protector:
    return DpapiProtector() if sys.platform == "win32" else PlainProtector()


class LicenseStore:
    def __init__(self, path: Path, protector: Protector | None = None) -> None:
        self.path = path
        self.protector = protector or default_protector()

    def load(self) -> LicenseState | None:
        try:
            raw = self.protector.unprotect(self.path.read_bytes())
            return LicenseState.from_dict(json.loads(raw.decode("utf-8")))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Archivo dañado, copiado de otro equipo o editado: hay que volver a iniciar sesión.
            LOGGER.warning("Licencia guardada no válida: %s", exc)
            return None

    def save(self, state: LicenseState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = self.protector.protect(json.dumps(state.to_dict()).encode("utf-8"))
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, self.path)

    def clear(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()


# --- Identificador del equipo ----------------------------------------------------------------


def machine_id() -> str:
    """MachineGuid de Windows (estable entre reinicios); fuera de Windows, la MAC."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        except OSError:
            LOGGER.warning("No se pudo leer MachineGuid; se usa la MAC")
    return f"{uuid.getnode():012x}"


def device_hash(identifier: str | None = None) -> str:
    """SHA-256 del identificador: la base nunca recibe datos del equipo en claro."""
    raw = identifier if identifier is not None else machine_id()
    return hashlib.sha256(f"gestia:{raw}".encode()).hexdigest()


def device_label() -> str:
    return (platform.node() or "Computadora")[:80]


# --- Lógica de licencia ----------------------------------------------------------------------


class LicenseStatus(StrEnum):
    VALID = "valid"  # puede usarse sin internet
    REVALIDATE = "revalidate"  # pasaron los 30 días: hace falta internet
    LOGIN = "login"  # no hay sesión guardada


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LicenseManager:
    def __init__(
        self,
        client: SupabaseClient,
        store: LicenseStore,
        device: str | None = None,
        label: str | None = None,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.client, self.store, self.clock = client, store, clock
        self.device = device or device_hash()
        self.label = label or device_label()
        self.state = store.load()

    def status(self) -> LicenseStatus:
        if self.state is None:
            return LicenseStatus.LOGIN
        return (
            LicenseStatus.VALID if self.state.is_valid(self.clock()) else LicenseStatus.REVALIDATE
        )

    def _activate(self, session: Session, email: str) -> LicenseState:
        self.client.activate_device(session.access_token, self.device, self.label)
        state = LicenseState(session.email or email, session.refresh_token, self.clock())
        self.store.save(state)
        self.state = state
        return state

    def login(self, email: str, password: str) -> LicenseState:
        email = email.strip().lower()
        session = self.client.sign_in(email, password)
        return self._activate(session, email)

    def revalidate(self) -> LicenseState:
        """Renueva con el token guardado. Sin red lanza NETWORK y el estado no cambia."""
        if self.state is None:
            raise LicenseError(LicenseErrorKind.SESSION_EXPIRED)
        try:
            session = self.client.refresh(self.state.refresh_token)
            return self._activate(session, self.state.email)
        except LicenseError as exc:
            if exc.kind in (LicenseErrorKind.SESSION_EXPIRED, LicenseErrorKind.NO_PURCHASE):
                # El token ya no sirve o la licencia se retiró: se pide iniciar sesión otra vez.
                self.logout()
            raise

    def try_renew(self) -> bool:
        """Al abrir: si quedan pocos días y hay internet, renueva sin molestar."""
        if self.state is None or self.status() is not LicenseStatus.VALID:
            return False
        if self.state.days_left(self.clock()) > RENEW_BEFORE_DAYS:
            return False
        try:
            self.revalidate()
        except LicenseError as exc:
            LOGGER.info("No se renovó la licencia ahora: %s", exc.kind)
            return False
        return True

    def logout(self) -> None:
        self.store.clear()
        self.state = None


def license_required(installed: bool, environ: dict[str, str] | None = None) -> bool:
    """La versión instalada siempre pide licencia; en desarrollo, solo si se pide."""
    env = os.environ if environ is None else environ
    return installed or env.get("GESTIA_REQUIRE_LICENSE") == "1"


def create_manager(data_dir: Path, transport: Transport | None = None) -> LicenseManager:
    client = SupabaseClient(transport or UrllibTransport())
    return LicenseManager(client, LicenseStore(data_dir / LICENSE_FILE))
