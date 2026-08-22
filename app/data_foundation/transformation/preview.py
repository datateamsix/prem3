"""Preview compiles projected effects without promoting output."""

from __future__ import annotations

import pandas as pd

from app.data_foundation.contracts import TransformationPlan, TransformationPreview
from app.data_foundation.enums import TransformAuthority, TransformId
from app.data_foundation.ids import new_preview_id
from app.data_foundation.transformation.executor import apply_actions
from app.tools.fingerprints import content_fingerprint, schema_signature


def preview_plan(frame: pd.DataFrame, plan: TransformationPlan) -> TransformationPreview:
    columns = [str(column) for column in frame.columns]
    keys = [column for column in ("date", "time") if column in columns] or columns[:1]
    input_schema = str(schema_signature(frame))
    input_content = content_fingerprint(frame, columns=columns, key_columns=keys)
    decisions: list[str] = []
    warnings: list[str] = []
    for action in plan.actions:
        if action.authority is TransformAuthority.USER_REQUIRED:
            decisions.append(action.action_id.value)
        if action.action_id is TransformId.DF_T020:
            warnings.append("MISSING != ZERO: zero-fill is not recommended and will fail closed.")
        if action.action_id is TransformId.DF_T021:
            warnings.append("Fabricating lower-grain rows is forbidden.")
    projected = apply_actions(frame, plan, preview=True)
    out_columns = [str(column) for column in projected.columns]
    return TransformationPreview(
        preview_id=new_preview_id(),
        plan_id=plan.plan_id,
        plan_fingerprint=plan.fingerprint,
        input_rows=int(len(frame)),
        input_schema_fingerprint=input_schema,
        input_content_fingerprint=input_content,
        projected_output_rows=int(len(projected)),
        projected_schema=tuple(out_columns),
        projected_grain=plan.target_grain or plan.source_grain,
        preserved_unknowns=("missing_periods_remain_unknown",),
        warnings=tuple(warnings),
        requires_user_decision=tuple(decisions),
        mutated_source=False,
        actions=tuple(item.action_id.value for item in plan.actions),
        authority=tuple(item.authority.value for item in plan.actions),
        row_delta=int(len(projected) - len(frame)),
        schema_before=tuple(columns),
        schema_after=tuple(out_columns),
        grain_before=plan.source_grain,
        grain_after=plan.target_grain or plan.source_grain,
        unknowns_preserved=("missing_periods_remain_unknown",),
        raw_source_unchanged=True,
    )
