"""Perfiles de usuario persistidos en JSON local (HU-09, HU-11, P3-16, P3-17 y P3-18).

Un perfil guarda solo ajustes y valores escalares de calibración: nunca imágenes ni landmarks.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gestia.app_context import normalize_app_name
from gestia.calibration import Calibration
from gestia.control import PointerSettings
from gestia.gestures import (
    DEFAULT_ACTIONS,
    MAX_SENSITIVITY,
    MIN_SENSITIVITY,
    Action,
    GestureId,
    GestureSettings,
    default_gesture_settings,
    selection_gestures,
)
from gestia.keyboard import KeyboardSettings

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 4
INDEX_FILE = "index.json"
EXPORT_FORMAT = "gestia-profile"
EXPORT_VERSION = 1
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    gestures: dict[GestureId, GestureSettings] = field(default_factory=default_gesture_settings)
    actions: dict[GestureId, Action] = field(default_factory=lambda: dict(DEFAULT_ACTIONS))
    # P3-16: mapeos propios por ejecutable («chrome.exe»); el resto de apps usa ``actions``.
    app_actions: dict[str, dict[GestureId, Action]] = field(default_factory=dict)
    calibration: Calibration | None = None
    pointer: PointerSettings = field(default_factory=PointerSettings)
    keyboard: KeyboardSettings = field(default_factory=KeyboardSettings)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def calibrated(self) -> bool:
        return self.calibration is not None

    def is_gesture_calibrated(self, gesture: GestureId) -> bool:
        return self.calibration is not None and gesture in self.calibration.gestures

    def selection_gestures(self) -> list[GestureId]:
        return selection_gestures(self.gestures, self.actions)

    def uncalibrated_gestures(self) -> list[GestureId]:
        """Gestos activados que no se reconocerán hasta calibrarlos."""
        return [
            gesture
            for gesture, item in self.gestures.items()
            if item.enabled and not self.is_gesture_calibrated(gesture)
        ]

    def restore_defaults(self) -> None:
        """P3-18: devuelve gestos, sensibilidad, mapeo, puntero y teclado a sus valores iniciales.

        Se conservan el nombre, la calibración, las frases frecuentes y las palabras aprendidas:
        son datos de la persona, no ajustes que puedan dejar el control inservible.
        """
        self.gestures = default_gesture_settings()
        self.actions = dict(DEFAULT_ACTIONS)
        self.app_actions = {}
        self.pointer = PointerSettings()
        defaults = KeyboardSettings()
        self.keyboard.layout, self.keyboard.key_size = defaults.layout, defaults.key_size

    def actions_for(self, app: str | None) -> dict[GestureId, Action]:
        """Mapeo que rige en ``app``: el suyo propio o, si no tiene, el general."""
        return {**self.actions, **self.app_actions.get(app or "", {})}

    def action_for(
        self, gesture: GestureId, app: str | None, paused: bool = False
    ) -> Action | None:
        """Acción de un gesto en ``app``.

        En pausa rige el mapeo general (salvo que el de la app sea el de pausa): la ventana
        activa no debe impedir reanudar con el gesto de siempre.
        """
        action = self.actions_for(app).get(gesture)
        if paused and action is not Action.PAUSE:
            return self.actions.get(gesture)
        return action

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "gestures": {
                str(gesture): {
                    "enabled": item.enabled,
                    "sensitivity": item.sensitivity,
                    "hold_ms": item.hold_ms,
                }
                for gesture, item in self.gestures.items()
            },
            "actions": {str(gesture): str(action) for gesture, action in self.actions.items()},
            "app_actions": {
                app: {str(gesture): str(action) for gesture, action in mapping.items()}
                for app, mapping in self.app_actions.items()
            },
            "calibration": None if self.calibration is None else self.calibration.to_dict(),
            "pointer": asdict(self.pointer),
            "keyboard": self.keyboard.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Profile:
        try:
            gestures = default_gesture_settings()
            for key, item in raw.get("gestures", {}).items():
                gesture = GestureId(key)
                sensitivity = int(item.get("sensitivity", gestures[gesture].sensitivity))
                hold_ms = int(item.get("hold_ms", gestures[gesture].hold_ms))
                if not MIN_SENSITIVITY <= sensitivity <= MAX_SENSITIVITY or hold_ms < 0:
                    raise ValueError(f"ajuste fuera de rango en {key}")
                gestures[gesture] = GestureSettings(
                    bool(item.get("enabled", True)), sensitivity, hold_ms
                )
            actions = dict(DEFAULT_ACTIONS)
            actions.update(
                {GestureId(k): Action(v) for k, v in raw.get("actions", {}).items()}
            )
            # Los perfiles anteriores a P3-16 no tienen esta sección.
            app_actions = {
                normalize_app_name(app): {GestureId(k): Action(v) for k, v in mapping.items()}
                for app, mapping in raw.get("app_actions", {}).items()
            }
            calibration = raw.get("calibration")
            # Los perfiles del Sprint 2 no tienen esta sección: se usan los valores por defecto.
            pointer = PointerSettings(**raw.get("pointer", {}))
            pointer.validate()
            # Los perfiles anteriores al Sprint 4 no tienen esta sección.
            keyboard = KeyboardSettings.from_dict(raw.get("keyboard", {}))
            return cls(
                id=str(raw["id"]),
                name=str(raw["name"]),
                gestures=gestures,
                actions=actions,
                app_actions=app_actions,
                calibration=None if calibration is None else Calibration.from_dict(calibration),
                pointer=pointer,
                keyboard=keyboard,
                created_at=str(raw.get("created_at", _now())),
                updated_at=str(raw.get("updated_at", _now())),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"Perfil no válido: {exc}") from exc


def _reject_constant(value: str) -> None:
    raise ValueError(f"valor numérico no válido: {value}")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"valor numérico no válido: {text}")
    return value


def read_export(path: Path) -> dict[str, Any]:
    """Lee y valida un archivo exportado sin modificar nada; ``ValueError`` si no es válido."""
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("El archivo es demasiado grande para ser un perfil de GestIA")
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except RecursionError as exc:
        raise ValueError("El archivo no es un JSON válido") from exc
    except ValueError as exc:  # incluye JSON y codificación incorrectos
        raise ValueError(f"El archivo no es un JSON válido: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("format") != EXPORT_FORMAT:
        raise ValueError("El archivo no es un perfil exportado por GestIA")
    version = raw.get("format_version")
    if not isinstance(version, int) or not 1 <= version <= EXPORT_VERSION:
        raise ValueError("El archivo viene de una versión de GestIA no compatible")
    data = raw.get("profile")
    if not isinstance(data, dict):
        raise ValueError("El archivo no contiene un perfil")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("El perfil del archivo no tiene nombre")
    keyboard = data.get("keyboard", {})
    if not isinstance(keyboard, dict) or not isinstance(keyboard.get("phrases", []), list):
        raise ValueError("Perfil no válido: frases frecuentes incorrectas")
    # El identificador lo decide quien importa: nunca se usa como ruta el que trae el archivo.
    Profile.from_dict({**data, "id": "importado"})
    return data


def _slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "perfil"


class ProfileStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, profile_id: str) -> Path:
        return self.directory / f"{profile_id}.json"

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def list(self) -> list[Profile]:
        if not self.directory.is_dir():
            return []
        profiles = []
        for path in sorted(self.directory.glob("*.json")):
            if path.name == INDEX_FILE:
                continue
            try:
                profiles.append(self.load(path.stem))
            except (OSError, ValueError) as exc:
                LOGGER.warning("Se ignora el perfil %s: %s", path.name, exc)
        return sorted(profiles, key=lambda item: item.name.casefold())

    def load(self, profile_id: str) -> Profile:
        try:
            raw = json.loads(self._path(profile_id).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Perfil dañado {profile_id}: {exc}") from exc
        return Profile.from_dict(raw)

    def save(self, profile: Profile) -> None:
        profile.updated_at = _now()
        self._write_json(self._path(profile.id), profile.to_dict())

    def create(self, name: str) -> Profile:
        name = name.strip()
        if not name:
            raise ValueError("El nombre del perfil no puede estar vacío")
        if any(item.name.casefold() == name.casefold() for item in self.list()):
            raise ValueError(f"Ya existe un perfil llamado «{name}»")
        profile = Profile(self._new_id(name), name)
        self.save(profile)
        return profile

    def _new_id(self, name: str) -> str:
        base = profile_id = _slug(name)
        suffix = 2
        while self._path(profile_id).exists():
            profile_id, suffix = f"{base}-{suffix}", suffix + 1
        return profile_id

    def export_profile(self, profile: Profile, path: Path) -> None:
        """P3-17: escribe el perfil completo en un archivo para llevarlo a otro equipo."""
        data = {
            "format": EXPORT_FORMAT,
            "format_version": EXPORT_VERSION,
            "profile": profile.to_dict(),
        }
        self._write_json(path, data)

    def import_profile(self, path: Path) -> Profile:
        """P3-17: añade el perfil del archivo como uno nuevo; nunca sobrescribe los existentes.

        Si el archivo no es válido lanza ``ValueError`` sin haber escrito nada.
        """
        data = read_export(path)
        taken = {item.name.casefold() for item in self.list()}
        base = name = data["name"].strip()
        suffix = 2
        while name.casefold() in taken:
            name, suffix = f"{base} ({suffix})", suffix + 1
        profile = Profile.from_dict({**data, "id": self._new_id(name), "name": name})
        self.save(profile)
        return profile

    def delete(self, profile_id: str) -> None:
        self._path(profile_id).unlink(missing_ok=True)
        if self.active_id() == profile_id:
            (self.directory / INDEX_FILE).unlink(missing_ok=True)

    def active_id(self) -> str | None:
        try:
            raw = json.loads((self.directory / INDEX_FILE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        value = raw.get("active") if isinstance(raw, dict) else None
        return value if isinstance(value, str) else None

    def set_active(self, profile_id: str) -> None:
        self._write_json(self.directory / INDEX_FILE, {"active": profile_id})

    def load_active(self) -> Profile:
        """Último perfil usado; si no existe, el primero disponible o uno nuevo."""
        active = self.active_id()
        if active is not None:
            try:
                return self.load(active)
            except (OSError, ValueError) as exc:
                LOGGER.warning("No se pudo cargar el perfil activo %s: %s", active, exc)
        profiles = self.list()
        profile = profiles[0] if profiles else self.create("Perfil 1")
        self.set_active(profile.id)
        return profile

