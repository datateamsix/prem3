"""Worker/image provenance for FINAL_MODEL. Qualification digests are historical only."""

from __future__ import annotations

import os
import subprocess
from typing import Protocol

from app.modeling.common.errors import WorkerProvenanceError

# Built from the uncommitted M3-02 working tree. Historical qualification evidence
# only. Ineligible for FINAL_MODEL.
HISTORICAL_UNCOMMITTED_WORKER_DIGESTS = frozenset(
    {
        "sha256:e4bda7be5bb6ec92dc1576d076f7800745c0c16e071e0d74964d65dfb25a930e",
    }
)


class SourceHistory(Protocol):
    def contains(self, sha: str) -> bool: ...


class AllowlistedSourceHistory:
    def __init__(self, shas: frozenset[str]) -> None:
        self._shas = shas

    def contains(self, sha: str) -> bool:
        return sha.lower() in {item.lower() for item in self._shas}


class GitSourceHistory:
    """Fail-closed: SHA must exist as a commit in this repository."""

    def contains(self, sha: str) -> bool:
        value = (sha or "").strip()
        if len(value) < 7:
            return False
        result = subprocess.run(
            ["git", "cat-file", "-t", value],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and (result.stdout or "").strip() == "commit"


class DeployPinnedSourceHistory:
    """Cloud Run has no .git. Deploy stamps PREM3_SOURCE_COMMIT_SHA from git rev-parse."""

    def __init__(self, pinned: str | None = None) -> None:
        self._pinned = (pinned or os.getenv("PREM3_SOURCE_COMMIT_SHA") or "").strip()

    def contains(self, sha: str) -> bool:
        value = (sha or "").strip()
        if GitSourceHistory().contains(value):
            return True
        return bool(self._pinned) and value.lower() == self._pinned.lower()


def resolve_source_commit_sha(*, configured: str | None = None) -> str | None:
    return (configured or os.getenv("PREM3_SOURCE_COMMIT_SHA") or "").strip() or None


def resolve_worker_build_id(*, configured: str | None = None) -> str | None:
    return (configured or os.getenv("PREM3_WORKER_BUILD_ID") or "").strip() or None


def assert_final_model_provenance(
    *,
    source_commit_sha: str | None,
    worker_image_digest: str | None,
    history: SourceHistory | None = None,
) -> None:
    sha = (source_commit_sha or "").strip()
    if not sha:
        raise WorkerProvenanceError(
            "FINAL_MODEL requires source_commit_sha recorded on the FitPlan."
        )
    checker = history or DeployPinnedSourceHistory()
    if not checker.contains(sha):
        raise WorkerProvenanceError(
            "FINAL_MODEL source_commit_sha must exist in Git history."
        )
    digest = (worker_image_digest or "").strip()
    if not digest:
        raise WorkerProvenanceError(
            "FINAL_MODEL requires a committed worker_image_digest."
        )
    if digest in HISTORICAL_UNCOMMITTED_WORKER_DIGESTS:
        raise WorkerProvenanceError(
            "Uncommitted worker digest is ineligible for FINAL_MODEL."
        )
