"""Drive source version identity and concurrency guard."""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.google.adapters import DriveFile
from app.investment_planning.contracts import BudgetDriveSourceVersion
from app.investment_planning.errors import SourceChangedSinceLoadError, SourceUnidentifiableError


@dataclass(frozen=True, slots=True)
class DriveSourceIdentity:
    drive_file_id: str
    md5_checksum: str | None
    head_revision_id: str | None
    drive_version: str | None

    def fingerprint(self) -> tuple[str | None, str | None, str | None]:
        return (self.md5_checksum, self.head_revision_id, self.drive_version)


def require_source_identity(file: DriveFile) -> DriveSourceIdentity:
    identity = DriveSourceIdentity(
        drive_file_id=file.file_id,
        md5_checksum=file.md5,
        head_revision_id=file.head_revision_id,
        drive_version=file.version,
    )
    if identity.fingerprint() == (None, None, None):
        raise SourceUnidentifiableError(
            "Drive file is missing version, revision, and checksum identity.",
            code="SOURCE_VERSION_UNVERIFIABLE",
        )
    return identity


def assert_source_unchanged(*, loaded: DriveSourceIdentity, current: DriveFile) -> None:
    live = require_source_identity(current)
    if live.drive_file_id != loaded.drive_file_id or live.fingerprint() != loaded.fingerprint():
        raise SourceChangedSinceLoadError(
            "Drive source changed since it was loaded.",
            code="SOURCE_CHANGED_SINCE_LOAD",
        )


def identity_from_source_version(version: BudgetDriveSourceVersion) -> DriveSourceIdentity:
    identity = DriveSourceIdentity(
        drive_file_id=version.drive_file_id,
        md5_checksum=version.md5_checksum,
        head_revision_id=version.head_revision_id,
        drive_version=version.drive_version,
    )
    if identity.fingerprint() == (None, None, None):
        raise SourceUnidentifiableError(
            "Stored source version is missing provider identity.",
            code="SOURCE_VERSION_UNVERIFIABLE",
        )
    return identity
