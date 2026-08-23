"""Bounded BigQuery → DatasetUpload materialization. No caller SQL."""

from __future__ import annotations

import json
from typing import Protocol

from app.governance.fingerprint import sha256_canonical
from app.integrations.google.adapters import BigQueryTableInfo

BOUNDED_EXPORT_MAX_ROWS = 100_000


class MaterializedTableBytes:
    __slots__ = ("columns", "row_count", "payload", "content_type", "filename")

    def __init__(
        self,
        *,
        columns: list[str],
        row_count: int,
        payload: bytes,
        content_type: str = "application/json",
        filename: str = "source.json",
    ) -> None:
        self.columns = columns
        self.row_count = row_count
        self.payload = payload
        self.content_type = content_type
        self.filename = filename


class BigQueryMaterializationRuntime(Protocol):
    def export_table(
        self,
        *,
        access_token: str,
        project_id: str,
        dataset_id: str,
        table_id: str,
        max_rows: int = BOUNDED_EXPORT_MAX_ROWS,
    ) -> MaterializedTableBytes: ...


def serialize_rows(*, columns: list[str], rows: list[dict[str, object]]) -> bytes:
    ordered: list[list[object]] = []
    for row in rows:
        ordered.append([row.get(column) for column in columns])
    return json.dumps(
        {"columns": columns, "rows": ordered},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def schema_fingerprint(columns: list[str]) -> str:
    return sha256_canonical({"columns": list(columns)})


class FakeBigQueryMaterializationRuntime:
    def __init__(self, client) -> None:
        self._client = client

    def export_table(
        self,
        *,
        access_token: str,
        project_id: str,
        dataset_id: str,
        table_id: str,
        max_rows: int = BOUNDED_EXPORT_MAX_ROWS,
    ) -> MaterializedTableBytes:
        info = self._client.get_table(
            access_token=access_token,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
        )
        if info is None:
            raise LookupError(f"{project_id}.{dataset_id}.{table_id}")
        columns, rows = self._client.export_table_rows(
            access_token=access_token,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            max_rows=max_rows,
        )
        if info.num_rows > max_rows:
            raise OverflowError(info.num_rows)
        payload = serialize_rows(columns=columns, rows=rows)
        return MaterializedTableBytes(
            columns=columns,
            row_count=len(rows),
            payload=payload,
            filename=f"{table_id}.json",
        )


def require_table_identity(info: BigQueryTableInfo | None) -> BigQueryTableInfo:
    if info is None:
        raise LookupError("missing")
    return info
