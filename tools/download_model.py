from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga explícita del modelo oficial")
    parser.add_argument("--output", type=Path, default=Path("models/face_landmarker.task"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".task.download")
    print(f"Descargando modelo oficial de MediaPipe:\n{MODEL_URL}")
    try:
        urllib.request.urlretrieve(MODEL_URL, temporary)  # noqa: S310
        temporary.replace(args.output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(f"Modelo guardado en {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
