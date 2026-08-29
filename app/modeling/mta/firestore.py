"""Compact Firestore twin for MTA metadata. Never stores large journeys."""

from __future__ import annotations

from typing import Any

from app.control_plane.serialization import document_to_model, model_to_document
from app.modeling.mta.contracts import (
    MTAChannelGrouping,
    MTAInputContract,
    MTAProvisioningPlan,
    MTAProvisioningReceipt,
    MTAReadinessReceipt,
    MTATrackConfig,
)
from app.modeling.mta.results_contracts import (
    MTADecisionIntelligenceBrief,
    MTAResultPointers,
    MTAResultSnapshotMetadata,
)

COL_TENANTS = "tenants"
COL_WORKSPACES = "workspaces"
COL_INDEX = "mta_modeling_index"


class FirestoreMTARepository:
    """Production metadata store for M5-00 contracts — compact documents only."""

    def __init__(self, client: Any) -> None:
        self._db = client

    def _ws(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COL_TENANTS)
            .document(tenant_id)
            .collection(COL_WORKSPACES)
            .document(workspace_id)
        )

    def _index(self, kind: str, key: str, tenant_id: str, workspace_id: str) -> None:
        self._db.collection(COL_INDEX).document(f"{kind}__{key}").set(
            {"tenant_id": tenant_id, "workspace_id": workspace_id, "kind": kind}
        )

    def _put(
        self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model: Any
    ) -> None:
        self._ws(tenant_id, workspace_id).collection(collection).document(doc_id).set(
            model_to_document(model)
        )

    def _get(
        self, tenant_id: str, workspace_id: str, collection: str, doc_id: str, model_type: Any
    ):
        snap = self._ws(tenant_id, workspace_id).collection(collection).document(doc_id).get()
        if not snap.exists:
            return None
        return document_to_model(model_type, snap.to_dict())

    def put_config(
        self, *, tenant_id: str, project_id: str, track_id: str, config: MTATrackConfig
    ) -> MTATrackConfig:
        self._put(tenant_id, project_id, "mta_track_configs", track_id, config)
        self._index("mta_config", track_id, tenant_id, project_id)
        return config

    def get_config(
        self, *, tenant_id: str, project_id: str, track_id: str
    ) -> MTATrackConfig | None:
        return self._get(tenant_id, project_id, "mta_track_configs", track_id, MTATrackConfig)

    def put_contract(
        self, *, tenant_id: str, project_id: str, contract: MTAInputContract
    ) -> MTAInputContract:
        self._put(
            tenant_id,
            project_id,
            "mta_input_contracts",
            contract.input_contract_id,
            contract,
        )
        self._index(
            "mta_input_contract",
            contract.input_contract_id,
            tenant_id,
            project_id,
        )
        return contract

    def get_contract(
        self, *, tenant_id: str, project_id: str, input_contract_id: str
    ) -> MTAInputContract | None:
        return self._get(
            tenant_id, project_id, "mta_input_contracts", input_contract_id, MTAInputContract
        )

    def put_readiness(
        self, *, tenant_id: str, project_id: str, receipt: MTAReadinessReceipt
    ) -> MTAReadinessReceipt:
        self._put(tenant_id, project_id, "mta_readiness", receipt.track_id, receipt)
        self._index("mta_readiness", receipt.track_id, tenant_id, project_id)
        return receipt

    def get_readiness(
        self, *, tenant_id: str, project_id: str, track_id: str
    ) -> MTAReadinessReceipt | None:
        return self._get(tenant_id, project_id, "mta_readiness", track_id, MTAReadinessReceipt)

    def put_grouping(
        self, *, tenant_id: str, project_id: str, grouping: MTAChannelGrouping
    ) -> MTAChannelGrouping:
        existing = self.get_grouping(
            tenant_id=tenant_id, project_id=project_id, version=grouping.version
        )
        if existing is not None and existing.fingerprint != grouping.fingerprint:
            raise ValueError(f"Cannot mutate channel grouping version {grouping.version}.")
        self._put(tenant_id, project_id, "mta_channel_groupings", grouping.version, grouping)
        self._index("mta_channel_grouping", grouping.version, tenant_id, project_id)
        return grouping

    def get_grouping(
        self, *, tenant_id: str, project_id: str, version: str
    ) -> MTAChannelGrouping | None:
        return self._get(
            tenant_id, project_id, "mta_channel_groupings", version, MTAChannelGrouping
        )

    def put_plan(
        self, *, tenant_id: str, project_id: str, plan: MTAProvisioningPlan
    ) -> MTAProvisioningPlan:
        self._put(tenant_id, project_id, "mta_provisioning_plans", plan.plan_id, plan)
        self._index("mta_provisioning_plan", plan.plan_id, tenant_id, project_id)
        return plan

    def put_provisioning_receipt(
        self, *, tenant_id: str, project_id: str, receipt: MTAProvisioningReceipt
    ) -> MTAProvisioningReceipt:
        self._put(tenant_id, project_id, "mta_provisioning_receipts", receipt.receipt_id, receipt)
        self._index("mta_provisioning_receipt", receipt.receipt_id, tenant_id, project_id)
        return receipt

    def put_result_snapshot_metadata(
        self,
        *,
        tenant_id: str,
        project_id: str,
        metadata: MTAResultSnapshotMetadata,
    ) -> MTAResultSnapshotMetadata:
        payload = model_to_document(metadata)
        if any(
            key in payload
            for key in (
                "channel_results",
                "rows",
                "visualizations",
                "journeys",
                "transitions",
            )
        ):
            raise ValueError("Firestore MTA result metadata must stay compact.")
        self._put(
            tenant_id,
            project_id,
            "mta_result_snapshots",
            metadata.result_snapshot_id,
            metadata,
        )
        self._index("mta_result_snapshot", metadata.result_snapshot_id, tenant_id, project_id)
        return metadata

    def get_result_snapshot_metadata(
        self, *, tenant_id: str, project_id: str, result_snapshot_id: str
    ) -> MTAResultSnapshotMetadata | None:
        return self._get(
            tenant_id,
            project_id,
            "mta_result_snapshots",
            result_snapshot_id,
            MTAResultSnapshotMetadata,
        )

    def put_result_pointers(
        self, *, tenant_id: str, project_id: str, pointers: MTAResultPointers
    ) -> MTAResultPointers:
        self._put(tenant_id, project_id, "mta_result_pointers", pointers.track_id, pointers)
        self._index("mta_result_pointers", pointers.track_id, tenant_id, project_id)
        return pointers

    def get_result_pointers(
        self, *, tenant_id: str, project_id: str, track_id: str
    ) -> MTAResultPointers | None:
        return self._get(tenant_id, project_id, "mta_result_pointers", track_id, MTAResultPointers)

    def put_brief_metadata(
        self,
        *,
        tenant_id: str,
        project_id: str,
        brief: MTADecisionIntelligenceBrief,
    ) -> dict[str, Any]:
        compact = {
            "brief_id": brief.brief_id,
            "result_snapshot_id": brief.result_snapshot_id,
            "policy_version": brief.policy_version,
            "fingerprint": brief.fingerprint,
            "generated_at": brief.generated_at.isoformat(),
        }
        self._ws(tenant_id, project_id).collection("mta_decision_briefs").document(
            brief.brief_id
        ).set(compact)
        self._index("mta_decision_brief", brief.brief_id, tenant_id, project_id)
        return compact
