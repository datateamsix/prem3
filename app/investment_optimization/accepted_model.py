"""Accepted MMM discovery. Never infer MODEL_ACCEPTED."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.investment_optimization.enums import OptimizationIssueCode
from app.modeling.mmm.contracts import MMMModelVersion
from app.modeling.mmm.states import MMMModelingStage

INELIGIBLE_STAGES: frozenset[MMMModelingStage] = frozenset(
    {
        MMMModelingStage.MODEL_READY,
        MMMModelingStage.DESIGNING_MODEL,
        MMMModelingStage.AWAITING_ASSUMPTION_DECISIONS,
        MMMModelingStage.CONFIGURING_MODEL,
        MMMModelingStage.PRIOR_VALIDATION,
        MMMModelingStage.READY_TO_FIT,
        MMMModelingStage.AWAITING_FIT_APPROVAL,
        MMMModelingStage.FITTING_MODEL,
        MMMModelingStage.EVALUATING_MODEL,
        MMMModelingStage.AWAITING_MODEL_REVIEW,
        MMMModelingStage.ITERATION_REQUIRED,
        MMMModelingStage.ITERATING_MODEL,
        MMMModelingStage.FAILED,
    }
)


class ModelingRepositoryDirectory:
    def __init__(self, repo: object) -> None:
        self._repo = repo

    def list_versions(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[MMMModelVersion, ...]:
        return tuple(self._repo.list_versions(tenant_id=tenant_id, project_id=project_id))

    def get_version(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> MMMModelVersion | None:
        return self._repo.get_version(
            tenant_id=tenant_id, project_id=project_id, model_version_id=model_version_id
        )


class MemoryAcceptedModelDirectory:
    def __init__(self) -> None:
        self._versions: list[MMMModelVersion] = []

    def put(self, version: MMMModelVersion) -> MMMModelVersion:
        self._versions.append(version)
        return version

    def list_versions(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[MMMModelVersion, ...]:
        return tuple(
            item
            for item in self._versions
            if item.tenant_id == tenant_id and item.project_id == project_id
        )

    def get_version(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> MMMModelVersion | None:
        return next(
            (
                item
                for item in self._versions
                if item.tenant_id == tenant_id
                and item.project_id == project_id
                and item.model_version_id == model_version_id
            ),
            None,
        )


def is_accepted_model(version: MMMModelVersion) -> bool:
    return version.accepted is True and version.state is MMMModelingStage.MODEL_ACCEPTED


class AcceptedModelDirectory(Protocol):
    def list_versions(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[MMMModelVersion, ...]: ...

    def get_version(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> MMMModelVersion | None: ...


@dataclass(frozen=True, slots=True)
class AcceptedModelSelection:
    version: MMMModelVersion | None
    issue_code: OptimizationIssueCode | None
    candidates: tuple[str, ...]


def select_accepted_model(
    versions: tuple[MMMModelVersion, ...],
    *,
    tenant_id: str,
    project_id: str,
    requested_model_version_id: str | None,
) -> AcceptedModelSelection:
    """0 → none; 1 → that version; 2+ without explicit id → review."""
    accepted = tuple(
        version
        for version in versions
        if version.tenant_id == tenant_id
        and version.project_id == project_id
        and is_accepted_model(version)
    )
    if requested_model_version_id:
        match = next(
            (
                version
                for version in versions
                if version.model_version_id == requested_model_version_id
            ),
            None,
        )
        if match is None:
            return AcceptedModelSelection(None, OptimizationIssueCode.NO_ACCEPTED_MODEL, ())
        if match.tenant_id != tenant_id:
            return AcceptedModelSelection(
                None, OptimizationIssueCode.CROSS_TENANT_MODEL_MAPPING, ()
            )
        if match.project_id != project_id:
            return AcceptedModelSelection(
                None, OptimizationIssueCode.CROSS_PROJECT_MODEL_MAPPING, ()
            )
        if not is_accepted_model(match):
            return AcceptedModelSelection(None, OptimizationIssueCode.NO_ACCEPTED_MODEL, ())
        return AcceptedModelSelection(match, None, (match.model_version_id,))
    if not accepted:
        return AcceptedModelSelection(None, OptimizationIssueCode.NO_ACCEPTED_MODEL, ())
    if len(accepted) > 1:
        return AcceptedModelSelection(
            None,
            OptimizationIssueCode.MULTIPLE_ACCEPTED_MODELS,
            tuple(item.model_version_id for item in accepted),
        )
    return AcceptedModelSelection(accepted[0], None, (accepted[0].model_version_id,))
