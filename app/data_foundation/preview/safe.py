"""Safe, budgeted Data Preview. No SELECT * and no caller SQL."""

from __future__ import annotations

import re

import pandas as pd

from app.data_foundation.contracts import DataPreview, DataPreviewRow, QueryBudgetPolicy
from app.data_foundation.discovery.query_budget import compile_profile_query
from app.data_foundation.enums import PreviewMode
from app.data_foundation.ids import new_preview_id

_EMAIL = re.compile(r"(email|e_mail)", re.I)
_PHONE = re.compile(r"(phone|mobile|msisdn)", re.I)
_NAME = re.compile(r"(first_name|last_name|full_name|customer_name)", re.I)
_ADDRESS = re.compile(r"(address|street|zip|postal)", re.I)
_ID = re.compile(r"(user_id|device_id|ssn|password|secret|token|auth)", re.I)
_SAFE_METRICS = re.compile(
    r"^(date|time|week|month|year|channel|campaign|spend|impressions|clicks|revenue|orders|qty|geo|market)$",
    re.I,
)


def classify_fields(columns: list[str]) -> tuple[list[str], list[str], list[str]]:
    keep: list[str] = []
    masked: list[str] = []
    omitted: list[str] = []
    for column in columns:
        if _ID.search(column) or column.lower() in {"password", "secret", "token"}:
            omitted.append(column)
            continue
        if _EMAIL.search(column) or _PHONE.search(column) or _NAME.search(column) or _ADDRESS.search(column):
            masked.append(column)
            keep.append(column)
            continue
        if _SAFE_METRICS.match(column) or len(keep) < 12:
            keep.append(column)
    return keep, masked, omitted


def _mask_value(column: str, value: object, masked: set[str]) -> object:
    if column not in masked or value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    text = str(value)
    if not text:
        return text
    return text[:1] + "***"


def compile_source_preview(
    frame: pd.DataFrame,
    *,
    source_id: str,
    date_field: str | None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    table_id: str | None = None,
    policy: QueryBudgetPolicy | None = None,
    contributing_file: str | None = None,
    original_filename: str | None = None,
) -> DataPreview:
    columns = [str(column) for column in frame.columns]
    keep, masked, omitted = classify_fields(columns)
    verified_time = date_field if date_field and date_field in frame.columns else None
    working = frame.loc[:, [column for column in keep if column in frame.columns]].copy()
    if verified_time:
        working["_sort"] = pd.to_datetime(working[verified_time], errors="coerce")
        working = working.dropna(subset=["_sort"]).sort_values("_sort", ascending=False)
        working = working.drop(columns=["_sort"])
        selection = "most_recent_verified_time"
    else:
        selection = "sample_rows"
    preview = working.head(5)
    masked_set = set(masked)
    rows = []
    for _, row in preview.iterrows():
        rows.append(
            DataPreviewRow(
                values={
                    column: _mask_value(column, row[column], masked_set) for column in preview.columns
                }
            )
        )
    sql = None
    bytes_used = int(preview.memory_usage(deep=True).sum()) if not preview.empty else 0
    if project_id and dataset_id and table_id and keep:
        compiled = compile_profile_query(
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            columns=tuple(keep),
            partition_field=verified_time,
            partition_start=None,
            policy=policy
            or QueryBudgetPolicy(require_partition_predicate=False, sample_limit=5),
            estimated_bytes=bytes_used,
        )
        sql = compiled.sql
        if verified_time:
            sql = (
                f"SELECT {', '.join(keep)} FROM `{project_id}.{dataset_id}.{table_id}` "
                f"ORDER BY {verified_time} DESC LIMIT 5"
            )
        else:
            sql = f"SELECT {', '.join(keep)} FROM `{project_id}.{dataset_id}.{table_id}` LIMIT 5"
    return DataPreview(
        preview_id=new_preview_id(),
        mode=PreviewMode.SOURCE_PREVIEW,
        source_id=source_id,
        compiled_sql=sql,
        row_selection=selection,
        rows=tuple(rows),
        masked_fields=tuple(masked),
        omitted_fields=tuple(omitted),
        contributing_file=contributing_file,
        original_filename=original_filename,
        estimated_bytes=bytes_used,
        verified_time_field=verified_time,
    )


def preview_from_output(
    frame: pd.DataFrame,
    *,
    source_id: str,
    mode: PreviewMode,
    output_resource: str | None = None,
) -> DataPreview:
    del output_resource
    keep, masked, omitted = classify_fields([str(column) for column in frame.columns])
    subset = frame.loc[:, [column for column in keep if column in frame.columns]].head(5)
    masked_set = set(masked)
    rows = [
        DataPreviewRow(
            values={column: _mask_value(column, row[column], masked_set) for column in subset.columns}
        )
        for _, row in subset.iterrows()
    ]
    return DataPreview(
        preview_id=new_preview_id(),
        mode=mode,
        source_id=source_id,
        compiled_sql=None,
        row_selection="latest_output_rows",
        rows=tuple(rows),
        masked_fields=tuple(masked),
        omitted_fields=tuple(omitted),
        estimated_bytes=int(subset.memory_usage(deep=True).sum()) if not subset.empty else 0,
        verified_time_field=None,
    )
