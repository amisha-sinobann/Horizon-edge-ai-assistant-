"""Small, deterministic disk cache for JSON API responses."""

import hashlib
import json
from pathlib import Path
from typing import Any


class JsonCache:
    """Persist JSON-compatible values under stable request keys."""

    def __init__(self, directory: str | Path) -> None:
        """Create the cache directory if necessary."""
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        """Return the path for a logical cache key."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def get(self, key: str) -> Any | None:
        """Return a cached value, or ``None`` when no valid value exists."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: Any) -> None:
        """Write a JSON-compatible value atomically enough for one process."""
        self._path(key).write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
