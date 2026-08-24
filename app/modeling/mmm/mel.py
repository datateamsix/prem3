"""MEL modeling evidence. MEL may learn; it may not mutate an active plan."""

from __future__ import annotations

from typing import Any

from app.modeling.mmm.contracts import ModelingReceipt


def modeling_episode_evidence(
    *,
    event: str,
    model_version_id: str,
    payload: dict[str, Any],
) -> ModelingReceipt:
    return ModelingReceipt(
        receipt_type=event,
        model_version_id=model_version_id,
        payload={
            "domain": "MMM_MODELING",
            "authority": "EVIDENCE_ONLY",
            "can_mutate_plan": False,
            **payload,
        },
    )
