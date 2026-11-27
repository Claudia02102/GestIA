"""Métricas de impacto anónimas con consentimiento y comentarios (P3-30), sin dependencias de Qt.

- **Sin consentimiento no se registra nada**: ni contadores, ni archivos, ni envíos.
- Con consentimiento se cuentan solo números por día (sesiones, minutos de uso, cuántas veces
  se usó cada acción y cada función). Nunca imágenes, video, landmarks, nombres, correos,
  perfiles, frases, palabras escritas, aplicaciones abiertas ni rutas.
- El reporte de un día se envía al día siguiente con un identificador aleatorio de instalación
  (no se deriva del equipo ni de la cuenta y se borra al retirar el consentimiento).
- Los comentarios son un envío explícito de la persona y no dependen del consentimiento.

Todo lo que se va a enviar espera en un buzón local (``buzon.json``) y sale cuando hay
internet, a las funciones ``submit_usage_report`` y ``submit_feedback`` de Supabase.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import sys
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from gestia.gestures import Action

LOGGER = logging.getLogger(__name__)

SETTINGS_FILE = "privacidad.json"
USAGE_FILE = "uso_pendiente.json"
OUTBOX_FILE = "buzon.json"
REPORT_SCHEMA = 1
MAX_OUTBOX = 200
MAX_MESSAGE = 1000
MIN_MESSAGE = 3
MAX_CONTACT = 120

FEATURES = ("teclado", "acciones_rapidas", "calibracion", "tutorial_completado", "practica")
FEEDBACK_CATEGORIES = {
    "sugerencia": "Sugerencia",
    "problema": "Problema o error",
    "agradecimiento": "Me ayudó",
}
REPORT_KEYS = frozenset(
    {
        "schema",
        "install_id",
        "app_version",
        "os",
        "day",
        "sessions",
        "active_minutes",
        "actions",
        "features",
    }
)
FEEDBACK_KEYS = frozenset({"category", "message", "contact", "app_version", "os"})


def app_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("gestia")
    except PackageNotFoundError:  # ejecutable empaquetado sin metadatos
        from gestia import __version__

        return __version__


def os_family() -> str:
    """Solo la familia del sistema («Windows 11»): nunca el nombre ni la versión exacta."""
    if sys.platform == "win32":
        try:
            build = int(platform.version().split(".")[-1])
        except ValueError:
            build = 0
        return "Windows 11" if build >= 22000 else "Windows 10"
    return platform.system() or "Otro"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as exc:
        LOGGER.warning("Archivo de métricas no válido (%s): %s", path.name, exc)
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporary, path)


# --- Consentimiento --------------------------------------------------------------------------


@dataclass(slots=True)
class ImpactSettings:
    """``consent`` es None mientras no se ha preguntado (equivale a «no»)."""

    consent: bool | None = None
    install_id: str | None = None

    @property
    def enabled(self) -> bool:
        return self.consent is True

    @classmethod
    def load(cls, path: Path) -> ImpactSettings:
        raw = _read_json(path, {})
        consent = raw.get("consent") if isinstance(raw, dict) else None
        install_id = raw.get("install_id") if isinstance(raw, dict) else None
        if consent not in (True, False, None):
            consent = None
        if not isinstance(install_id, str) or not _UUID.fullmatch(install_id):
            install_id = None
        if consent is not True:
            install_id = None
        return cls(consent, install_id)

    def save(self, path: Path) -> None:
        _write_json(path, {"consent": self.consent, "install_id": self.install_id})


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


# --- Contadores diarios ----------------------------------------------------------------------


@dataclass(slots=True)
class DayUsage:
    sessions: int = 0
    active_seconds: int = 0
    actions: dict[str, int] = field(default_factory=dict)
    features: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessions": self.sessions,
            "active_seconds": self.active_seconds,
            "actions": dict(self.actions),
            "features": dict(self.features),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> DayUsage:
        actions = {str(k): int(v) for k, v in raw.get("actions", {}).items() if k in _ACTION_NAMES}
        features = {str(k): int(v) for k, v in raw.get("features", {}).items() if k in FEATURES}
        return cls(
            int(raw.get("sessions", 0)), int(raw.get("active_seconds", 0)), actions, features
        )


# Las mismas que acepta ``submit_usage_report`` en la base (migración de la landing). Si se
# añade una acción nueva, hay que sumarla aquí y en la migración; una prueba lo recuerda.
_ACTION_NAMES = frozenset(
    {
        "left_click",
        "right_click",
        "double_click",
        "drag",
        "pause",
        "recalibrate",
        "scroll",
        "quick_menu",
    }
)


def build_report(day: date, usage: DayUsage, install_id: str, version: str) -> dict[str, Any]:
    """Reporte anónimo de un día: solo las claves de ``REPORT_KEYS``."""
    report = {
        "schema": REPORT_SCHEMA,
        "install_id": install_id,
        "app_version": version[:20],
        "os": os_family(),
        "day": day.isoformat(),
        "sessions": usage.sessions,
        "active_minutes": round(usage.active_seconds / 60),
        "actions": {name: usage.actions[name] for name in sorted(usage.actions)},
        "features": {name: usage.features.get(name, 0) for name in FEATURES},
    }
    return report


class UsageTracker:
    """Cuenta el uso por día solo con consentimiento; sin él no guarda ni recuerda nada."""

    def __init__(
        self, path: Path, settings: ImpactSettings, today: Callable[[], date] = date.today
    ) -> None:
        self.path, self.settings, self.today = path, settings, today
        self._lock = threading.Lock()
        self.days: dict[str, DayUsage] = {}
        if settings.enabled:
            raw = _read_json(path, {})
            for key, item in raw.items() if isinstance(raw, dict) else ():
                try:
                    date.fromisoformat(key)
                    self.days[key] = DayUsage.from_dict(item)
                except (TypeError, ValueError, AttributeError):
                    continue

    def _day(self) -> DayUsage:
        return self.days.setdefault(self.today().isoformat(), DayUsage())

    def _changed(self) -> None:
        try:
            _write_json(self.path, {k: v.to_dict() for k, v in self.days.items()})
        except OSError as exc:
            LOGGER.warning("No se pudieron guardar las métricas: %s", exc)

    def record_session(self) -> None:
        if not self.settings.enabled:
            return
        with self._lock:
            self._day().sessions += 1
            self._changed()

    def record_action(self, action: Action) -> None:
        if not self.settings.enabled or str(action) not in _ACTION_NAMES:
            return
        with self._lock:
            actions = self._day().actions
            actions[str(action)] = actions.get(str(action), 0) + 1
            self._changed()

    def record_feature(self, name: str) -> None:
        if not self.settings.enabled or name not in FEATURES:
            return
        with self._lock:
            features = self._day().features
            features[name] = features.get(name, 0) + 1
            self._changed()

    def add_active_seconds(self, seconds: int, save: bool = False) -> None:
        """Se llama cada segundo de uso activo; se guarda en disco cada minuto."""
        if not self.settings.enabled or seconds <= 0:
            return
        with self._lock:
            self._day().active_seconds += seconds
            if save:
                self._changed()

    def flush(self) -> None:
        if self.settings.enabled:
            with self._lock:
                self._changed()

    def take_finished_days(self) -> list[tuple[date, DayUsage]]:
        """Días ya terminados (anteriores a hoy), que se quitan para enviarse."""
        if not self.settings.enabled:
            return []
        today = self.today().isoformat()
        with self._lock:
            done = sorted(key for key in self.days if key < today)
            taken = [(date.fromisoformat(key), self.days.pop(key)) for key in done]
            if taken:
                self._changed()
        return taken

    def clear(self) -> None:
        with self._lock:
            self.days = {}
            try:
                self.path.unlink(missing_ok=True)
            except OSError as exc:
                LOGGER.warning("No se pudieron borrar las métricas: %s", exc)


# --- Comentarios -----------------------------------------------------------------------------

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def build_feedback(category: str, message: str, contact: str, version: str) -> dict[str, Any]:
    """Valida un comentario; ``ValueError`` con un texto para mostrar si algo falta."""
    if category not in FEEDBACK_CATEGORIES:
        raise ValueError("Elige el tipo de comentario.")
    text = " ".join(message.split())
    if len(text) < MIN_MESSAGE:
        raise ValueError("Escribe tu comentario antes de enviarlo.")
    if len(text) > MAX_MESSAGE:
        raise ValueError(f"El comentario puede tener hasta {MAX_MESSAGE} caracteres.")
    contact = contact.strip()
    if contact and (len(contact) > MAX_CONTACT or not _EMAIL.fullmatch(contact)):
        raise ValueError("El correo de contacto no es válido (puedes dejarlo vacío).")
    return {
        "category": category,
        "message": text,
        "contact": contact or None,
        "app_version": version[:20],
        "os": os_family(),
    }


# --- Buzón de envíos -------------------------------------------------------------------------


class Outbox:
    """Lo pendiente de enviar; sobrevive a reinicios y a la falta de internet."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        raw = _read_json(path, [])
        self.items: list[dict[str, Any]] = [
            item
            for item in (raw if isinstance(raw, list) else [])
            if isinstance(item, dict)
            and item.get("kind") in ("usage", "feedback")
            and isinstance(item.get("payload"), dict)
            and isinstance(item.get("id"), str)
        ]

    def _save(self) -> None:
        if self.items:
            _write_json(self.path, self.items)
        else:
            self.path.unlink(missing_ok=True)

    def add(self, kind: str, payload: dict[str, Any]) -> str:
        item_id = uuid.uuid4().hex
        with self._lock:
            self.items.append(
                {
                    "id": item_id,
                    "kind": kind,
                    "payload": payload,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            while len(self.items) > MAX_OUTBOX:
                # Se descartan primero los reportes más viejos; los comentarios se conservan.
                usage = next((i for i in self.items if i["kind"] == "usage"), self.items[0])
                self.items.remove(usage)
            self._save()
        return item_id

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.items)

    def remove(self, item_id: str) -> None:
        with self._lock:
            self.items = [item for item in self.items if item["id"] != item_id]
            self._save()

    def drop_usage(self) -> None:
        with self._lock:
            self.items = [item for item in self.items if item["kind"] != "usage"]
            self._save()

    def has(self, item_id: str) -> bool:
        with self._lock:
            return any(item["id"] == item_id for item in self.items)


# --- Servicio --------------------------------------------------------------------------------

RPC = {"usage": ("submit_usage_report", "p_report"), "feedback": ("submit_feedback", "p_feedback")}


class ImpactService:
    """Consentimiento, contadores, comentarios y envío; lo usa la ventana principal."""

    def __init__(
        self,
        data_dir: Path,
        client: Any | None = None,
        today: Callable[[], date] = date.today,
        version: str | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.settings_path = data_dir / SETTINGS_FILE
        self.settings = ImpactSettings.load(self.settings_path)
        self.tracker = UsageTracker(data_dir / USAGE_FILE, self.settings, today)
        self.outbox = Outbox(data_dir / OUTBOX_FILE)
        self.version = version or app_version()
        self._client = client
        self._send_lock = threading.Lock()

    @property
    def asked(self) -> bool:
        return self.settings.consent is not None

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    def set_consent(self, consent: bool) -> None:
        """Al retirar el consentimiento se borra todo lo pendiente y el identificador."""
        self.settings.consent = consent
        if consent:
            self.settings.install_id = self.settings.install_id or str(uuid.uuid4())
        else:
            self.settings.install_id = None
            self.tracker.clear()
            self.outbox.drop_usage()
        self.settings.save(self.settings_path)

    def preview(self) -> dict[str, Any]:
        """Lo que se enviaría hoy, para mostrarlo a la persona («Ver qué se envía»)."""
        usage = self.tracker.days.get(self.tracker.today().isoformat(), DayUsage())
        install_id = self.settings.install_id or "(se crea al aceptar)"
        return build_report(self.tracker.today(), usage, install_id, self.version)

    def queue_finished_days(self) -> int:
        if not self.enabled or self.settings.install_id is None:
            return 0
        days = self.tracker.take_finished_days()
        for day, usage in days:
            self.outbox.add(
                "usage", build_report(day, usage, self.settings.install_id, self.version)
            )
        return len(days)

    def submit_feedback(self, category: str, message: str, contact: str = "") -> str:
        return self.outbox.add("feedback", build_feedback(category, message, contact, self.version))

    def client(self) -> Any:
        if self._client is None:
            from gestia.license import SupabaseClient, UrllibTransport

            self._client = SupabaseClient(UrllibTransport())
        return self._client

    def flush(self) -> tuple[int, int]:
        """Envía lo pendiente; devuelve (enviados, pendientes). Sin red, todo espera."""
        from gestia.license import LicenseError

        sent = 0
        with self._send_lock:
            for item in self.outbox.pending():
                if item["kind"] == "usage" and not self.enabled:
                    self.outbox.remove(item["id"])
                    continue
                function, argument = RPC[item["kind"]]
                try:
                    self.client().rpc(function, {argument: item["payload"]})
                except LicenseError as exc:
                    if _rejected(exc):
                        # El servidor rechazó el contenido: reintentarlo no sirve y bloquearía
                        # el resto del buzón.
                        LOGGER.warning("Envío rechazado (%s): %s", item["kind"], exc)
                        self.outbox.remove(item["id"])
                        continue
                    LOGGER.info("Envío pendiente (%s): %s", item["kind"], exc.kind)
                    break
                self.outbox.remove(item["id"])
                sent += 1
        return sent, len(self.outbox.pending())


def _rejected(exc: Exception) -> bool:
    """400 o 422: datos no válidos. Sin red, 401/403 (permisos) o 404/5xx se reintenta."""
    return str(exc) in ("HTTP 400", "HTTP 422")
