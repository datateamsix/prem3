"""Drive ancestry and format checks for M2-12 materialization."""

from __future__ import annotations

from app.integrations.google.adapters import DriveClient, DriveFile
from app.integrations.google.formats import SHEETS_MIME, drive_format


PROTECTED_DRIVE_PLANES: frozenset[str] = frozenset(
    {"imports", "sources", "business_data", "evidence"}
)


def file_inside_root(
    drive: DriveClient,
    *,
    access_token: str,
    file: DriveFile,
    root_folder_id: str,
) -> bool:
    if file.file_id == root_folder_id:
        return True
    seen: set[str] = set()
    current: DriveFile | None = file
    while current is not None:
        if current.file_id == root_folder_id:
            return True
        if current.file_id in seen:
            return False
        seen.add(current.file_id)
        if not current.parents:
            return False
        current = drive.get_file(access_token=access_token, file_id=current.parents[0])
    return False


def supported_drive_format(file: DriveFile) -> str | None:
    if file.mime_type == SHEETS_MIME:
        return None
    return drive_format(mime_type=file.mime_type, name=file.name)


def content_type_for_format(fmt: str) -> str:
    if fmt == "csv":
        return "text/csv"
    if fmt == "json":
        return "application/json"
    if fmt == "parquet":
        return "application/parquet"
    return "application/octet-stream"
