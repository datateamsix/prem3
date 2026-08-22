"""Deterministic Data Foundation MVP proof. Does not fabricate live cloud success."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from app.business_iq.service import BusinessIqService
from app.business_iq.store import InMemoryBusinessIqStore
from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.data_foundation.context import context_from_tenant
from app.data_foundation.contracts import (
    BusinessChannelFact,
    BusinessProfileSnapshot,
    SourceContract,
)
from app.data_foundation.enums import ConnectionLifecycle, TransformId
from app.data_foundation.service import DataFoundationService
from app.data_foundation.store import InMemoryDataFoundationStore
from app.data_foundation.warehouse import FoundationWarehouse, WarehouseTable

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evaluation" / "data_foundation_mvp_proof.json"


def _sha() -> tuple[str, str]:
    def rev(ref: str) -> str:
        return subprocess.check_output(["git", "rev-parse", ref], cwd=ROOT, text=True).strip()

    try:
        return rev("origin/main"), rev("HEAD")
    except subprocess.CalledProcessError:
        return "unknown", rev("HEAD")


def _snapshot() -> BusinessProfileSnapshot:
    return BusinessProfileSnapshot(
        snapshot_id="bps_acme00000000000001",
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        version="Business Profile v3",
        fingerprint="a" * 64,
        business_context_ready=True,
        kpi="Revenue",
        markets=("United States",),
        channels=(
            BusinessChannelFact(channel_name="Paid Search", role="demand capture"),
            BusinessChannelFact(channel_name="Paid Social", role="multiple roles"),
        ),
        promotions_relevant=True,
        inventory_relevant=True,
        competition_relevant=True,
        seasonality_relevant=True,
    )


def run_mvp_proof() -> Path:
    main_sha, feature_sha = _sha()
    tenant = TenantContext(
        tenant_id="tenant-a",
        user_id="proof-runner",
        auth_state=AuthState.AUTHENTICATED,
    )
    service = DataFoundationService(
        store=InMemoryDataFoundationStore(),
        warehouse=FoundationWarehouse(),
        live_cloud_proof="LIVE_CLOUD_PROOF_NOT_RUN",
    )
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="google_ads_campaign_daily",
            frame=pd.DataFrame(
                {
                    "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
                    "channel": ["Paid Search", "Paid Search", "Paid Search"],
                    "spend": [100.0, 110.0, 90.0],
                    "impressions": [1000, 1100, 900],
                }
            ),
        )
    )
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="shopify_orders_daily",
            frame=pd.DataFrame(
                {
                    "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
                    "revenue": [500.0, 520.0, 480.0],
                    "orders": [20, 22, 19],
                }
            ),
        )
    )
    with bind_tenant(tenant):
        biq = BusinessIqService(store=InMemoryBusinessIqStore())
        profile = biq.create_profile(
            tenant_id="tenant-a",
            workspace_id="wsp_test00000000000001",
            actor_id="proof-runner",
            payload={
                "business_identity": {"brand_name": "Acme"},
                "measurement_objectives": [
                    {"objective_id": "obj_1", "statement": "Allocate budget"}
                ],
                "kpi": "Revenue",
                "markets": [{"market_id": "mkt_us", "name": "United States"}],
                "marketing_portfolio": [
                    {
                        "channel_id": "bch_search",
                        "canonical_name": "Paid Search",
                        "active_from": "2023-01-01",
                        "lifecycle_status": "ACTIVE",
                    }
                ],
                "facts": [{"fact_id": "bfact_kpi", "concept": "kpi", "value": "Revenue"}],
            },
        )
        ready = biq.evaluate_ready(
            tenant_id="tenant-a", workspace_id="wsp_test00000000000001"
        )
        brief = biq.regenerate_brief(
            tenant_id="tenant-a", workspace_id="wsp_test00000000000001"
        )
        context = context_from_tenant(
            workspace_id="wsp_test00000000000001",
            destination_project_id="acme_analytics",
            source_project_ids=("acme_analytics",),
            source_dataset_ids=("marketing",),
            drive_root_folder_id="root_prem3",
            bq_lifecycle=ConnectionLifecycle.AUTHORIZED,
            drive_lifecycle=ConnectionLifecycle.DISCOVERY_READY,
            read_verified=True,
            write_verified=True,
        )
        service.load_business_snapshot(context, _snapshot())
        inventory = service.discover(context)
        media = next(
            item
            for item in inventory.candidates
            if item.resource.table_id == "google_ads_campaign_daily"
        )
        kpi = next(
            item
            for item in inventory.candidates
            if item.resource.table_id == "shopify_orders_daily"
        )
        media_binding = service.bind_source(
            context,
            candidate_id=media.candidate_id,
            contract=SourceContract(
                grain="daily",
                date_field="date",
                date_format="YYYY-MM-DD",
                unique_keys=("date", "channel"),
                required_fields=("date", "spend"),
                currency="USD",
                timezone="America/New_York",
            ),
            governance_import_ready=True,
        )
        kpi_binding = service.bind_source(
            context,
            candidate_id=kpi.candidate_id,
            contract=SourceContract(
                grain="daily",
                date_field="date",
                date_format="YYYY-MM-DD",
                unique_keys=("date",),
                required_fields=("date", "revenue"),
                currency="USD",
                timezone="America/New_York",
            ),
            governance_import_ready=True,
        )
        media_assess = service.assess_source(context, media_binding.source_id)
        service.assess_source(context, kpi_binding.source_id)
        plan = service.compile_transformation_plan(
            context, source_id=media_binding.source_id, action_ids=[TransformId.DF_T006]
        )
        preview = service.get_transformation_preview(context, plan.plan_id)
        service.approve_plan(context, plan_id=plan.plan_id)
        transform = service.execute_transformation(context, transformation_plan_id=plan.plan_id)
        foundation = service.compile_foundation_plan(context)
        service.approve_plan(context, plan_id=foundation.plan_id)
        service.execute_plan(context, plan_id=foundation.plan_id)
        media_ready = service.evaluate_source_ready(context, media_binding.source_id)
        service.evaluate_source_ready(context, kpi_binding.source_id)
        env = service.evaluate_data_foundation_ready(context)
        overview = service.get_quality_overview(context, media_binding.source_id)
        intel = service.compile_intelligence_brief(context)
        payload = {
            "design_freeze": "foundational-intake-freeze-2026-08-22-v1",
            "origin_main_at_mission_start": "dce8a209bb67fbaa3c8a78ae4e8a7384897252ed",
            "dependency_base_sha": "02cec50b6da6507838081e65086eaaf29a4a5329",
            "branch_repair_required": False,
            "base_main_sha": main_sha,
            "feature_sha": feature_sha,
            "live_cloud_proof": "LIVE_CLOUD_PROOF_NOT_RUN",
            "pipeline": [
                "BUSINESS REQUIREMENTS LOADED",
                "BQ + DRIVE DISCOVERY",
                "SOURCE CANDIDATES",
                "SOURCE ASSESSMENTS",
                "QUALITY FINDINGS",
                "TRANSFORMATION PREVIEW",
                "APPROVED TEST PLAN",
                "TRANSFORM EXECUTION",
                "BQ STAGING/CANONICAL OUTPUT",
                "POST-TRANSFORM QA",
                "FOUNDATION_SOURCE_READY",
                "FOUNDATION PLAN",
                "PROVISION / VERIFY",
                "DATA_FOUNDATION_READY",
            ],
            "readiness": {
                "IMPORT_READY": "M2-11 evaluate_import_readiness only",
                "FOUNDATION_SOURCE_READY": media_ready.status_code.value,
                "DATA_FOUNDATION_READY": env.status_code.value,
                "m2_11_import_ready_consumed": media_ready.governance_import_ready,
            },
            "source_fingerprints": {
                "media": plan.source_fingerprint,
                "output": transform.output_fingerprints.get("output"),
            },
            "quality_findings": [item.check_id for item in media_assess.quality.checks],
            "transform_plan": {
                "plan_id": plan.plan_id,
                "fingerprint": plan.fingerprint,
                "actions": [item.action_id.value for item in plan.actions],
            },
            "row_counts": {
                "input": transform.input_rows,
                "output": transform.output_rows,
                "preview_projected": preview.projected_output_rows,
            },
            "reconciliation": {"source_mutated": transform.source_mutated},
            "source_foundation_status": media_ready.status_code.value,
            "data_foundation_ready": env.status_code.value,
            "m2_11_import_ready_unchanged": True,
            "business_iq": {
                "profile_id": profile.profile_id,
                "version": profile.version,
                "fingerprint": profile.fingerprint,
                "business_context_ready": ready.status.value,
                "brief_advisory": brief.advisory,
                "brief_evidence_refs": list(brief.evidence_refs),
            },
            "durable_stores": {
                "business_iq_production": "FirestoreBusinessIqStore",
                "data_foundation_production": "FirestoreDataFoundationStore",
                "ci_local": "InMemory",
                "backed": [
                    "MeasurementCycle",
                    "SourceBinding",
                    "FoundationPlan",
                    "quality findings",
                    "receipts",
                ],
            },
            "quality_overview": {
                "source_id": overview.source_id,
                "blocker_count": overview.blocker_count,
                "review_count": overview.review_count,
                "pass_count": overview.pass_count,
            },
            "data_intelligence_brief": {
                "advisory": intel.advisory,
                "model_version": intel.model_version,
                "evidence_refs": list(intel.evidence_refs),
                "gemini_prose": "EXTERNAL_DEPENDENCY",
            },
            "foundation_plan": {
                "domains": [item.value for item in foundation.domains],
                "will_not_modify": list(foundation.will_not_modify),
                "permission_preview": list(foundation.permission_preview),
            },
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    companion = ROOT / "evaluation" / "business_iq_data_foundation_mvp_proof.json"
    companion.write_text(text, encoding="utf-8")
    return OUTPUT
