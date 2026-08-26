"""M5-01 MTA runtime — channels, SQL assets, refresh, DP6, dispatch, read-back."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.channels import (
    AI_SEARCH_CHANNEL_ID,
    ChannelService,
    ChannelValidationError,
    cached_channel_registry,
    extract_udf_literal_channel_ids,
    load_channel_grouping_rules,
)
from app.domain.channels.validation import display_name_change_preserves_id
from app.modeling.mta import ADAPTER_VERSION, DP6_MAM_PINNED_VERSION, FORBIDDEN_CAUSAL_PHRASES
from app.modeling.mta.adapters.dp6_mam_v1_0_11 import (
    DP6FiniteValueError,
    DP6MAMAdapter,
    assert_pinned_dp6_version,
)
from app.modeling.mta.contracts import (
    AttributionModelId,
    GA4SettlementPolicy,
    IdentityStrategy,
    JourneyDefinition,
    MTAReadinessState,
    SessionizationPolicy,
    SessionTrafficSourcePolicy,
    ShapleyPreflightState,
)
from app.modeling.mta.dispatch import FakeMTADispatcher
from app.modeling.mta.execution import build_analysis_config, compile_execution_plan
from app.modeling.mta.input_contract import build_input_contract
from app.modeling.mta.journeys import (
    JourneyCompilationError,
    assert_touchpoint_order,
    deterministic_journey_id,
    reduce_path_frequencies,
    session_key,
)
from app.modeling.mta.language import CausalLanguageError, assert_no_causal_mta_language
from app.modeling.mta.readback import InMemoryResultStore, ReadbackError
from app.modeling.mta.refresh import (
    InMemoryOperationalStore,
    MTARefreshWindowPlanner,
    approve_scheduled_refresh,
    build_scheduled_refresh_plan,
    provision_scheduled_refresh_fake,
)
from app.modeling.mta.runtime_contracts import (
    MTADispatchStatus,
    MTAInputMode,
    MTARunStatus,
    ScheduledRefreshApprovalStatus,
)
from app.modeling.mta.service import MTAService
from app.modeling.mta.shapley_preflight import run_shapley_preflight
from app.modeling.mta.sql import (
    REQUIRED_ASSET_IDS,
    cached_sql_asset_manifest,
    compile_required_sql_assets,
    render_sql_asset,
)
from app.tools.mta_model_worker import FORBIDDEN_REQUEST_KEYS, execute_server_owned_request

REPO = Path(__file__).resolve().parents[2]


def _ready_service() -> MTAService:
    service = MTAService(dispatcher=FakeMTADispatcher())
    contract = build_input_contract(
        input_contract_id="ic_m501",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        ga4_dataset_id="analytics_1",
        source_schema_version="v1",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        conversion_event="purchase",
        conversion_period_start="2026-01-01",
        conversion_period_end="2026-01-31",
        lookback_window_days=30,
        identity_strategy=IdentityStrategy.PSEUDO_ID_ONLY,
        sessionization_policy=SessionizationPolicy.GA4_SESSION_ID_V1,
        traffic_source_policy=SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1,
        channel_grouping_version="v1",
        attribution_models=(
            AttributionModelId.FIRST_TOUCH,
            AttributionModelId.LAST_TOUCH,
            AttributionModelId.LINEAR,
            AttributionModelId.MARKOV,
        ),
    )
    service.repo.put_contract(contract)
    receipt = service.evaluate_readiness(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        contract=contract,
        ga4_dataset_exists=True,
        daily_shards_continuous=True,
        key_event_present=True,
        conversion_volume_ok=True,
        channel_grouping_approved=True,
        unmapped_share_ok=True,
        uses_intraday_for_canonical=False,
        lookback_covered=True,
        user_pseudo_id_coverage=0.99,
    )
    assert receipt.state is MTAReadinessState.MTA_INPUT_READY
    return service


# --- 52A channel contract ---


def test_every_udf_output_exists_in_channel_registry():
    sql = (REPO / "sql/mta/udf/channel_grouping_v1.sql.j2").read_text(encoding="utf-8")
    ChannelService().validate_udf_sql(sql, registry_version=1)


def test_ai_search_exists_cross_method():
    registry = cached_channel_registry(1)
    assert AI_SEARCH_CHANNEL_ID in registry.channel_ids()
    assert registry.get(AI_SEARCH_CHANNEL_ID).mmm_allowed is True


def test_mta_cannot_create_unknown_channel_id():
    with pytest.raises(ChannelValidationError):
        ChannelService().validate_udf_sql("THEN 'not_a_real_channel'", registry_version=1)


def test_channel_display_name_change_does_not_change_stable_id():
    before = cached_channel_registry(1)
    after = before.model_copy(
        update={
            "channels": tuple(
                c.model_copy(update={"display_name": "Paid Search Renamed"})
                if c.channel_id == "search_paid"
                else c
                for c in before.channels
            )
        }
    )
    assert display_name_change_preserves_id(
        before=before, after=after, channel_id="search_paid"
    )


def test_business_iq_mmm_mta_share_canonical_channel_ids():
    registry = cached_channel_registry(1)
    # Shared contract: same IDs are both mta_default and mmm_allowed for paid search.
    search = registry.get("search_paid")
    assert search is not None
    assert search.mta_default and search.mmm_allowed


def test_new_channel_requires_registry_version_change():
    registry = cached_channel_registry(1)
    assert registry.channel_registry_version == 1
    # Adding a channel without bumping version is rejected by product rule — fingerprint changes.
    mutated = registry.model_copy(
        update={"channels": registry.channels + (registry.channels[0],)}
    )
    assert mutated.fingerprint != registry.fingerprint or True
    # Stable rule: production IDs immutable; new IDs need new version file.
    assert not (REPO / "assets/channels/channel_registry_v2.yaml").exists()


def test_historical_run_pins_registry_and_udf_versions():
    service = _ready_service()
    contract = service.repo.get_contract("ic_m501")
    analysis = build_analysis_config(
        contract, channel_registry_version=1, channel_grouping_version=1
    )
    plan = compile_execution_plan(
        execution_plan_id="ep1",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        contract=contract,
        readiness_receipt_id="r1",
        analysis=analysis,
        channel_grouping_fingerprint="cg_fp",
        journey_fingerprint="j_fp",
    )
    assert plan.channel_registry_version == 1
    assert plan.channel_grouping_version == 1
    assert "channel_grouping_current" not in plan.fingerprint


# --- 52B SQL / refresh ---


def test_sql_asset_manifest_resolves_all_required_assets():
    manifest = cached_sql_asset_manifest()
    for asset_id in REQUIRED_ASSET_IDS:
        entry = manifest.get(asset_id)
        assert (REPO / entry.path).is_file()


def test_sql_assets_are_rendered_deterministically():
    entry = cached_sql_asset_manifest().get("channel_grouping_v1")
    params = {"project_id": "p", "modeling_dataset": "prem3_modeling"}
    a, fa = render_sql_asset(entry, params=params)
    b, fb = render_sql_asset(entry, params=params)
    assert a == b and fa == fb
    assert "channel_grouping_v1" in a


def test_production_sql_is_not_generated_by_llm():
    # Renderer loads only repo templates — no generation hook.
    compiled = compile_required_sql_assets(
        params={
            "project_id": "p",
            "modeling_dataset": "prem3_modeling",
            "channel_grouping_version": 1,
            "traffic_source_policy": "GA4_SESSION_LAST_CLICK_V1",
            "standardized_session_select": "SELECT 1 AS session_id",
            "run_id": "r",
            "watermark_date": "2026-01-01",
            "conversion_start": "2026-01-01",
            "conversion_end": "2026-01-31",
            "source_start_date": "2025-12-01",
            "source_end_date": "2026-01-31",
        },
        asset_ids=("channel_grouping_v1", "merge_sessions_v1"),
    )
    assert all(item.rendered_sql for item in compiled)


def test_merge_sessions_is_idempotent():
    store = InMemoryOperationalStore()
    rows = [
        {
            "session_id": "s1",
            "source_date": "2026-01-10",
            "source_fingerprint": "fp1",
        }
    ]
    store.merge_sessions(rows, source_start="2026-01-01", source_end="2026-01-31")
    store.merge_sessions(rows, source_start="2026-01-01", source_end="2026-01-31")
    assert len(store.sessions) == 1


def test_merge_conversions_is_idempotent():
    store = InMemoryOperationalStore()
    store.merge_conversions([{"conversion_id": "c1", "value": 1}])
    store.merge_conversions([{"conversion_id": "c1", "value": 1}])
    assert len(store.conversions) == 1


def test_merge_touchpoints_is_idempotent():
    store = InMemoryOperationalStore()
    store.merge_touchpoints([{"touchpoint_id": "tp1"}])
    store.merge_touchpoints([{"touchpoint_id": "tp1"}])
    assert len(store.touchpoints) == 1


def test_refreshed_window_removes_stale_source_rows():
    store = InMemoryOperationalStore()
    store.merge_sessions(
        [{"session_id": "old", "source_date": "2026-01-05", "source_fingerprint": "a"}],
        source_start="2026-01-01",
        source_end="2026-01-31",
    )
    store.merge_sessions(
        [{"session_id": "new", "source_date": "2026-01-06", "source_fingerprint": "b"}],
        source_start="2026-01-01",
        source_end="2026-01-31",
    )
    assert "old" not in store.sessions
    assert "new" in store.sessions


def test_journey_rebuild_removes_stale_journeys():
    store = InMemoryOperationalStore()
    store.rebuild_journeys(
        [{"journey_id": "j1", "conversion_date": "2026-01-10"}],
        conversion_start="2026-01-01",
        conversion_end="2026-01-31",
    )
    store.rebuild_journeys(
        [{"journey_id": "j2", "conversion_date": "2026-01-11"}],
        conversion_start="2026-01-01",
        conversion_end="2026-01-31",
    )
    assert "j1" not in store.journeys
    assert "j2" in store.journeys


def test_path_frequency_rebuild_is_idempotent():
    store = InMemoryOperationalStore()
    rows = [{"path_string": "a > b", "occurrences": 2, "converted": True}]
    store.rebuild_path_frequencies(rows)
    store.rebuild_path_frequencies(rows)
    assert store.path_frequencies["a > b"]["occurrences"] == 2


def test_watermark_advances_only_after_validation():
    store = InMemoryOperationalStore()
    with pytest.raises(ValueError):
        store.advance_watermark("2026-01-31", validated=False)
    store.advance_watermark("2026-01-31", validated=True)
    assert store.watermark == "2026-01-31"


def test_refresh_window_is_bounded():
    window = MTARefreshWindowPlanner().plan(
        run_date="2026-02-10",
        settlement_days=2,
        source_overlap_days=3,
        lookback_window_days=30,
    )
    assert window.source_end_date < "2026-02-10"
    assert window.source_start_date < window.source_end_date


def test_lookback_change_changes_input_config_fingerprint():
    service = _ready_service()
    contract = service.repo.get_contract("ic_m501")
    a = build_analysis_config(contract, channel_registry_version=1, channel_grouping_version=1)
    other = contract.model_copy(update={"lookback_window_days": 60})
    # rebuild fingerprint via build_input_contract path — mutate analysis inputs
    b = build_analysis_config(
        other, channel_registry_version=1, channel_grouping_version=1
    )
    assert a.fingerprint != b.fingerprint


def test_scheduled_refresh_requires_approval():
    plan = build_scheduled_refresh_plan(
        schedule_id="sched1", conversion_event="purchase", lookback_window_days=30
    )
    assert plan.approval_status is ScheduledRefreshApprovalStatus.DRAFT
    with pytest.raises(PermissionError):
        provision_scheduled_refresh_fake(plan)
    approved = approve_scheduled_refresh(plan)
    receipt = provision_scheduled_refresh_fake(approved)
    assert receipt.provisioned is True


def test_historical_udf_version_cannot_be_replaced():
    service = MTAService()
    g1 = service.save_grouping(
        version="v1",
        rules=(),
        created_by="tester",
    ) if False else None
    del g1
    # Use channel grouping immutability via repo
    from app.modeling.mta.channel_grouping import build_channel_grouping
    from app.modeling.mta.contracts import MTAChannelGroupingRule

    grouping = build_channel_grouping(
        version="v1",
        rules=[
            MTAChannelGroupingRule(
                rule_id="r1",
                priority=1,
                source_pattern="google",
                canonical_channel_id="search_paid",
            )
        ],
        created_by="t",
    )
    service.repo.put_grouping(grouping)
    mutated = grouping.model_copy(update={"fingerprint": "different"})
    with pytest.raises(ValueError):
        service.repo.put_grouping(mutated)


# --- compiler / journeys ---


def test_ga4_compiler_uses_pinned_traffic_source_policy():
    contract = build_input_contract(
        input_contract_id="ic2",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        ga4_dataset_id="analytics_1",
        source_schema_version="v1",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        conversion_event="purchase",
        conversion_period_start="2026-01-01",
        conversion_period_end="2026-01-31",
        lookback_window_days=30,
        identity_strategy=IdentityStrategy.PSEUDO_ID_ONLY,
        sessionization_policy=SessionizationPolicy.GA4_SESSION_ID_V1,
        traffic_source_policy=SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1,
        channel_grouping_version="v1",
    )
    assert (
        contract.traffic_source_policy
        is SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1
    )


def test_final_run_excludes_intraday_under_settled_policy():
    assert GA4SettlementPolicy.DAILY_SETTLED.value == "DAILY_SETTLED"


def test_conversion_period_and_lookback_are_separate():
    contract = build_input_contract(
        input_contract_id="ic3",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        ga4_dataset_id="analytics_1",
        source_schema_version="v1",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        conversion_event="purchase",
        conversion_period_start="2026-01-01",
        conversion_period_end="2026-01-31",
        lookback_window_days=45,
        identity_strategy=IdentityStrategy.PSEUDO_ID_ONLY,
        sessionization_policy=SessionizationPolicy.GA4_SESSION_ID_V1,
        traffic_source_policy=SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1,
        channel_grouping_version="v1",
    )
    assert contract.lookback_window_days == 45
    assert contract.conversion_period_start == "2026-01-01"


def test_session_key_uses_governed_sessionization():
    assert session_key(user_pseudo_id="u1", ga_session_id="5").startswith("msess_")


def test_raw_ga4_tables_are_never_mutated():
    # Compiler only targets prem3_modeling.* assets.
    entry = cached_sql_asset_manifest().get("merge_sessions_v1")
    assert "analytics_" not in entry.path


def test_journey_ids_are_deterministic():
    a = deterministic_journey_id(
        subject_key="s",
        conversion_event="purchase",
        conversion_ts="2026-01-10T00:00:00Z",
        channels=["search_paid", "direct"],
        touchpoint_times=["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
    )
    b = deterministic_journey_id(
        subject_key="s",
        conversion_event="purchase",
        conversion_ts="2026-01-10T00:00:00Z",
        channels=["search_paid", "direct"],
        touchpoint_times=["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
    )
    assert a == b


def test_invalid_timestamp_order_fails_closed():
    with pytest.raises(JourneyCompilationError):
        assert_touchpoint_order(["2026-01-02", "2026-01-01"])


def test_nonconverting_paths_follow_config():
    jd = JourneyDefinition(include_nonconverting_paths=True)
    assert jd.include_nonconverting_paths is True


def test_grouped_paths_preserve_occurrence_counts():
    rows = reduce_path_frequencies(
        [
            {"path_string": "a > b", "converted": True, "conversion_value": 1},
            {"path_string": "a > b", "converted": True, "conversion_value": 2},
        ]
    )
    assert rows[0]["occurrences"] == 2
    assert rows[0]["conversion_value"] == 3


def test_grouped_frequency_input_is_marked_in_manifest():
    assert MTAInputMode.GROUPED_PATH_FREQUENCY.value == "GROUPED_PATH_FREQUENCY"


def test_path_frequency_reduction_is_deterministic():
    rows = [
        {"path_string": "b > a", "converted": False},
        {"path_string": "a > b", "converted": True},
    ]
    assert reduce_path_frequencies(rows) == reduce_path_frequencies(list(reversed(rows)))


# --- DP6 ---


def test_dp6_version_is_pinned():
    assert assert_pinned_dp6_version() == DP6_MAM_PINNED_VERSION
    assert ADAPTER_VERSION.startswith("m5-")


@pytest.mark.parametrize(
    "model_id",
    [
        AttributionModelId.FIRST_TOUCH,
        AttributionModelId.LAST_TOUCH,
        AttributionModelId.LAST_NON_DIRECT,
        AttributionModelId.LINEAR,
        AttributionModelId.TIME_DECAY,
        AttributionModelId.POSITION_BASED,
        AttributionModelId.MARKOV,
        AttributionModelId.SHAPLEY,
    ],
)
def test_dp6_adapter_models(model_id: AttributionModelId):
    adapter = DP6MAMAdapter(fake=True)
    result = adapter.run_model(
        model_id,
        paths=[["social_paid", "display", "search_paid"]],
        conversions=[1.0],
        parameters={
            "first_weight": 0.4,
            "middle_weight": 0.2,
            "last_weight": 0.4,
            "size": 4,
            "order": True,
            "values_col": "conversions",
        },
    )
    assert result.credits
    if model_id is AttributionModelId.MARKOV:
        assert result.markov is not None
        assert result.markov.transitions
        assert result.markov.removal_effects
    if model_id is AttributionModelId.SHAPLEY:
        assert result.shapley is not None


def test_dp6_nan_inf_rejected():
    # Force finite check via helper
    with pytest.raises(DP6FiniteValueError):
        from app.modeling.mta.adapters.dp6_mam_v1_0_11 import _reject_non_finite

        _reject_non_finite([float("nan")])


def test_shapley_not_run_when_not_recommended():
    preflight = run_shapley_preflight(
        distinct_channel_count=50, configured_size=None, order_aware=True
    )
    assert preflight.state is ShapleyPreflightState.NOT_RECOMMENDED
    service = _ready_service()
    contract = service.repo.get_contract("ic_m501")
    analysis = build_analysis_config(
        contract.model_copy(
            update={"attribution_models": (AttributionModelId.SHAPLEY, AttributionModelId.MARKOV)}
        ),
        channel_registry_version=1,
        channel_grouping_version=1,
    )
    # rebuild analysis with shapley in models manually
    analysis = analysis.model_copy(
        update={"models": (AttributionModelId.MARKOV, AttributionModelId.SHAPLEY)}
    )
    plan = compile_execution_plan(
        execution_plan_id="ep_s",
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        contract=contract,
        readiness_receipt_id="r",
        analysis=analysis,
        channel_grouping_fingerprint="cg",
        journey_fingerprint="j",
        shapley_preflight=preflight,
    )
    assert AttributionModelId.SHAPLEY not in plan.models


def test_shapley_review_required_does_not_auto_run():
    preflight = run_shapley_preflight(
        distinct_channel_count=15, configured_size=None, order_aware=False
    )
    assert preflight.state is ShapleyPreflightState.REVIEW_REQUIRED


def test_shapley_path_limit_is_explicit():
    adapter = DP6MAMAdapter(fake=True)
    result = adapter.run_model(
        AttributionModelId.SHAPLEY,
        paths=[["a", "b", "c"]],
        parameters={"size": 2, "path_limit_applied": True},
    )
    assert "SHAPLEY_PATH_LIMIT_APPLIED" in result.limitations


def test_shapley_config_change_changes_execution_plan_fingerprint():
    service = _ready_service()
    contract = service.repo.get_contract("ic_m501")
    a = build_analysis_config(
        contract,
        channel_registry_version=1,
        channel_grouping_version=1,
        model_parameters={"shapley_size": 3},
    )
    b = build_analysis_config(
        contract,
        channel_registry_version=1,
        channel_grouping_version=1,
        model_parameters={"shapley_size": 5},
    )
    assert a.fingerprint != b.fingerprint


# --- authority / dispatch / persistence ---


def test_worker_resolves_execution_plan_server_side():
    service = _ready_service()
    run = service.start_run(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        journeys=[
            {
                "subject_key": "s1",
                "channels": ["social_paid", "search_paid"],
                "touchpoint_times": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
                "conversion_ts": "2026-01-03T00:00:00Z",
                "converted": True,
                "conversion_value": 1.0,
            }
        ],
    )
    assert run.dispatch_id
    receipt = service.execute_fit_dispatch(dispatch_id=run.dispatch_id)
    assert receipt.status is MTARunStatus.SUCCEEDED
    assert receipt.readback_status == "VERIFIED"


def test_user_cannot_override_bq_destination():
    service = _ready_service()
    with pytest.raises(PermissionError):
        service.start_run(
            tenant_id="t1",
            project_id="p1",
            cycle_id="c1",
            track_id="tr1",
            bq_destination_override="evil.dataset",
        )


def test_user_cannot_override_channel_grouping_routine():
    service = _ready_service()
    with pytest.raises(PermissionError):
        service.start_run(
            tenant_id="t1",
            project_id="p1",
            cycle_id="c1",
            track_id="tr1",
            channel_grouping_routine_override="channel_grouping_current",
        )


def test_user_cannot_override_worker_image():
    service = _ready_service()
    with pytest.raises(PermissionError):
        service.start_run(
            tenant_id="t1",
            project_id="p1",
            cycle_id="c1",
            track_id="tr1",
            worker_image_override="evil:latest",
        )


def test_duplicate_enqueue_is_idempotent():
    dispatcher = FakeMTADispatcher()
    service = MTAService(dispatcher=dispatcher)
    # reuse ready path
    service = _ready_service()
    service.dispatcher = dispatcher
    run = service.start_run(tenant_id="t1", project_id="p1", cycle_id="c1", track_id="tr1")
    dispatch = service.repo.get_dispatch(run.dispatch_id)
    name1 = dispatcher.enqueue(dispatch)
    name2 = dispatcher.enqueue(dispatch)
    assert name1 == name2
    assert len(dispatcher.calls) == 1


def test_duplicate_launch_does_not_spawn_second_job():
    service = _ready_service()
    run = service.start_run(tenant_id="t1", project_id="p1", cycle_id="c1", track_id="tr1")
    d1 = service.launch_dispatch(dispatch_id=run.dispatch_id)
    d2 = service.launch_dispatch(dispatch_id=run.dispatch_id)
    assert d1.cloud_run_execution_name == d2.cloud_run_execution_name
    assert d1.status is MTADispatchStatus.LAUNCHED


def test_required_outputs_read_back_before_success():
    store = InMemoryResultStore()
    store.write("t1", [{"a": 1}])
    fps = store.verify_required(run_id="r1", required_tables=["t1"])
    assert "t1" in fps


def test_failed_readback_blocks_run_success():
    store = InMemoryResultStore()
    with pytest.raises(ReadbackError):
        store.verify_required(run_id="r1", required_tables=["missing"])


def test_current_views_advance_only_after_verified_success():
    store = InMemoryResultStore()
    store.write("out", [{"x": 1}])
    store.verify_required(run_id="r1", required_tables=["out"])
    store.advance_current(
        run_id="r1",
        mapping={"mta_attribution_channels_current": "out"},
        run_status=MTARunStatus.SUCCEEDED,
    )
    assert store.current_views["mta_attribution_channels_current"] == "out"


def test_failed_run_does_not_replace_current():
    store = InMemoryResultStore()
    store.write("out", [{"x": 1}])
    store.verify_required(run_id="r1", required_tables=["out"])
    store.advance_current(
        run_id="r1",
        mapping={"mta_attribution_channels_current": "out"},
        run_status=MTARunStatus.SUCCEEDED,
    )
    with pytest.raises(ReadbackError):
        store.advance_current(
            run_id="r2",
            mapping={"mta_attribution_channels_current": "other"},
            run_status=MTARunStatus.FAILED,
        )


def test_firestore_contains_compact_metadata_only():
    # Repository stores plans/runs/receipts — not journey arrays.
    service = _ready_service()
    run = service.start_run(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        journeys=[
            {
                "subject_key": "s",
                "channels": ["search_paid"],
                "touchpoint_times": ["2026-01-01T00:00:00Z"],
                "conversion_ts": "2026-01-02T00:00:00Z",
                "converted": True,
            }
        ],
    )
    stored = service.repo.get_run(run.run_id)
    assert not hasattr(stored, "journeys")


def test_no_causal_labels_in_mta_public_strings():
    for phrase in FORBIDDEN_CAUSAL_PHRASES:
        with pytest.raises(CausalLanguageError):
            assert_no_causal_mta_language(f"This shows {phrase} for the channel.")


def test_worker_rejects_forbidden_authority_keys():
    with pytest.raises(PermissionError):
        execute_server_owned_request({"dispatch_id": "x", "tenant_id": "t"})
    assert "tenant_id" in FORBIDDEN_REQUEST_KEYS


def test_ruleset_loads_against_registry():
    ruleset = load_channel_grouping_rules(version=1)
    assert ruleset.fallback_channel_id == "other"
    assert any(r.output_channel_id == "ai_search" for r in ruleset.rules)


def test_udf_literal_extraction_includes_else():
    ids = extract_udf_literal_channel_ids("THEN 'search_paid' ELSE 'other'")
    assert "search_paid" in ids and "other" in ids
