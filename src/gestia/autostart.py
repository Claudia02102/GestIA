"""Inicio automático con Windows (P3-25).

Se usa la clave por usuario ``HKCU\\...\\CurrentVersion\\Run``: no necesita permisos de
administrador y es la misma que escribe el instalador cuando se marca «Iniciar GestIA con
Windows». El valor arranca GestIA con ``--autostart``, que abre la cámara sin pulsar nada.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from gestia.paths import is_installed

LOGGER = logging.getLogger(__name__)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "GestIA"
AUTOSTART_FLAG = "--autostart"


class RunRegistry(Protocol):
    def get(self) -> str | None: ...
    def set(self, command: str) -> None: ...
    def delete(self) -> None: ...


class WindowsRunRegistry:
    """Valor ``GestIA`` de la clave Run del usuario actual."""

    def __init__(self) -> None:
        import winreg  # solo existe en Windows

        self._winreg = winreg

    def get(self) -> str | None:
        reg = self._winreg
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _kind = reg.QueryValueEx(key, VALUE_NAME)
        except FileNotFoundError:
            return None
        return str(value)

    def set(self, command: str) -> None:
        reg = self._winreg
        with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
            reg.SetValueEx(key, VALUE_NAME, 0, reg.REG_SZ, command)

    def delete(self) -> None:
        reg = self._winreg
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                reg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass


def launch_command(data_dir: Path | None = None) -> str:
    """Orden que arranca esta misma instalación de GestIA al iniciar sesión.

    Instalada es el ``GestIA.exe``; en desarrollo, ``pythonw -m gestia`` (sin consola) con la
    carpeta de datos del proyecto, porque Windows no deja elegir el directorio de trabajo.
    """
    if is_installed():
        return subprocess.list2cmdline([sys.executable, AUTOSTART_FLAG])
    executable = Path(sys.executable)
    windowless = executable.with_name("pythonw.exe")
    python = windowless if windowless.exists() else executable
    args = [str(python), "-m", "gestia", AUTOSTART_FLAG]
    if data_dir is not None:
        args += ["--data-dir", str(data_dir)]
    return subprocess.list2cmdline(args)


class Autostart:
    """Activa, desactiva y consulta el arranque con Windows."""

    def __init__(self, registry: RunRegistry | None, command: str) -> None:
        self.registry = registry
        self.command = command

    @classmethod
    def for_system(cls, data_dir: Path | None = None) -> Autostart:
        registry: RunRegistry | None = None
        if sys.platform == "win32":
            try:
                registry = WindowsRunRegistry()
            except (ImportError, OSError):
                LOGGER.warning("No se puede acceder al registro de Windows", exc_info=True)
        return cls(registry, launch_command(data_dir))

    @property
    def available(self) -> bool:
        return self.registry is not None

    def is_enabled(self) -> bool:
        if self.registry is None:
            return False
        try:
            return self.registry.get() is not None
        except OSError:
            LOGGER.warning("No se pudo leer el inicio automático", exc_info=True)
            return False

    def set_enabled(self, enabled: bool) -> None:
        """Lanza ``OSError`` si Windows no permite el cambio."""
        if self.registry is None:
            raise OSError("El inicio automático solo está disponible en Windows")
        if enabled:
            self.registry.set(self.command)
        else:
            self.registry.delete()

    def refresh(self) -> None:
        """Si está activado pero apunta a otra ubicación (programa movido), la corrige."""
        # En desarrollo no se toca: podría pisar el inicio de la versión instalada.
        if self.registry is None or not is_installed():
            return
        try:
            current = self.registry.get()
            if current is not None and current != self.command:
                self.registry.set(self.command)
        except OSError:
            LOGGER.warning("No se pudo actualizar el inicio automático", exc_info=True)
