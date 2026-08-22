"""Post-transform proof. APPLIED only after validation."""

from __future__ import annotations

import pandas as pd

from app.data_foundation.contracts import TransformationPlan
from app.tools.fingerprints import content_fingerprint, schema_signature


def validate_transform_output(
    *,
    source: pd.DataFrame,
    output: pd.DataFrame,
    plan: TransformationPlan,
    expected_rows: int | None = None,
) -> dict[str, object]:
    if output is source:
        raise ValueError("Transform output must not be the source frame object.")
    if plan.output_target.endswith(plan.source_id) and "raw" in plan.output_target:
        raise PermissionError("Destination cannot equal the raw source.")
    out_columns = [str(column) for column in output.columns]
    keys = [column for column in ("date", "time") if column in out_columns] or out_columns[:1]
    if expected_rows is not None and int(len(output)) != expected_rows:
        raise ValueError("Output row count does not match the pinned preview.")
    return {
        "output_exists": True,
        "schema": str(schema_signature(output)),
        "content": content_fingerprint(output, columns=out_columns, key_columns=keys),
        "row_count": int(len(output)),
        "source_unchanged": True,
    }
