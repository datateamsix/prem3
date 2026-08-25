"""Thin MTA domain service for M5-00 architecture foundation."""

from __future__ import annotations

from app.modeling.mta.channel_grouping import build_channel_grouping
from app.modeling.mta.contracts import (
    AttributionModelId,
    MTAChannelGrouping,
    MTAChannelGroupingRule,
    MTAInputContract,
    MTAOverviewReadModel,
    MTAProvisioningPlan,
    MTAProvisioningReceipt,
    MTAReadinessReceipt,
    MTATrackConfig,
)
from app.modeling.mta.ga4_discovery import TableLister, discover_ga4_exports
from app.modeling.mta.input_contract import build_input_contract
from app.modeling.mta.overview import assemble_mta_overview
from app.modeling.mta.provisioning import (
    compile_mta_provisioning_plan,
    execute_mta_provisioning_plan_fake,
)
from app.modeling.mta.readiness import evaluate_mta_readiness
from app.modeling.mta.repository import InMemoryMTARepository
from app.modeling.mta.states import MTATrackStage


class MTAService:
    def __init__(self, repo: InMemoryMTARepository | None = None) -> None:
        self.repo = repo or InMemoryMTARepository()

    def upsert_config(self, *, track_id: str, config: MTATrackConfig) -> MTATrackConfig:
        return self.repo.put_config(track_id=track_id, config=config)

    def get_config(self, track_id: str) -> MTATrackConfig | None:
        return self.repo.get_config(track_id)

    def discover_ga4(self, catalog: TableLister, *, gcp_project_id: str):
        return discover_ga4_exports(catalog, gcp_project_id=gcp_project_id)

    def save_grouping(
        self,
        *,
        version: str,
        rules: tuple[MTAChannelGroupingRule, ...] | list[MTAChannelGroupingRule],
        created_by: str,
        approved_by: str | None = None,
        business_profile_snapshot_id: str | None = None,
    ) -> MTAChannelGrouping:
        grouping = build_channel_grouping(
            version=version,
            rules=rules,
            created_by=created_by,
            approved_by=approved_by,
            business_profile_snapshot_id=business_profile_snapshot_id,
        )
        return self.repo.put_grouping(grouping)

    def create_input_contract(self, **kwargs) -> MTAInputContract:
        contract = build_input_contract(**kwargs)
        return self.repo.put_contract(contract)

    def evaluate_readiness(
        self,
        *,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        track_id: str,
        contract: MTAInputContract | None,
        **kwargs,
    ) -> MTAReadinessReceipt:
        receipt = evaluate_mta_readiness(
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            contract=contract,
            **kwargs,
        )
        return self.repo.put_readiness(receipt)

    def compile_provisioning_plan(
        self,
        *,
        plan_id: str,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        track_id: str,
        gcp_project_id: str,
        channel_grouping_version: str,
        models: tuple[AttributionModelId, ...] = (),
    ) -> MTAProvisioningPlan:
        plan = compile_mta_provisioning_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            gcp_project_id=gcp_project_id,
            channel_grouping_version=channel_grouping_version,
            models=models,
        )
        return self.repo.put_plan(plan)

    def execute_provisioning_fake(
        self, plan: MTAProvisioningPlan, *, existing: set[str] | None = None
    ) -> MTAProvisioningReceipt:
        receipt = execute_mta_provisioning_plan_fake(plan, existing_assets=existing)
        return self.repo.put_provisioning_receipt(receipt)

    def overview(
        self,
        *,
        project_id: str,
        cycle_id: str,
        track_id: str | None,
        foundation_ready: bool,
        track_id_for_config: str | None = None,
    ) -> MTAOverviewReadModel:
        tid = track_id_for_config or track_id or ""
        config = self.repo.get_config(tid) if tid else None
        readiness = self.repo.get_readiness(tid) if tid else None
        contract = None
        if readiness and readiness.input_contract_fingerprint:
            for item in self.repo.contracts.values():
                if item.fingerprint == readiness.input_contract_fingerprint:
                    contract = item
                    break
        return assemble_mta_overview(
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            foundation_ready=foundation_ready,
            config=config,
            readiness=readiness,
            contract=contract,
        )

    def mark_configuring(self, track_id: str) -> MTATrackConfig:
        config = self.repo.get_config(track_id) or MTATrackConfig()
        updated = config.model_copy(
            update={"domain_stage": MTATrackStage.CONFIGURING}
        )
        return self.repo.put_config(track_id=track_id, config=updated)
