import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def environment_metadata() -> dict[str, Any]:
    memory_bytes: int | None = None
    try:
        memory_bytes = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
    except (ValueError, OSError, AttributeError):
        pass
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "architecture": platform.machine(),
        "cpu": platform.processor() or "no informado",
        "logical_cpu_count": os.cpu_count(),
        "ram_bytes": memory_bytes,
        "session_type": os.environ.get("XDG_SESSION_TYPE", "no informado"),
    }


class MetricsWriter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, session: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "environment": environment_metadata(),
            **session,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
