from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class JsonFileCache:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, namespace: str, payload: dict[str, Any]) -> Path:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
                "utf-8"
            )
        ).hexdigest()
        safe_namespace = namespace.replace("/", "_")
        return self.base_dir / f"{safe_namespace}-{digest}.json"

    def get(self, namespace: str, payload: dict[str, Any]) -> Any | None:
        path = self._path_for(namespace, payload)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def set(self, namespace: str, payload: dict[str, Any], value: Any) -> None:
        path = self._path_for(namespace, payload)
        path.write_text(json.dumps(value, indent=2, sort_keys=True))
