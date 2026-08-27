"""Firestore metadata store for optimization readiness. Amounts never persist."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from app.control_plane.serialization import (
    SCHEMA_VERSION,
    ControlPlaneDocumentError,
    _normalize_inbound,
    _normalize_outbound,
)
from app.investment_optimization.contracts import (
    ModelConsumptionContract,
    OptimizationEvidenceCoverage,
    OptimizationInputContract,
    OptimizationProposal,
    OptimizationReadinessReceipt,
    OptimizationResultRef,
    OptimizationRun,
    PlanningDecisionRecord,
    PortfolioModelMapping,
    ProposalDecisionReceipt,
    ProposalReadinessReceipt,
    ScenarioArtifact,
)
from app.investment_optimization.store import (
    OptimizationMetadata,
    assert_optimization_metadata_only,
)
from app.investment_planning.errors import PersistenceBarrierError

COLLECTION_TENANTS = "tenants"
COLLECTION_WORKSPACES = "workspaces"
COL_MAPPINGS = "portfolio_model_mappings"
COL_INPUTS = "optimization_input_contracts"
COL_RECEIPTS = "optimization_readiness_receipts"
COL_COVERAGE = "optimization_evidence_coverage"
COL_CONTRACTS = "model_consumption_contracts"
COL_RUNS = "optimization_runs"
COL_RESULTS = "optimization_result_refs"
COL_SCENARIOS = "scenario_artifacts"
COL_PROPOSALS = "optimization_proposals"
COL_PROPOSAL_READY = "proposal_readiness_receipts"
COL_DECISIONS = "proposal_decision_receipts"
COL_DECISION_RECORDS = "planning_decision_records"
COL_INDEX = "investment_optimization_index"


def _to_document(model: BaseModel) -> dict[str, Any]:
    payload = _normalize_outbound(model.model_dump(mode="python"))
    payload["schema_version"] = SCHEMA_VERSION
    return payload


def _from_document[T: BaseModel](model_type: type[T], data: dict[str, Any] | None) -> T:
    if data is None:
        raise ControlPlaneDocumentError(f"Missing document for {model_type.__name__}.")
    if not isinstance(data, dict):
        raise ControlPlaneDocumentError(f"Malformed document for {model_type.__name__}.")
    cleaned = dict(data)
    cleaned.pop("schema_version", None)
    try:
        return model_type.model_validate(_normalize_inbound(cleaned))
    except ValidationError as exc:
        raise ControlPlaneDocumentError(
            f"Rejected malformed {model_type.__name__} document."
        ) from exc


class FirestoreOptimizationMetadataStore:
    def __init__(self, client: Any) -> None:
        self._db = client

    def _workspace(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COLLECTION_TENANTS)
            .document(tenant_id)
            .collection(COLLECTION_WORKSPACES)
            .document(workspace_id)
        )

    def _index(self, kind: str, resource_id: str):
        return self._db.collection(COL_INDEX).document(f"{kind}__{resource_id}")

    def _put_index(
        self,
        *,
        kind: str,
        resource_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> None:
        self._index(kind, resource_id).set(
            {"tenant_id": tenant_id, "workspace_id": workspace_id}
        )

    def _load[T: BaseModel](
        self,
        model_type: type[T],
        *,
        kind: str,
        resource_id: str,
        collection: str,
    ) -> T | None:
        snap = self._index(kind, resource_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        doc = (
            self._workspace(str(data["tenant_id"]), str(data["workspace_id"]))
            .collection(collection)
            .document(resource_id)
            .get()
        )
        if not doc.exists:
            return None
        return _from_document(model_type, doc.to_dict())

    def put(self, value: OptimizationMetadata) -> OptimizationMetadata:
        safe = assert_optimization_metadata_only(value)
        if isinstance(safe, PortfolioModelMapping):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_MAPPINGS).document(
                safe.mapping_id
            ).set(_to_document(safe))
            self._put_index(
                kind="mapping",
                resource_id=safe.mapping_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationInputContract):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_INPUTS).document(
                safe.optimization_input_id
            ).set(_to_document(safe))
            self._put_index(
                kind="input",
                resource_id=safe.optimization_input_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationReadinessReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RECEIPTS).document(
                safe.receipt_id
            ).set(_to_document(safe))
            self._put_index(
                kind="receipt",
                resource_id=safe.receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationEvidenceCoverage):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_COVERAGE).document(
                safe.coverage_id
            ).set(_to_document(safe))
            self._put_index(
                kind="coverage",
                resource_id=safe.coverage_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ModelConsumptionContract):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_CONTRACTS).document(
                safe.consumption_contract_id
            ).set(_to_document(safe))
            self._put_index(
                kind="consumption",
                resource_id=safe.consumption_contract_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationRun):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RUNS).document(
                safe.optimization_run_id
            ).set(_to_document(safe))
            self._put_index(
                kind="run",
                resource_id=safe.optimization_run_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationResultRef):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RESULTS).document(
                safe.result_id
            ).set(_to_document(safe))
            self._put_index(
                kind="result",
                resource_id=safe.result_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ScenarioArtifact):
            existing = self.get_scenario(safe.scenario_id)
            if existing is not None:
                raise PersistenceBarrierError(
                    "ScenarioArtifact is immutable after publish.",
                    code="SCENARIO_IMMUTABLE",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_SCENARIOS).document(
                safe.scenario_id
            ).set(_to_document(safe))
            self._put_index(
                kind="scenario",
                resource_id=safe.scenario_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationProposal):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_PROPOSALS).document(
                safe.proposal_id
            ).set(_to_document(safe))
            self._put_index(
                kind="proposal",
                resource_id=safe.proposal_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ProposalReadinessReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_PROPOSAL_READY
            ).document(safe.receipt_id).set(_to_document(safe))
            self._put_index(
                kind="proposal_readiness",
                resource_id=safe.receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ProposalDecisionReceipt):
            if self.get_decision_receipt(safe.decision_receipt_id) is not None:
                raise PersistenceBarrierError(
                    "ProposalDecisionReceipt is immutable.",
                    code="DECISION_RECEIPT_IMMUTABLE",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_DECISIONS).document(
                safe.decision_receipt_id
            ).set(_to_document(safe))
            self._put_index(
                kind="decision",
                resource_id=safe.decision_receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, PlanningDecisionRecord):
            if self.get_decision_record(safe.decision_id) is not None:
                raise PersistenceBarrierError(
                    "PlanningDecisionRecord is immutable.",
                    code="DECISION_RECEIPT_IMMUTABLE",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_DECISION_RECORDS
            ).document(safe.decision_id).set(_to_document(safe))
            self._put_index(
                kind="decision_record",
                resource_id=safe.decision_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        else:
            raise PersistenceBarrierError(
                f"{type(safe).__name__} is not a P6-04/P6-06 persistence contract.",
                code="PLANNING_PERSISTENCE_BARRIER",
            )
        return safe

    def get_mapping(self, mapping_id: str) -> PortfolioModelMapping | None:
        return self._load(
            PortfolioModelMapping, kind="mapping", resource_id=mapping_id, collection=COL_MAPPINGS
        )

    def list_mappings(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[PortfolioModelMapping, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_MAPPINGS).stream()
        return tuple(_from_document(PortfolioModelMapping, doc.to_dict()) for doc in docs)

    def latest_mapping(
        self, *, tenant_id: str, project_id: str
    ) -> PortfolioModelMapping | None:
        matches = self.list_mappings(tenant_id=tenant_id, project_id=project_id)
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_receipt(self, receipt_id: str) -> OptimizationReadinessReceipt | None:
        return self._load(
            OptimizationReadinessReceipt,
            kind="receipt",
            resource_id=receipt_id,
            collection=COL_RECEIPTS,
        )

    def latest_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationReadinessReceipt | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_RECEIPTS).stream()
        matches = [
            _from_document(OptimizationReadinessReceipt, doc.to_dict()) for doc in docs
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_input_contract(
        self, optimization_input_id: str
    ) -> OptimizationInputContract | None:
        return self._load(
            OptimizationInputContract,
            kind="input",
            resource_id=optimization_input_id,
            collection=COL_INPUTS,
        )

    def get_coverage(self, coverage_id: str) -> OptimizationEvidenceCoverage | None:
        return self._load(
            OptimizationEvidenceCoverage,
            kind="coverage",
            resource_id=coverage_id,
            collection=COL_COVERAGE,
        )

    def get_consumption_for_model(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> ModelConsumptionContract | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_CONTRACTS).stream()
        matches = [
            _from_document(ModelConsumptionContract, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("model_version_id") == model_version_id
        ]
        if not matches:
            return None
        return matches[-1]

    def get_run(self, optimization_run_id: str) -> OptimizationRun | None:
        return self._load(
            OptimizationRun, kind="run", resource_id=optimization_run_id, collection=COL_RUNS
        )

    def list_runs(self, *, tenant_id: str, project_id: str) -> tuple[OptimizationRun, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_RUNS).stream()
        matches = [_from_document(OptimizationRun, doc.to_dict()) for doc in docs]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def latest_run(self, *, tenant_id: str, project_id: str) -> OptimizationRun | None:
        matches = self.list_runs(tenant_id=tenant_id, project_id=project_id)
        return matches[0] if matches else None

    def get_run_by_idempotency(
        self, *, tenant_id: str, project_id: str, idempotency_key: str
    ) -> OptimizationRun | None:
        matches = [
            item
            for item in self.list_runs(tenant_id=tenant_id, project_id=project_id)
            if item.idempotency_key == idempotency_key
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_result_ref(self, result_id: str) -> OptimizationResultRef | None:
        return self._load(
            OptimizationResultRef, kind="result", resource_id=result_id, collection=COL_RESULTS
        )

    def get_result_ref_for_run(self, optimization_run_id: str) -> OptimizationResultRef | None:
        snap = self._index("run", optimization_run_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        docs = (
            self._workspace(str(data["tenant_id"]), str(data["workspace_id"]))
            .collection(COL_RESULTS)
            .stream()
        )
        matches = [
            _from_document(OptimizationResultRef, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("optimization_run_id") == optimization_run_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def latest_completed_result(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationResultRef | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_RESULTS).stream()
        matches = [_from_document(OptimizationResultRef, doc.to_dict()) for doc in docs]
        current = [item for item in matches if item.is_current]
        pool = current or matches
        if not pool:
            return None
        return max(pool, key=lambda item: item.created_at)

    def get_scenario(self, scenario_id: str) -> ScenarioArtifact | None:
        return self._load(
            ScenarioArtifact,
            kind="scenario",
            resource_id=scenario_id,
            collection=COL_SCENARIOS,
        )

    def list_scenarios(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ScenarioArtifact, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_SCENARIOS).stream()
        matches = [_from_document(ScenarioArtifact, doc.to_dict()) for doc in docs]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def get_proposal(self, proposal_id: str) -> OptimizationProposal | None:
        return self._load(
            OptimizationProposal,
            kind="proposal",
            resource_id=proposal_id,
            collection=COL_PROPOSALS,
        )

    def list_proposals(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[OptimizationProposal, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_PROPOSALS).stream()
        matches = [_from_document(OptimizationProposal, doc.to_dict()) for doc in docs]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def get_proposal_readiness(self, receipt_id: str) -> ProposalReadinessReceipt | None:
        return self._load(
            ProposalReadinessReceipt,
            kind="proposal_readiness",
            resource_id=receipt_id,
            collection=COL_PROPOSAL_READY,
        )

    def get_proposal_readiness_for_proposal(
        self, proposal_id: str
    ) -> ProposalReadinessReceipt | None:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return None
        docs = (
            self._workspace(proposal.tenant_id, proposal.project_id)
            .collection(COL_PROPOSAL_READY)
            .stream()
        )
        matches = [
            _from_document(ProposalReadinessReceipt, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("proposal_id") == proposal_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_decision_receipt(
        self, decision_receipt_id: str
    ) -> ProposalDecisionReceipt | None:
        return self._load(
            ProposalDecisionReceipt,
            kind="decision",
            resource_id=decision_receipt_id,
            collection=COL_DECISIONS,
        )

    def get_decision_receipt_for_proposal(
        self, proposal_id: str
    ) -> ProposalDecisionReceipt | None:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return None
        docs = (
            self._workspace(proposal.tenant_id, proposal.project_id)
            .collection(COL_DECISIONS)
            .stream()
        )
        matches = [
            _from_document(ProposalDecisionReceipt, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("proposal_id") == proposal_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_decision_record(self, decision_id: str) -> PlanningDecisionRecord | None:
        return self._load(
            PlanningDecisionRecord,
            kind="decision_record",
            resource_id=decision_id,
            collection=COL_DECISION_RECORDS,
        )
