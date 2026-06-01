"""Helpers for archiving generated output files into Supabase."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config


def _get_supabase_client():
    """Create a Supabase client only when credentials are configured."""
    url = config.SUPABASE_URL
    key = config.SUPABASE_SERVICE_ROLE_KEY or config.SUPABASE_ANON_KEY
    if not url or not key:
        return None

    try:
        from supabase import create_client
    except ImportError:
        return None

    return create_client(url, key)


def _build_output_payload(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Convert an output file into the row shape stored in Supabase."""
    file_path = Path(path).resolve()
    project_root = Path(__file__).resolve().parents[1]
    try:
        source_path = file_path.relative_to(project_root).as_posix()
    except ValueError:
        source_path = file_path.as_posix()

    raw_content = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()
    content_json = None
    content_text = None

    if suffix == ".json":
        try:
            content_json = json.loads(raw_content)
        except json.JSONDecodeError:
            content_text = raw_content
    else:
        content_text = raw_content

    stat = file_path.stat()
    parts = file_path.parts
    category = ""
    if "outputs" in parts:
        output_index = parts.index("outputs")
        if len(parts) > output_index + 1:
            category = parts[output_index + 1]

    return {
        "source_path": source_path,
        "category": category,
        "filename": file_path.name,
        "file_ext": suffix.lstrip("."),
        "content_json": content_json,
        "content_text": content_text,
        "raw_content": raw_content,
        "file_size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def sync_output_file(path: str | os.PathLike[str]) -> bool:
    """Upsert one output file into Supabase. Returns False when not configured."""
    client = _get_supabase_client()
    if client is None:
        return False

    payload = _build_output_payload(path)
    client.table(config.SUPABASE_OUTPUTS_TABLE).upsert(
        payload,
        on_conflict="source_path",
    ).execute()
    return True


def safe_sync_output_file(path: str | os.PathLike[str]) -> bool:
    """Best-effort Supabase sync for UI code; never raises."""
    try:
        return sync_output_file(path)
    except Exception:
        return False


def iter_output_files(outputs_dir: str | os.PathLike[str]) -> list[Path]:
    """List uploadable files under outputs, excluding placeholders and caches."""
    root = Path(outputs_dir)
    if not root.exists():
        return []

    ignored_names = {".gitkeep"}
    ignored_parts = {"__pycache__"}
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in ignored_names:
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def sync_outputs_dir(outputs_dir: str | os.PathLike[str]) -> tuple[int, list[str]]:
    """Upload all output files. Returns (uploaded_count, failed_paths)."""
    uploaded = 0
    failed = []
    for path in iter_output_files(outputs_dir):
        try:
            if sync_output_file(path):
                uploaded += 1
        except Exception:
            failed.append(str(path))
    return uploaded, failed
