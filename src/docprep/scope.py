"""Source scope derivation and stale URI computation."""

from __future__ import annotations

from pathlib import Path

from .ids import canonicalize_source_uri
from .models.domain import SourceScope


def derive_scope(
    source: str | Path,
    *,
    source_root: str | Path | None = None,
    explicit_scope: str | None = None,
) -> SourceScope:
    """Derive authoritative source scope for a run."""
    if explicit_scope is not None:
        normalized = _normalize_prefix(explicit_scope)
        return SourceScope(prefixes=(normalized,), explicit=True)

    source_path = Path(source)
    resolved_root = Path(source_root).resolve() if source_root is not None else None

    if source_path.exists() and source_path.is_file():
        uri = canonicalize_source_uri(
            source_path,
            source_root=resolved_root
            if resolved_root is not None
            else source_path.resolve().parent,
        )
        return SourceScope(prefixes=(uri,), explicit=False)

    if source_path.exists() and source_path.is_dir():
        directory_root = resolved_root if resolved_root is not None else source_path.resolve()
        directory_uri = canonicalize_source_uri(source_path, source_root=directory_root)
        return SourceScope(prefixes=(_normalize_directory_prefix(directory_uri),), explicit=False)

    directory_root = resolved_root if resolved_root is not None else source_path.resolve().parent
    directory_uri = canonicalize_source_uri(source_path, source_root=directory_root)
    return SourceScope(prefixes=(_normalize_directory_prefix(directory_uri),), explicit=False)


def uri_in_scope(uri: str, scope: SourceScope) -> bool:
    """Check if a source URI falls within the given scope."""
    for prefix in scope.prefixes:
        if prefix.endswith("/") or prefix == "file:":
            if uri.startswith(prefix):
                return True
            continue
        if uri == prefix:
            return True
    return False


def compute_stale_uris(
    scope: SourceScope,
    seen_uris: set[str],
    stored_uris: set[str],
) -> set[str]:
    """Compute URIs in scope but absent from the latest run."""
    return {uri for uri in stored_uris if uri_in_scope(uri, scope) and uri not in seen_uris}


def _normalize_prefix(prefix: str) -> str:
    normalized = prefix.strip().replace("\\", "/")
    if normalized == "file:.":
        return "file:"
    return normalized


def _normalize_directory_prefix(uri: str) -> str:
    normalized = _normalize_prefix(uri)
    if normalized == "file:":
        return normalized
    if normalized.endswith("/"):
        return normalized
    return f"{normalized}/"
