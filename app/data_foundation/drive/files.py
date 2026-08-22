"""Drive file registration. Raw files stay immutable."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.contracts import DriveFileRecord
from app.data_foundation.drive.naming import canonical_logical_name, provider_slug


def fingerprint_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def register_file(
    *,
    context: DataFoundationContext,
    drive_file_id: str,
    original_name: str,
    parent_folder_id: str,
    payload: bytes,
    mime_type: str,
    source_slug: str | None = None,
    data_role: str = "media",
    grain: str = "daily",
    start_date: str = "unknown",
    end_date: str = "unknown",
    version: int = 1,
) -> DriveFileRecord:
    if context.drive_root_folder_id is None:
        raise PermissionError("Drive root is not bound.")
    if parent_folder_id != context.drive_root_folder_id:
        raise PermissionError("Drive access outside the bound root is rejected.")
    digest = fingerprint_bytes(payload)
    ext = Path(original_name).suffix.lstrip(".") or "csv"
    logical = None
    slug = None
    if source_slug:
        slug = provider_slug(source_slug)
        if start_date != "unknown" and end_date != "unknown":
            logical = canonical_logical_name(
                source_slug=slug,
                data_role=data_role,
                grain=grain,
                start_date=start_date,
                end_date=end_date,
                version=version,
                ext=ext,
            )
    now = datetime.now(UTC)
    return DriveFileRecord(
        drive_file_id=drive_file_id,
        original_name=original_name,
        canonical_logical_name=logical,
        parent_folder_id=parent_folder_id,
        source_slug=slug,
        file_fingerprint=digest,
        mime_type=mime_type,
        size=len(payload),
        discovered_at=now,
        registered_at=now,
    )


def reject_outside_root(*, context: DataFoundationContext, parent_folder_id: str) -> None:
    root = context.drive_root_folder_id
    if root is None or parent_folder_id != root and not parent_folder_id.startswith(root):
        # Layout children are allowed when their IDs are stored as layout members.
        # Callers must pass the bound root or a known child. Unknown parents fail.
        if parent_folder_id != root:
            raise PermissionError("Drive access outside the bound root is rejected.")
