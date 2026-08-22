"""Deterministic file-series grouping. Membership is evidence, not agent opinion."""

from __future__ import annotations

from collections import defaultdict

from app.data_foundation.contracts import DriveFileRecord, FileSeriesCandidate
from app.data_foundation.ids import new_candidate_id


def group_file_series(files: list[DriveFileRecord]) -> list[FileSeriesCandidate]:
    buckets: dict[tuple[str, str], list[DriveFileRecord]] = defaultdict(list)
    for item in files:
        slug = item.source_slug or "custom_unclassified"
        buckets[(item.parent_folder_id, slug)].append(item)
    series: list[FileSeriesCandidate] = []
    for (parent, slug), members in buckets.items():
        fingerprints = {item.file_fingerprint for item in members}
        names = {item.original_name for item in members}
        series.append(
            FileSeriesCandidate(
                series_id=new_candidate_id(),
                source_slug=slug,
                parent_folder_id=parent,
                file_ids=tuple(item.drive_file_id for item in members),
                schema_versions=len(fingerprints) if len(members) > 1 else 1,
                overlapping_periods=0,
                confidence=0.9 if len(members) > 1 else 0.6,
                evidence=(
                    f"parent:{parent}",
                    f"slug:{slug}",
                    f"files:{len(members)}",
                    f"unique_names:{len(names)}",
                ),
            )
        )
    return series
