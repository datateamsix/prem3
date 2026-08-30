"""M5-00 MTA architecture foundation tests."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.modeling.mta.channel_grouping import (
    ChannelGroupingValidationError,
    DEFAULT_MUSIC_CENTER_RULES,
    assert_grouping_version_immutable,
    build_channel_grouping,
    compile_channel_grouping_sql,
)
from app.modeling.mta.contracts import (
    AttributionModelId,
    GA4SettlementPolicy,
    MTAReadinessState,
    MTATrackConfig,
    SessionTrafficSourcePolicy,
    ShapleyPreflightState,
)
from app.modeling.mta.ga4_discovery import InMemoryGA4Catalog, discover_ga4_exports
from app.modeling.mta.input_contract import build_input_contract
from app.modeling.mta.language import CausalLanguageError, assert_no_causal_mta_language
from app.modeling.mta.models_registry import all_model_specs, get_model_spec
from app.modeling.mta.policies import (
    settled_through_date,
    select_traffic_source_policy,
)
from app.modeling.mta.provisioning import (
    compile_mta_provisioning_plan,
    execute_mta_provisioning_plan_fake,
)
from app.modeling.mta.readiness import evaluate_mta_readiness
from app.modeling.mta.service import MTAService
from app.modeling.mta.shapley_preflight import run_shapley_preflight
from app.modeling.mta.states import MTATrackStage
from app.project.tracks import mta_availability
from app.control_plane.models import MeasurementTrackStatus
from app.project.enums import CapabilityAvailability, NextActionType


def test_settlement_excludes_recent_days():
    settled = settled_through_date(as_of=date(2026, 6, 30), lag_days=3)
    assert settled == date(2026, 6, 27)


def test_traffic_source_policy_prefers_session_last_click():
    assert (
        select_traffic_source_policy(
            has_session_traffic_source_last_click=True,
            has_collected_traffic_source=True,
        )
        is SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1
    )


def test_ga4_discovery_analytics_datasets():
    catalog = InMemoryGA4Catalog(
        datasets={
            "analytics_123": ["events_20260401", "events_20260402", "events_intraday_20260403"],
            "other_ds": ["t1"],
        },
        schemas={
            ("proj", "analytics_123", "events_20260401"): [
                "event_name",
                "user_pseudo_id",
                "session_traffic_source_last_click",
            ]
        },
    )
    result = discover_ga4_exports(catalog, gcp_project_id="proj", as_of_iso="2026-06-30")
    assert len(result.bindings) == 1
    assert result.bindings[0].property_id == "123"
    assert result.bindings[0].has_session_traffic_source_last_click is True


def test_readiness_fail_closed_without_contract():
    receipt = evaluate_mta_readiness(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        contract=None,
        ga4_dataset_exists=True,
        key_event_present=True,
        conversion_volume_ok=True,
        channel_grouping_approved=True,
        lookback_covered=True,
    )
    assert receipt.state is MTAReadinessState.NOT_READY
    assert "INPUT_CONTRACT_MISSING" in receipt.blocking_failures


def test_readiness_ready_when_gates_pass():
    contract = build_input_contract(
        input_contract_id="ic1",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        ga4_dataset_id="analytics_123",
        conversion_event="purchase",
        conversion_period_start="2026-04-01",
        conversion_period_end="2026-06-30",
        channel_grouping_version="v1",
        attribution_models=(AttributionModelId.MARKOV,),
    )
    receipt = evaluate_mta_readiness(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        contract=contract,
        ga4_dataset_exists=True,
        key_event_present=True,
        conversion_volume_ok=True,
        channel_grouping_approved=True,
        lookback_covered=True,
        user_pseudo_id_coverage=0.9,
    )
    assert receipt.state is MTAReadinessState.MTA_INPUT_READY


def test_channel_grouping_immutable_version():
    g1 = build_channel_grouping(
        version="v1",
        rules=DEFAULT_MUSIC_CENTER_RULES,
        created_by="tester",
        approved_by="tester",
    )
    sql = compile_channel_grouping_sql(g1)
    assert "Paid Search" in sql
    with pytest.raises(ChannelGroupingValidationError):
        assert_grouping_version_immutable(
            existing_version="v1",
            proposed_version="v1",
            existing_fingerprint=g1.fingerprint,
            proposed_fingerprint="different",
        )


def test_provisioning_plan_idempotent():
    plan = compile_mta_provisioning_plan(
        plan_id="plan1",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        gcp_project_id="gcp",
        channel_grouping_version="v1",
        models=(AttributionModelId.MARKOV, AttributionModelId.SHAPLEY),
    )
    r1 = execute_mta_provisioning_plan_fake(plan)
    r2 = execute_mta_provisioning_plan_fake(plan, existing_assets=set(r1.created))
    assert r1.verified and r2.verified
    assert r1.plan_fingerprint == plan.fingerprint
    assert "mta_markov_transitions_plan" in r1.created
    assert "mta_shapley_results_plan" in r1.created
    assert not r2.created or set(r2.created).isdisjoint(set(r1.created)) or r2.reused


def test_shapley_preflight_blocks_large_channel_sets():
    pf = run_shapley_preflight(distinct_channel_count=25)
    assert pf.state is ShapleyPreflightState.NOT_RECOMMENDED


def test_model_registry_has_eight_specs():
    specs = all_model_specs()
    assert len(specs) == 8
    assert "not causal" in get_model_spec(AttributionModelId.MARKOV).assumption.lower() or (
        "Not causal" in get_model_spec(AttributionModelId.MARKOV).assumption
    )


def test_forbidden_causal_language():
    with pytest.raises(CausalLanguageError):
        assert_no_causal_mta_language("Paid Search true contribution is high")
    assert_no_causal_mta_language("Paid Search attributed credit is 34%")


def test_overview_not_ready_before_foundation():
    service = MTAService()
    overview = service.overview(
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        foundation_ready=False,
    )
    assert overview.readiness_state is MTAReadinessState.NOT_READY
    assert overview.next_action.action_type == "CONTINUE_DATA_FOUNDATION"
    assert overview.epistemic_label == "Observable journey attribution"
    assert overview.latest_result_state == "NOT_AVAILABLE"


def test_mta_availability_distinguishes_input_ready():
    status, avail, ctx, action = mta_availability(
        entitled=True,
        foundation_ready=True,
        ga4_dataset_id="analytics_1",
        key_event_name="purchase",
        channel_grouping_version="v1",
        mta_input_ready=True,
    )
    assert status is MeasurementTrackStatus.READY_TO_RUN
    assert "MTA_INPUT_READY" in ctx
    assert action is NextActionType.OPEN_MTA
    assert avail is CapabilityAvailability.IN_PROGRESS


def test_service_end_to_end_config_grouping_contract():
    service = MTAService()
    service.upsert_config(
        track_id="tr1",
        config=MTATrackConfig(
            ga4_dataset_id="analytics_999",
            ga4_property_id="999",
            key_event_name="purchase",
            conversion_period_start="2026-04-01",
            conversion_period_end="2026-06-30",
            channel_grouping_version="v1",
            domain_stage=MTATrackStage.CONFIGURING,
            attribution_models=(AttributionModelId.FIRST_TOUCH, AttributionModelId.MARKOV),
            settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        ),
    )
    grouping = service.save_grouping(
        version="v1",
        rules=DEFAULT_MUSIC_CENTER_RULES,
        created_by="tester",
        approved_by="tester",
    )
    contract = service.create_input_contract(
        input_contract_id="ic-mc",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        ga4_dataset_id="analytics_999",
        ga4_property_id="999",
        conversion_event="purchase",
        conversion_period_start="2026-04-01",
        conversion_period_end="2026-06-30",
        channel_grouping_version=grouping.version,
        attribution_models=(AttributionModelId.MARKOV,),
    )
    receipt = service.evaluate_readiness(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        contract=contract,
        ga4_dataset_exists=True,
        key_event_present=True,
        conversion_volume_ok=True,
        channel_grouping_approved=True,
        lookback_covered=True,
        user_pseudo_id_coverage=1.0,
    )
    assert receipt.state is MTAReadinessState.MTA_INPUT_READY
    overview = service.overview(
        project_id="p1", cycle_id="c1", track_id="tr1", foundation_ready=True
    )
    assert overview.domain_stage is MTATrackStage.MTA_INPUT_READY


def test_api_mta_overview_route():
    from app.control_plane.entitlements import PlanId
    from app.control_plane.memory import InMemoryControlPlaneRepository
    from app.service.app import create_app
    from app.service.auth import FakeIdentityVerifier
    from tests.unit.api_support import auth_header, seed_tenant

    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    app = create_app(
        control_plane_repository=repo,
        identity_verifier=FakeIdentityVerifier(default=identity),
    )
    client = TestClient(app, raise_server_exceptions=False)
    headers = auth_header()
    project_id = client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "MTA Project", "scope_type": "BRAND"},
    ).json()["project_id"]
    # Ensure cycle tracks exist via home or tracks endpoint
    tracks = client.get(f"/v1/projects/{project_id}/cycles/cycle-mta/tracks", headers=headers)
    assert tracks.status_code in {200, 404}
    resp = client.get(f"/v1/projects/{project_id}/cycles/cycle-mta/mta", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["epistemic_label"] == "Observable journey attribution"
    assert body["acceptance_computed_by_server"] is True
    assert body["latest_result_state"] == "NOT_AVAILABLE"
    assert "causal" not in body["next_action"]["statement"].lower()
    assert "incremental contribution" not in body["next_action"]["statement"].lower()
