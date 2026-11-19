"""Carpetas de la aplicación en desarrollo y en la versión instalada (P3-24).

En desarrollo todo vive en la carpeta del proyecto (como hasta ahora). Instalada, la carpeta del
programa es de solo lectura y contiene el modelo; la configuración, los perfiles y las métricas
de cada persona van en ``%LOCALAPPDATA%\\GestIA``, que el desinstalador no borra.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "GestIA"


def is_installed() -> bool:
    """Verdadero en el ejecutable empaquetado con PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Carpeta con los recursos del programa (modelo y archivos de ejemplo)."""
    if is_installed():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def user_data_dir(environ: dict[str, str] | None = None) -> Path:
    """Datos de la persona en la versión instalada; se crea si no existe."""
    env = os.environ if environ is None else environ
    base = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def bundled_path(relative: str) -> Path:
    """Ruta de un recurso empaquetado (por ejemplo ``models/face_landmarker.task``)."""
    return bundle_dir() / relative
