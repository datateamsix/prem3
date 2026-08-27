"""Firestore metadata store for Investment Planning. Amounts never persist."""

from __future__ import annotations

from typing import Any

from app.control_plane.serialization import document_to_model, model_to_document
from app.investment_planning.contracts import (
    BudgetColumnMapping,
    BudgetDriveSourceVersion,
    InvestmentPlan,
    InvestmentPlanValidationReceipt,
)
from app.investment_planning.store import (
    InvestmentPlanningMetadata,
    assert_metadata_only,
)

COLLECTION_TENANTS = "tenants"
COLLECTION_WORKSPACES = "workspaces"
COL_PLANS = "investment_plans"
COL_SOURCES = "budget_source_versions"
COL_MAPPINGS = "budget_column_mappings"
COL_RECEIPTS = "investment_plan_receipts"
COL_INDEX = "investment_planning_index"


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

    def put(self, value: InvestmentPlanningMetadata) -> InvestmentPlanningMetadata:
        safe = assert_metadata_only(value)
        if isinstance(safe, InvestmentPlan):
            self._workspace(safe.tenant_id, safe.workspace_id).collection(COL_PLANS).document(
                safe.plan_id
            ).set(model_to_document(safe))
            self._db.collection(COL_INDEX).document(f"plan__{safe.plan_id}").set(
                {"tenant_id": safe.tenant_id, "workspace_id": safe.workspace_id}
            )
        elif isinstance(safe, BudgetDriveSourceVersion):
            self._workspace(safe.tenant_id, safe.workspace_id).collection(COL_SOURCES).document(
                safe.source_version_id
            ).set(model_to_document(safe))
        elif isinstance(safe, BudgetColumnMapping):
            plan = self.get_plan(safe.plan_id)
            if plan is None:
                raise LookupError(safe.plan_id)
            self._workspace(plan.tenant_id, plan.workspace_id).collection(COL_MAPPINGS).document(
                safe.mapping_id
            ).set(model_to_document(safe))
        elif isinstance(safe, InvestmentPlanValidationReceipt):
            plan = self.get_plan(safe.plan_id)
            if plan is None:
                raise LookupError(safe.plan_id)
            self._workspace(plan.tenant_id, plan.workspace_id).collection(COL_RECEIPTS).document(
                safe.receipt_id
            ).set(model_to_document(safe))
        return safe

    def get_plan(self, plan_id: str) -> InvestmentPlan | None:
        snap = self._db.collection(COL_INDEX).document(f"plan__{plan_id}").get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        doc = (
            self._workspace(str(data["tenant_id"]), str(data["workspace_id"]))
            .collection(COL_PLANS)
            .document(plan_id)
            .get()
        )
        if not doc.exists:
            return None
        return document_to_model(InvestmentPlan, doc.to_dict())

    def list_plans(self, *, project_id: str) -> tuple[InvestmentPlan, ...]:
        del project_id
        return ()

    def get_source(self, source_version_id: str) -> BudgetDriveSourceVersion | None:
        del source_version_id
        return None

    def get_mapping(self, mapping_id: str) -> BudgetColumnMapping | None:
        del mapping_id
        return None

    def get_receipt(self, receipt_id: str) -> InvestmentPlanValidationReceipt | None:
        del receipt_id
        return None
