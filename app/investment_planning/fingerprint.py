"""Canonical fingerprints for Planning metadata. A hash is not persist permission."""

from __future__ import annotations

from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint


def metadata_fingerprint(payload: dict[str, Any]) -> str:
    return canonical_fingerprint(payload)


def investment_plan_fingerprint(
    *, plan_id: str, project_id: str, revision: int, status: str
) -> str:
    return metadata_fingerprint(
        {
            "plan_id": plan_id,
            "project_id": project_id,
            "revision": revision,
            "status": status,
        }
    )
