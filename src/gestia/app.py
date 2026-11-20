from __future__ import annotations

import argparse
import locale
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gestia.config import AppConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GestIA - seguimiento facial local")
    parser.add_argument(
        "--config", type=Path, help="Archivo de configuración (por defecto, config.json)"
    )
    parser.add_argument("--camera", type=int, help="Sobrescribe el índice de cámara")
    parser.add_argument(
        "--data-dir", type=Path, help="Carpeta de configuración, perfiles y métricas"
    )
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Arranque con Windows: abre la cámara sin pulsar Iniciar (P3-25)",
    )
    return parser


def resolve_locations(args: argparse.Namespace) -> tuple[Path, Path]:
    """Carpeta de datos y archivo de configuración.

    Instalada (P3-24), los datos van en %LOCALAPPDATA%/GestIA; en desarrollo, en la carpeta
    actual como hasta ahora.
    """
    from gestia.paths import is_installed, user_data_dir

    if args.data_dir is not None:
        root = args.data_dir
    elif is_installed():
        root = user_data_dir()
    else:
        root = Path.cwd()
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    config = args.config if args.config is not None else Path("config.json")
    return root, config if config.is_absolute() else root / config


def use_bundled_model(config: AppConfig, project_root: Path) -> None:
    """Instalada, el modelo viene dentro del programa: se usa si no hay otro en los datos."""
    from gestia.config import resolve_from_project
    from gestia.paths import bundled_path, is_installed

    model = Path(config.vision.model_path)
    if model.is_absolute() or not is_installed():
        return
    if not resolve_from_project(config.vision.model_path, project_root).exists():
        config.vision.model_path = str(bundled_path(config.vision.model_path))


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = build_parser().parse_args(argv)
    from gestia.config import AppConfig

    try:
        project_root, config_path = resolve_locations(args)
    except OSError as exc:
        print(f"No se pudo preparar la carpeta de datos: {exc}", file=sys.stderr)
        return 2
    from gestia.paths import is_installed

    if is_installed():
        # Sin consola: el registro queda en la carpeta de datos para poder dar soporte.
        from logging.handlers import RotatingFileHandler

        handler = RotatingFileHandler(
            project_root / "gestia.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
    try:
        config = AppConfig.load(config_path)
    except ValueError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2
    if args.camera is not None:
        if args.camera < 0:
            print("El índice de cámara no puede ser negativo", file=sys.stderr)
            return 2
        config.camera.index = args.camera
    use_bundled_model(config, project_root)

    # QApplication adopts the user locale on Unix. The protobuf upb backend
    # parses floating-point proto defaults with LC_NUMERIC; comma-decimal
    # locales make MediaPipe values such as "0.5" invalid.
    os.environ["LC_NUMERIC"] = "C"

    from PySide6.QtWidgets import QApplication

    from gestia.ui import MainWindow

    application = QApplication(sys.argv[:1])
    locale.setlocale(locale.LC_NUMERIC, "C")
    window = MainWindow(config, project_root, autostart=args.autostart)
    if args.autostart and window.profile.calibrated:
        # Al iniciar Windows no tapa el escritorio: queda en la barra de tareas, ya controlando.
        window.showMinimized()
    else:
        window.show()
    return application.exec()
