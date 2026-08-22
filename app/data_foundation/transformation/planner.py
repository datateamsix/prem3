"""Compile an immutable transformation plan from registered actions."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.contracts import TransformationAction, TransformationPlan
from app.data_foundation.enums import TransformAuthority, TransformId
from app.data_foundation.ids import new_plan_id
from app.data_foundation.plan_fingerprint import fingerprint_payload
from app.data_foundation.transformation.catalog import authority_for, refuse_authority_promotion


def compile_transformation_plan(
    *,
    source_id: str,
    source_fingerprint: str,
    registry_version: str,
    action_ids: list[TransformId],
    output_target: str,
    source_grain: str | None = None,
    target_grain: str | None = None,
    parameters: dict[str, dict] | None = None,
    requested_authority: dict[TransformId, TransformAuthority] | None = None,
) -> TransformationPlan:
    params = parameters or {}
    requested = requested_authority or {}
    actions: list[TransformationAction] = []
    requires_approval = False
    lossy = False
    for action_id in action_ids:
        owned = authority_for(action_id)
        if action_id in requested:
            owned = refuse_authority_promotion(action_id, requested[action_id])
        if owned in {TransformAuthority.APPROVAL_REQUIRED, TransformAuthority.USER_REQUIRED}:
            requires_approval = True
        if action_id in {
            TransformId.DF_T011,
            TransformId.DF_T019,
            TransformId.DF_T020,
            TransformId.DF_T021,
        }:
            lossy = True
        if owned is TransformAuthority.NOT_RECOMMENDED:
            requires_approval = True
            lossy = True
        actions.append(
            TransformationAction(
                action_id=action_id,
                authority=owned,
                parameters=params.get(action_id.value, {}),
                lossy=action_id
                in {
                    TransformId.DF_T011,
                    TransformId.DF_T019,
                    TransformId.DF_T020,
                    TransformId.DF_T021,
                },
            )
        )
    payload = {
        "source_id": source_id,
        "source_fingerprint": source_fingerprint,
        "registry_version": registry_version,
        "actions": [item.model_dump(mode="json") for item in actions],
        "output_target": output_target,
    }
    return TransformationPlan(
        plan_id=new_plan_id(),
        version=1,
        source_id=source_id,
        source_fingerprint=source_fingerprint,
        registry_version=registry_version,
        actions=tuple(actions),
        source_grain=source_grain,
        target_grain=target_grain,
        projected_row_delta=None,
        lossy=lossy,
        missingness_behavior="preserve_unknown",
        reconciliation_required=True,
        requires_approval=requires_approval,
        output_target=output_target,
        fingerprint=fingerprint_payload(payload),
        created_at=datetime.now(UTC),
        immutable=True,
    )
