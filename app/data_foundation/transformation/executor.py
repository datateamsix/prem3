"""Execute pinned plans. Accepts IDs only. Never writes the raw source."""

from __future__ import annotations

import pandas as pd

from app.data_foundation.contracts import TransformationPlan
from app.data_foundation.enums import TransformAuthority, TransformId
from app.data_foundation.quality.temporal import refuse_zero_fill_missing
from app.tools.remediation import (
    canonicalize_channel_labels,
    canonicalize_geo_labels,
    convert_cost_micros_to_currency,
    normalize_dates,
    normalize_numeric_values,
    remove_exact_duplicates,
)


def apply_actions(
    frame: pd.DataFrame,
    plan: TransformationPlan,
    *,
    preview: bool,
    user_decisions: dict[str, str] | None = None,
) -> pd.DataFrame:
    del preview
    decisions = user_decisions or {}
    result = frame.copy(deep=True)
    for action in plan.actions:
        action_id = action.action_id
        params = action.parameters
        if (
            action.authority is TransformAuthority.USER_REQUIRED
            and action_id.value not in decisions
        ):
            raise PermissionError(f"{action_id.value} requires a recorded user decision.")
        if action_id is TransformId.DF_T001:
            for field in action.field_ids or tuple(str(col) for col in result.columns):
                if field in result.columns and result[field].dtype == object:
                    result[field] = result[field].astype("string").str.strip()
        elif action_id is TransformId.DF_T002:
            for field in action.field_ids:
                if field in result.columns:
                    result[field] = result[field].replace("", pd.NA)
        elif action_id is TransformId.DF_T003:
            result = normalize_dates(result, params["column"], params["expected_format"])
        elif action_id is TransformId.DF_T004:
            result = normalize_numeric_values(result, params["column"])
        elif action_id is TransformId.DF_T005:
            result = convert_cost_micros_to_currency(result, params["column"])
        elif action_id is TransformId.DF_T006:
            result = remove_exact_duplicates(result)
        elif action_id is TransformId.DF_T007:
            keys = list(params.get("keys") or [])
            revision = params.get("revision_field")
            if not keys or not revision:
                raise PermissionError("Reissue removal requires proven keys and a revision field.")
            result = result.sort_values(revision).drop_duplicates(subset=keys, keep="last")
        elif action_id is TransformId.DF_T008:
            result = canonicalize_channel_labels(result, params["column"], params["mapping"])
        elif action_id is TransformId.DF_T010:
            result = canonicalize_geo_labels(result, params["column"], params["mapping"])
        elif action_id is TransformId.DF_T012:
            extras = params.get("frames")
            if extras:
                result = pd.concat([result, *extras], ignore_index=True)
        elif action_id is TransformId.DF_T014:
            raise PermissionError("Currency conversion cannot auto-run.")
        elif action_id is TransformId.DF_T015:
            raise PermissionError("Ambiguous business-key dedupe cannot auto-run.")
        elif action_id is TransformId.DF_T020:
            refuse_zero_fill_missing(list(params.get("missing_periods") or ["unspecified"]))
        elif action_id is TransformId.DF_T021:
            raise PermissionError("Fabricating lower-grain rows from aggregates is forbidden.")
        elif action_id is TransformId.DF_T022:
            pass
        elif action.authority is TransformAuthority.NOT_RECOMMENDED:
            raise PermissionError(f"{action_id.value} is not recommended and is blocked.")
        elif action.authority is TransformAuthority.APPROVAL_REQUIRED and not params.get(
            "approved"
        ):
            raise PermissionError(f"{action_id.value} requires plan approval.")
    return result.reset_index(drop=True)
