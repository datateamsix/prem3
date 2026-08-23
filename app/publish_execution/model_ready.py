"""Resolve deterministic MODEL_READY evidence. Never emit MODEL_READY."""

from __future__ import annotations

from typing import Protocol

from app.publish_execution.contracts import ModelReadyEvidence


class ModelReadyEvidenceResolver(Protocol):
    def resolve(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
    ) -> ModelReadyEvidence | None: ...


class NullModelReadyEvidenceResolver:
    def resolve(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
    ) -> ModelReadyEvidence | None:
        del tenant_id, workspace_id, dataset_id, run_id
        return None


class InMemoryModelReadyEvidenceResolver:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str, str], ModelReadyEvidence] = {}

    def put(self, evidence: ModelReadyEvidence) -> None:
        self._items[
            (evidence.tenant_id, evidence.workspace_id, evidence.dataset_id, evidence.run_id)
        ] = evidence

    def resolve(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        run_id: str,
    ) -> ModelReadyEvidence | None:
        return self._items.get((tenant_id, workspace_id, dataset_id, run_id))
