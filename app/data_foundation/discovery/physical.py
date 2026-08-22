"""Physical metadata from warehouse tables and Drive file series."""

from __future__ import annotations

from app.data_foundation.contracts import DriveFileRecord, PhysicalMetadata
from app.data_foundation.enums import RowCountKind
from app.data_foundation.warehouse import WarehouseTable


def physical_from_table(table: WarehouseTable) -> PhysicalMetadata:
    is_view = table.object_type.upper() == "VIEW"
    row_count = table.num_rows if table.num_rows is not None else len(table.frame)
    kind = RowCountKind(table.row_count_kind) if table.row_count_kind in RowCountKind.__members__ else (
        RowCountKind.SAMPLED if is_view else RowCountKind.EXACT
    )
    return PhysicalMetadata(
        object_type=table.object_type,
        row_count=row_count,
        row_count_kind=kind if not is_view or table.num_rows is not None else RowCountKind.SAMPLED,
        column_count=int(len(table.frame.columns)),
        table_size_bytes=table.num_bytes if not is_view else None,
        dataset_location=table.location,
        last_modified=table.last_modified,
        partitioning_type=None if is_view else table.partitioning_type,
        partitioning_field=None if is_view else table.partition_field,
        partition_count=None if is_view else table.partition_count,
        clustering_fields=() if is_view else table.clustering_fields,
        view_lineage=table.description if is_view else None,
    )


def physical_from_drive_files(files: list[DriveFileRecord], *, row_count: int | None) -> PhysicalMetadata:
    names = [item.original_name for item in files]
    return PhysicalMetadata(
        object_type="DRIVE_LOGICAL_SOURCE",
        row_count=row_count,
        row_count_kind=RowCountKind.EXACT if row_count is not None else RowCountKind.UNKNOWN,
        file_count=len(files),
        schema_versions=tuple(sorted({item.file_fingerprint[:12] for item in files})),
        latest_file_at=None,
        folder_path=files[0].parent_folder_id if files else None,
        date_range=None if not names else "file-series",
    )
