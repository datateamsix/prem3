"""Drive file parsers and staging materialization. Raw files are never rewritten."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from app.data_foundation.contracts import DriveFileRecord
from app.tools.io import read_table


def parse_drive_payload(
    *,
    record: DriveFileRecord,
    payload: bytes,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    suffix = Path(record.original_name).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(io.BytesIO(payload))
    if suffix == ".parquet":
        return pd.read_parquet(io.BytesIO(payload))
    if suffix in {".xlsx", ".xlsm"}:
        workbook = pd.ExcelFile(io.BytesIO(payload))
        if sheet_name is None:
            if len(workbook.sheet_names) != 1:
                raise PermissionError("Multiple worksheets require a USER_REQUIRED sheet decision.")
            sheet_name = workbook.sheet_names[0]
        return workbook.parse(sheet_name)
    raise ValueError(f"Unsupported Drive format: {suffix or record.mime_type}")


def parse_local_table(path: str | Path) -> pd.DataFrame:
    return read_table(path)
