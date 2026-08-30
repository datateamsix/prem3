"""M5-01A unit tests — channel bindings, planner, manifest, schedule approval."""

from __future__ import annotations

from datetime import date

import pytest

from app.business_iq.contracts import (
    BusinessIdentity,
    BusinessProfile,
    BusinessProfileSnapshot,
    MarketingChannel,
)
from app.core.contracts import utc_now
from app.domain.channels import (
    AI_SEARCH_CHANNEL_ID,
    cached_channel_registry,
    cross_method_join_on_channel_id,
    extract_udf_literal_channel_ids,
    music_center_default_bindings,
    resolve_mmm_variable_to_channel,
)
from app.domain.channels.bindings import PlanningChannelAllocation, build_channel_binding
from app.modeling.mta.parameter_explanations import parameter_explanations
from app.modeling.mta.provisioning_service import MTAProvisioningService
from app.modeling.mta.refresh import (
    MTARefreshWindowPlanner,
    build_scheduled_refresh_plan,
    provision_scheduled_refresh_fake,
)
from app.modeling.mta.runtime_contracts import ScheduledRefreshApprovalStatus
from app.modeling.mta.sql.registry import (
    REQUIRED_ASSET_IDS,
    REQUIRED_ASSET_TYPE_CLASSES,
    cached_sql_asset_manifest,
    load_sql_asset_manifest,
    resolve_asset_path,
)
from app.modeling.mta.sql.renderer import render_sql_asset
from app.modeling.mta.synthetic_music_center import EVIDENCE_LABEL


def test_business_profile_channel_ids_exist_in_registry():
    registry = cached_channel_registry()
    channel = MarketingChannel(
        channel_id="local_biq_1",
        canonical_name="Paid Search",
        registry_channel_id="search_paid",
        channel_registry_version=registry.channel_registry_version,
    )
    assert channel.registry_channel_id in registry.channel_ids()


def test_mmm_channel_binding_uses_registry_id():
    assert resolve_mmm_variable_to_channel("paid_search") == "search_paid"
    assert resolve_mmm_variable_to_channel("ai_search") == AI_SEARCH_CHANNEL_ID


def test_mta_udf_outputs_use_registry_ids():
    registry = cached_channel_registry()
    entry = cached_sql_asset_manifest().get("channel_grouping_v1")
    sql, _ = render_sql_asset(
        entry, params={"project_id": "p", "modeling_dataset": "prem3_modeling"}
    )
    ids = extract_udf_literal_channel_ids(sql)
    assert ids <= registry.channel_ids()
    assert AI_SEARCH_CHANNEL_ID in ids


def test_planning_channel_binding_uses_registry_id():
    alloc = PlanningChannelAllocation(
        allocation_id="a1",
        channel_id="search_paid",
        channel_registry_version=1,
        amount=1000.0,
    )
    assert alloc.channel_id in cached_channel_registry().channel_ids()


def test_ai_search_available_to_biq_mmm_mta_planning():
    bindings = {b.channel_id: b for b in music_center_default_bindings()}
    assert AI_SEARCH_CHANNEL_ID in bindings
    b = bindings[AI_SEARCH_CHANNEL_ID]
    assert b.business_profile_channel_ref
    assert "ai_search" in b.mmm_variable_refs
    assert b.mta_grouping_refs
    assert b.planning_allocation_refs


def test_cross_method_channel_join_requires_no_label_fuzzy_matching():
    joined = cross_method_join_on_channel_id(
        biq_registry_channel_ids={"search_paid", AI_SEARCH_CHANNEL_ID},
        mmm_channel_ids={"search_paid", AI_SEARCH_CHANNEL_ID},
        mta_channel_ids={"search_paid", AI_SEARCH_CHANNEL_ID, "direct"},
        planning_channel_ids={"search_paid", AI_SEARCH_CHANNEL_ID},
    )
    assert joined == {"search_paid", AI_SEARCH_CHANNEL_ID}
    # Display labels must not be used as join keys
    assert "Paid Search" not in joined


def test_historical_business_profile_snapshot_preserves_registry_version():
    now = utc_now()
    profile = BusinessProfile(
        profile_id="p1",
        tenant_id="t1",
        workspace_id="w1",
        version=1,
        fingerprint="fp",
        current_snapshot_id="snap_old",
        business_identity=BusinessIdentity(),
        marketing_portfolio=(
            MarketingChannel(channel_id="legacy_local", canonical_name="Paid Search"),
        ),
        created_at=now,
        updated_at=now,
        updated_by="u",
        created_by="u",
    )
    historical = BusinessProfileSnapshot(
        snapshot_id="snap_old",
        profile_id="p1",
        tenant_id="t1",
        workspace_id="w1",
        version=1,
        fingerprint="fp",
        profile=profile,
        created_at=now,
        created_by="u",
        immutable=True,
        channel_registry_version=None,
    )
    assert historical.immutable is True
    assert historical.channel_registry_version is None
    newer = historical.model_copy(update={"channel_registry_version": 1, "snapshot_id": "snap_new"})
    assert newer.channel_registry_version == 1
    assert historical.channel_registry_version is None


@pytest.mark.parametrize("lookback", [7, 30, 60, 90])
def test_refresh_window_lookback_expands_source(lookback: int):
    window = MTARefreshWindowPlanner().plan(
        run_date="2024-06-10",
        settlement_days=3,
        source_overlap_days=2,
        lookback_window_days=lookback,
    )
    start = date.fromisoformat(window.source_start_date)
    end = date.fromisoformat(window.source_end_date)
    assert end == date(2024, 6, 7)
    assert (end - start).days == lookback + 2
    assert window.calculation_trace
    assert any("lookback" in step for step in window.calculation_trace)


def test_refresh_window_watermark_clamp():
    window = MTARefreshWindowPlanner().plan(
        run_date="2024-06-10",
        settlement_days=3,
        source_overlap_days=2,
        lookback_window_days=30,
        last_watermark_date="2024-06-05",
    )
    assert window.source_start_date == "2024-06-03"
    assert "watermark" in " ".join(window.calculation_trace)


def test_schedule_plan_requires_approval():
    plan = build_scheduled_refresh_plan(
        schedule_id="s1",
        conversion_event="purchase",
        lookback_window_days=30,
    )
    assert plan.approval_status is ScheduledRefreshApprovalStatus.DRAFT
    with pytest.raises(PermissionError):
        provision_scheduled_refresh_fake(plan)


def test_schedule_cannot_provision_without_approval():
    svc = MTAProvisioningService(live=False)
    plan = build_scheduled_refresh_plan(
        schedule_id="s2", conversion_event="purchase", lookback_window_days=7
    )
    with pytest.raises(PermissionError):
        svc.provision_schedule(
            plan, gcp_project_id="modelready-m3", query_sql="SELECT 1"
        )


def test_schedule_update_changes_fingerprint():
    a = build_scheduled_refresh_plan(
        schedule_id="s3", conversion_event="purchase", lookback_window_days=30
    )
    b = build_scheduled_refresh_plan(
        schedule_id="s3", conversion_event="purchase", lookback_window_days=60
    )
    assert a.fingerprint != b.fingerprint


def test_schedule_target_is_bound_prem3_modeling():
    svc = MTAProvisioningService(live=False)
    ux = svc.render_ready_plan_view(
        gcp_project_id="modelready-m3",
        ga4_dataset_id="analytics_music_center_synthetic",
    )
    assert ux["dataset"] == "prem3_modeling"
    assert ux["evidence_label"] == EVIDENCE_LABEL


def test_manifest_contains_required_mta_assets():
    manifest = load_sql_asset_manifest()
    ids = {a.asset_id for a in manifest.assets}
    assert set(REQUIRED_ASSET_IDS) <= ids


def test_every_manifest_template_exists():
    for entry in load_sql_asset_manifest().assets:
        assert resolve_asset_path(entry).is_file()


def test_manifest_dependencies_resolve():
    manifest = load_sql_asset_manifest()
    ids = {a.asset_id for a in manifest.assets}
    for entry in manifest.assets:
        for dep in entry.dependencies:
            assert dep in ids


def test_rendered_assets_are_deterministic():
    entry = cached_sql_asset_manifest().get("channel_grouping_v1")
    params = {"project_id": "p", "modeling_dataset": "prem3_modeling"}
    a, fa = render_sql_asset(entry, params=params)
    b, fb = render_sql_asset(entry, params=params)
    assert a == b and fa == fb


def test_historical_asset_versions_are_immutable():
    entry = cached_sql_asset_manifest().get("channel_grouping_v1")
    assert entry.immutable_after_first_run is True


def test_no_unknown_channel_ids_in_default_udf():
    test_mta_udf_outputs_use_registry_ids()


def test_parameter_explanations_cover_mission_keys():
    expl = parameter_explanations()
    assert "lookback_window_days" in expl
    assert "TIME_DECAY.decay_over_time" in expl
    assert "MARKOV.transition_to_same_state" in expl
    assert "SHAPLEY.size" in expl


def test_build_channel_binding_fingerprint_stable():
    a = build_channel_binding(channel_id="search_paid", mmm_variable_refs=("paid_search",))
    b = build_channel_binding(channel_id="search_paid", mmm_variable_refs=("paid_search",))
    assert a.fingerprint == b.fingerprint


def test_manifest_asset_types_recognized():
    for entry in load_sql_asset_manifest().assets:
        assert entry.asset_type in REQUIRED_ASSET_TYPE_CLASSES


def test_provisioning_fake_requires_approval():
    svc = MTAProvisioningService(live=False)
    plan = svc.compile_infrastructure_plan(
        plan_id="p1",
        tenant_id="t",
        project_id="proj",
        cycle_id="c",
        track_id="tr",
        gcp_project_id="modelready-m3",
    )
    with pytest.raises(PermissionError):
        svc.provision_infrastructure(plan, approved=False)
    receipt = svc.provision_infrastructure(plan, approved=True)
    assert receipt.verified is True
