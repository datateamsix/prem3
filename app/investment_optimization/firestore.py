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
    OptimizationReadinessReceipt,
    PortfolioModelMapping,
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
        else:
            raise PersistenceBarrierError(
                f"{type(safe).__name__} is not a P6-04 persistence contract.",
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
