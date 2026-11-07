"""Aplicación en primer plano para el mapeo por aplicación (P3-16).

Las aplicaciones se identifican por el nombre de su ejecutable en minúsculas («chrome.exe»).
Solo se consulta ese nombre: nunca títulos de ventana ni contenido. Fuera de Windows, o si la
consulta falla, no hay aplicación conocida y se usa el mapeo general.
"""

from __future__ import annotations

import logging
import os
import re
import sys

LOGGER = logging.getLogger(__name__)
_APP_NAME = re.compile(r"^[\w .+()-]+\.exe$")


def normalize_app_name(text: str) -> str:
    """Convierte lo escrito o detectado en la clave del mapeo; ``ValueError`` si no es válido."""
    name = text.strip().replace("/", "\\").rsplit("\\", 1)[-1].casefold()
    if name and not name.endswith(".exe"):
        name += ".exe"
    if not _APP_NAME.fullmatch(name):
        raise ValueError(f"Nombre de aplicación no válido: «{text}»")
    return name


def _windows_api():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    )
    return ctypes, wintypes, user32, kernel32


def _app_of_window(hwnd, api) -> str | None:
    """Ejecutable dueño de la ventana; ``None`` si es de GestIA o no se puede consultar."""
    ctypes, wintypes, user32, kernel32 = api
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value or pid.value == os.getpid():
        return None
    query_limited_information = 0x1000
    handle = kernel32.OpenProcess(query_limited_information, False, pid.value)
    if not handle:  # p. ej. una aplicación con permisos de administrador
        return None
    try:
        size = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return None
    finally:
        kernel32.CloseHandle(handle)
    try:
        return normalize_app_name(path.value)
    except ValueError:
        return None


def foreground_app() -> str | None:
    """Aplicación activa. ``None`` si es GestIA o no se puede saber: rige el mapeo general."""
    if sys.platform != "win32":
        return None
    try:
        api = _windows_api()
        hwnd = api[2].GetForegroundWindow()
        return _app_of_window(hwnd, api) if hwnd else None
    except OSError:
        LOGGER.warning("No se pudo consultar la aplicación activa", exc_info=True)
        return None


def open_apps() -> list[str]:
    """Aplicaciones con ventanas visibles, para elegir a cuál dar un mapeo propio."""
    if sys.platform != "win32":
        return []
    try:
        api = _windows_api()
        ctypes, wintypes, user32, _ = api
        found: set[str] = set()

        def visit(hwnd, _param) -> bool:
            if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
                app = _app_of_window(hwnd, api)
                if app is not None:
                    found.add(app)
            return True

        callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit)
        user32.EnumWindows(callback, 0)
        return sorted(found)
    except OSError:
        LOGGER.warning("No se pudieron listar las aplicaciones abiertas", exc_info=True)
        return []
