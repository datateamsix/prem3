"""Firestore metadata store for Investment Planning. Amounts never persist."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.control_plane.serialization import (
    SCHEMA_VERSION,
    ControlPlaneDocumentError,
    _normalize_inbound,
    _normalize_outbound,
)
from app.investment_planning.contracts import (
    BudgetColumnMapping,
    BudgetDriveSourceVersion,
    InvestmentPlan,
    InvestmentPlanValidationReceipt,
    PortfolioSnapshotRef,
)
from app.investment_planning.store import (
    InvestmentPlanningMetadata,
    assert_metadata_only,
)

BUDGET_SCHEMA_FIELD = "budget_schema_version"

COLLECTION_TENANTS = "tenants"
COLLECTION_WORKSPACES = "workspaces"
COL_PLANS = "investment_plans"
COL_SOURCES = "budget_source_versions"
COL_MAPPINGS = "budget_column_mappings"
COL_RECEIPTS = "investment_plan_receipts"
COL_SNAPSHOTS = "portfolio_snapshot_refs"
COL_INDEX = "investment_planning_index"

T = TypeVar("T", bound=BaseModel)


def _planning_to_document(model: BaseModel) -> dict[str, Any]:
    """Persist metadata without clobbering BudgetDriveSourceVersion.schema_version."""
    raw = model.model_dump(mode="python")
    budget_schema = raw.get("schema_version")
    payload = _normalize_outbound(raw)
    payload["schema_version"] = SCHEMA_VERSION
    if isinstance(budget_schema, str):
        payload[BUDGET_SCHEMA_FIELD] = budget_schema
    return payload


def _planning_from_document(model_type: type[T], data: dict[str, Any] | None) -> T:
    if data is None:
        raise ControlPlaneDocumentError(f"Missing document for {model_type.__name__}.")
    if not isinstance(data, dict):
        raise ControlPlaneDocumentError(f"Malformed document for {model_type.__name__}.")
    cleaned = dict(data)
    cleaned.pop("schema_version", None)
    budget_schema = cleaned.pop(BUDGET_SCHEMA_FIELD, None)
    if budget_schema is not None:
        cleaned["schema_version"] = budget_schema
    try:
        return model_type.model_validate(_normalize_inbound(cleaned))
    except ValidationError as exc:
        raise ControlPlaneDocumentError(
            f"Rejected malformed {model_type.__name__} document."
        ) from exc


class FirestoreInvestmentPlanningStore:
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
        extra: dict[str, str] | None = None,
    ) -> None:
        payload: dict[str, str] = {"tenant_id": tenant_id, "workspace_id": workspace_id}
        if extra:
            payload.update(extra)
        self._index(kind, resource_id).set(payload)

    def _load(
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
        return _planning_from_document(model_type, doc.to_dict())

    def put(self, value: InvestmentPlanningMetadata) -> InvestmentPlanningMetadata:
        safe = assert_metadata_only(value)
        if isinstance(safe, InvestmentPlan):
            self._workspace(safe.tenant_id, safe.workspace_id).collection(COL_PLANS).document(
                safe.plan_id
            ).set(_planning_to_document(safe))
            self._put_index(
                kind="plan",
                resource_id=safe.plan_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.workspace_id,
            )
        elif isinstance(safe, BudgetDriveSourceVersion):
            self._workspace(safe.tenant_id, safe.workspace_id).collection(COL_SOURCES).document(
                safe.source_version_id
            ).set(_planning_to_document(safe))
            self._put_index(
                kind="source",
                resource_id=safe.source_version_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.workspace_id,
            )
        elif isinstance(safe, BudgetColumnMapping):
            plan = self.get_plan(safe.plan_id)
            if plan is None:
                raise LookupError(safe.plan_id)
            self._workspace(plan.tenant_id, plan.workspace_id).collection(COL_MAPPINGS).document(
                safe.mapping_id
            ).set(_planning_to_document(safe))
            self._put_index(
                kind="mapping",
                resource_id=safe.mapping_id,
                tenant_id=plan.tenant_id,
                workspace_id=plan.workspace_id,
            )
            self._put_index(
                kind="source_map",
                resource_id=safe.source_version_id,
                tenant_id=plan.tenant_id,
                workspace_id=plan.workspace_id,
                extra={"mapping_id": safe.mapping_id},
            )
        elif isinstance(safe, InvestmentPlanValidationReceipt):
            plan = self.get_plan(safe.plan_id)
            if plan is None:
                raise LookupError(safe.plan_id)
            self._workspace(plan.tenant_id, plan.workspace_id).collection(COL_RECEIPTS).document(
                safe.receipt_id
            ).set(_planning_to_document(safe))
            self._put_index(
                kind="receipt",
                resource_id=safe.receipt_id,
                tenant_id=plan.tenant_id,
                workspace_id=plan.workspace_id,
            )
            self._put_index(
                kind="plan_receipt",
                resource_id=safe.plan_id,
                tenant_id=plan.tenant_id,
                workspace_id=plan.workspace_id,
                extra={"receipt_id": safe.receipt_id},
            )
        elif isinstance(safe, PortfolioSnapshotRef):
            self._workspace(safe.tenant_id, safe.workspace_id).collection(COL_SNAPSHOTS).document(
                safe.snapshot_id
            ).set(_planning_to_document(safe))
            self._put_index(
                kind="snapshot",
                resource_id=safe.snapshot_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.workspace_id,
            )
        return safe

    def get_plan(self, plan_id: str) -> InvestmentPlan | None:
        return self._load(InvestmentPlan, kind="plan", resource_id=plan_id, collection=COL_PLANS)

    def list_plans(self, *, tenant_id: str, project_id: str) -> tuple[InvestmentPlan, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_PLANS).stream()
        return tuple(_planning_from_document(InvestmentPlan, doc.to_dict()) for doc in docs)

    def get_source(self, source_version_id: str) -> BudgetDriveSourceVersion | None:
        return self._load(
            BudgetDriveSourceVersion,
            kind="source",
            resource_id=source_version_id,
            collection=COL_SOURCES,
        )

    def get_mapping(self, mapping_id: str) -> BudgetColumnMapping | None:
        return self._load(
            BudgetColumnMapping,
            kind="mapping",
            resource_id=mapping_id,
            collection=COL_MAPPINGS,
        )

    def mapping_for_source(self, source_version_id: str) -> BudgetColumnMapping | None:
        snap = self._index("source_map", source_version_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        mapping_id = str(data.get("mapping_id") or "")
        if not mapping_id:
            return None
        return self.get_mapping(mapping_id)

    def get_receipt(self, receipt_id: str) -> InvestmentPlanValidationReceipt | None:
        return self._load(
            InvestmentPlanValidationReceipt,
            kind="receipt",
            resource_id=receipt_id,
            collection=COL_RECEIPTS,
        )

    def latest_receipt(self, plan_id: str) -> InvestmentPlanValidationReceipt | None:
        snap = self._index("plan_receipt", plan_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        receipt_id = str(data.get("receipt_id") or "")
        if not receipt_id:
            return None
        return self.get_receipt(receipt_id)

    def get_snapshot(self, snapshot_id: str) -> PortfolioSnapshotRef | None:
        return self._load(
            PortfolioSnapshotRef,
            kind="snapshot",
            resource_id=snapshot_id,
            collection=COL_SNAPSHOTS,
        )

    def latest_snapshot(
        self, *, tenant_id: str, project_id: str, fiscal_year: int | None = None
    ) -> PortfolioSnapshotRef | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_SNAPSHOTS).stream()
        matches = [
            _planning_from_document(PortfolioSnapshotRef, doc.to_dict()) for doc in docs
        ]
        if fiscal_year is not None:
            matches = [item for item in matches if item.fiscal_year == fiscal_year]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)
