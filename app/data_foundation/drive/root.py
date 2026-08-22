"""Ensure Data Foundation children exist under the bound Drive root."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.contracts import DriveFoundationLayout

FOUNDATION_CHILDREN = ("sources", "business_data", "evidence", "system")


def ensure_layout(
    *,
    context: DataFoundationContext,
    existing: DriveFoundationLayout | None,
    child_ids: dict[str, str] | None = None,
) -> DriveFoundationLayout:
    if context.drive_root_folder_id is None:
        raise PermissionError("Drive root must be bound before layout creation.")
    now = datetime.now(UTC)
    children = child_ids or {}
    if existing is not None:
        return existing
    return DriveFoundationLayout(
        tenant_id=context.tenant_id,
        workspace_id=context.workspace_id,
        root_folder_id=context.drive_root_folder_id,
        sources_folder_id=children.get("sources"),
        business_data_folder_id=children.get("business_data"),
        evidence_folder_id=children.get("evidence"),
        system_folder_id=children.get("system"),
        created_at=now,
        updated_at=now,
    )
