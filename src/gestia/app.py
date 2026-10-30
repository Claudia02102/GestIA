from __future__ import annotations

import argparse
import locale
import logging
import os
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GestIA - seguimiento facial local")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--camera", type=int, help="Sobrescribe el índice de cámara")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = build_parser().parse_args(argv)
    project_root = Path.cwd()
    from gestia.config import AppConfig

    try:
        config = AppConfig.load(args.config)
    except ValueError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2
    if args.camera is not None:
        if args.camera < 0:
            print("El índice de cámara no puede ser negativo", file=sys.stderr)
            return 2
        config.camera.index = args.camera

    # QApplication adopts the user locale on Unix. The protobuf upb backend
    # parses floating-point proto defaults with LC_NUMERIC; comma-decimal
    # locales make MediaPipe values such as "0.5" invalid.
    os.environ["LC_NUMERIC"] = "C"

    from PySide6.QtWidgets import QApplication

    from gestia.ui import MainWindow

    application = QApplication(sys.argv[:1])
    locale.setlocale(locale.LC_NUMERIC, "C")
    window = MainWindow(config, project_root)
    window.show()
    return application.exec()
