"""Checkpoint store for resumable ingestion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

_CHECKPOINT_VERSION = 1
_DEFAULT_CHECKPOINT_PATH = ".docprep-checkpoint.json"


@dataclass(kw_only=True, slots=True)
class CheckpointData:
    """Serializable checkpoint state."""

    version: int = _CHECKPOINT_VERSION
    run_id: str = ""
    config_fingerprint: str = ""
    completed_sources: dict[str, str] = field(default_factory=dict)


class CheckpointStore:
    """Manages checkpoint file for resumable ingestion."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else Path(_DEFAULT_CHECKPOINT_PATH)
        self._data: CheckpointData = CheckpointData()

    @property
    def path(self) -> Path:
        return self._path

    def load(self, config_fingerprint: str) -> None:
        """Load checkpoint from file and invalidate when config changes."""
        if not self._path.exists():
            self._data = CheckpointData(config_fingerprint=config_fingerprint)
            return
        try:
            raw_obj = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw_obj, dict):
                raise TypeError("checkpoint root must be an object")

            stored_fp = raw_obj.get("config_fingerprint", "")
            stored_version = raw_obj.get("version", 0)
            completed_sources = raw_obj.get("completed_sources", {})

            if (
                not isinstance(stored_fp, str)
                or not isinstance(stored_version, int)
                or not isinstance(completed_sources, dict)
            ):
                raise TypeError("invalid checkpoint field types")

            if stored_version != _CHECKPOINT_VERSION or stored_fp != config_fingerprint:
                self._data = CheckpointData(config_fingerprint=config_fingerprint)
                return

            normalized_completed: dict[str, str] = {}
            for source_uri, checksum in completed_sources.items():
                if isinstance(source_uri, str) and isinstance(checksum, str):
                    normalized_completed[source_uri] = checksum

            run_id = raw_obj.get("run_id", "")
            self._data = CheckpointData(
                version=stored_version,
                run_id=run_id if isinstance(run_id, str) else "",
                config_fingerprint=stored_fp,
                completed_sources=normalized_completed,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            self._data = CheckpointData(config_fingerprint=config_fingerprint)

    def is_completed(self, source_uri: str, source_checksum: str) -> bool:
        """Check if source was processed with matching checksum."""
        return self._data.completed_sources.get(source_uri) == source_checksum

    def mark_completed(self, source_uri: str, source_checksum: str) -> None:
        """Mark a source as successfully processed."""
        self._data.completed_sources[source_uri] = source_checksum

    def save(self, run_id: str) -> None:
        """Persist checkpoint data to disk."""
        self._data.run_id = run_id
        self._path.write_text(
            json.dumps(asdict(self._data), indent=2) + "\n",
            encoding="utf-8",
        )

    @property
    def completed_count(self) -> int:
        return len(self._data.completed_sources)

    def clear(self) -> None:
        """Remove checkpoint file if present."""
        if self._path.exists():
            self._path.unlink()


def compute_config_fingerprint(
    *,
    loader_config: Any = None,
    parser_config: Any = None,
    chunker_configs: Any = None,
) -> str:
    """Hash output-affecting pipeline config for checkpoint invalidation."""
    parts: list[str] = []
    if loader_config is not None:
        parts.append(f"loader:{_stable_repr(loader_config)}")
    if parser_config is not None:
        parts.append(f"parser:{_stable_repr(parser_config)}")
    if chunker_configs is not None:
        parts.append(f"chunkers:{_stable_repr(chunker_configs)}")
    raw = "|".join(parts) if parts else "default"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _stable_repr(obj: Any) -> str:
    """Create a stable string representation for hashing."""
    if hasattr(obj, "__dict__"):
        return repr(sorted(obj.__dict__.items()))
    if isinstance(obj, (list, tuple)):
        return repr([_stable_repr(item) for item in obj])
    return repr(obj)
