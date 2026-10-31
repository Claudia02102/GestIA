"""Perfiles de usuario persistidos en JSON local (HU-09 y HU-11).

Un perfil guarda solo ajustes y valores escalares de calibración: nunca imágenes ni landmarks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 2
INDEX_FILE = "index.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    gestures: dict[GestureId, GestureSettings] = field(default_factory=default_gesture_settings)
    actions: dict[GestureId, Action] = field(default_factory=lambda: dict(DEFAULT_ACTIONS))
    calibration: Calibration | None = None
    pointer: PointerSettings = field(default_factory=PointerSettings)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @property
    def calibrated(self) -> bool:
        return self.calibration is not None

    def is_gesture_calibrated(self, gesture: GestureId) -> bool:
        return self.calibration is not None and gesture in self.calibration.gestures

    def selection_gestures(self) -> list[GestureId]:
        return selection_gestures(self.gestures, self.actions)

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
            "calibration": None if self.calibration is None else self.calibration.to_dict(),
            "pointer": asdict(self.pointer),
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
            calibration = raw.get("calibration")
            # Los perfiles del Sprint 2 no tienen esta sección: se usan los valores por defecto.
            pointer = PointerSettings(**raw.get("pointer", {}))
            pointer.validate()
            return cls(
                id=str(raw["id"]),
                name=str(raw["name"]),
                gestures=gestures,
                actions=actions,
                calibration=None if calibration is None else Calibration.from_dict(calibration),
                pointer=pointer,
                created_at=str(raw.get("created_at", _now())),
                updated_at=str(raw.get("updated_at", _now())),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"Perfil no válido: {exc}") from exc


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
        base = profile_id = _slug(name)
        suffix = 2
        while self._path(profile_id).exists():
            profile_id, suffix = f"{base}-{suffix}", suffix + 1
        profile = Profile(profile_id, name)
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

