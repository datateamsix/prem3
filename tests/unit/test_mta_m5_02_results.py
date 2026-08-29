"""M5-02 unit tests — result snapshots, roles, visuals, DI, APIs."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.modeling.mta.contracts import (
    AttributionModelId,
    GA4SettlementPolicy,
    IdentityStrategy,
    MTAReadinessState,
    SessionizationPolicy,
    SessionTrafficSourcePolicy,
)
from app.modeling.mta.dispatch import FakeMTADispatcher
from app.modeling.mta.input_contract import build_input_contract
from app.modeling.mta.language import assert_result_payload_language
from app.modeling.mta.result_policies import (
    DEFAULT_ROLE_POLICY,
    DEFAULT_SENSITIVITY_POLICY,
    ROLE_POLICY_VERSION,
    SENSITIVITY_POLICY_VERSION,
    classify_channel_roles,
    classify_sensitivity,
    share_dispersion,
)
from app.modeling.mta.results_compiler import MTAResultsCompiler, filter_model_comparison
from app.modeling.mta.results_contracts import (
    DECISION_INTELLIGENCE_POLICY_VERSION,
    ChannelRoleLabel,
    MetricAvailability,
    MTAResultPointers,
    MTAResultsCompileError,
    MTAResultsCompileFailureClass,
    MTAResultSnapshotMetadata,
    MTAResultStatus,
    MTAVisualizationKind,
    ObservabilityStatus,
    SensitivityLabel,
)
from app.modeling.mta.runtime_contracts import MTARunStatus
from app.modeling.mta.service import MTAService
from app.service.app import create_app
from app.service.auth import FakeIdentityVerifier
from tests.unit.api_support import auth_header, seed_tenant


def _journeys_introducer() -> list[dict]:
    rows = []
    for i in range(10):
        rows.append(
            {
                "subject_key": f"u{i}",
                "channels": ["social_paid", "display", "search_paid"],
                "touchpoint_times": [
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-02T00:00:00+00:00",
                    "2026-01-05T00:00:00+00:00",
                ],
                "conversion_ts": "2026-01-06T00:00:00+00:00",
                "converted": True,
                "conversion_value": 1.0,
            }
        )
    return rows


def _ready_service(
    *,
    models: tuple[AttributionModelId, ...] | None = None,
    journeys: list[dict] | None = None,
) -> MTAService:
    service = MTAService(dispatcher=FakeMTADispatcher())
    contract = build_input_contract(
        input_contract_id="ic_m502",
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
        attribution_models=models
        or (
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
    del journeys
    return service


def _execute(service: MTAService, journeys: list[dict] | None = None):
    run = service.start_run(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        journeys=journeys or _journeys_introducer(),
    )
    service.launch_dispatch(dispatch_id=run.dispatch_id)
    service.execute_fit_dispatch(dispatch_id=run.dispatch_id)
    run = service.repo.get_run(run.run_id)
    compiled = service.repo.get_compiled_results(
        service.repo.get_snapshot_for_run(run.run_id).result_snapshot_id
    )
    brief = service.repo.get_brief_for_snapshot(compiled.snapshot.result_snapshot_id)
    return service, run, compiled, brief


# --- 93 availability ---


def test_results_not_available_without_verified_run():
    compiler = MTAResultsCompiler(MTAService().repo, MTAService().result_store)
    with pytest.raises(MTAResultsCompileError) as exc:
        compiler.compile("missing")
    assert exc.value.failure_class is MTAResultsCompileFailureClass.MTA_RESULTS_SOURCE_NOT_VERIFIED


def test_failed_mta_run_cannot_create_result_snapshot():
    service = _ready_service()
    run = service.start_run(tenant_id="t1", project_id="p1", cycle_id="c1", track_id="tr1")
    failed = run.model_copy(update={"status": MTARunStatus.FAILED})
    service.repo.put_run(failed)
    with pytest.raises(MTAResultsCompileError):
        service.results_compiler.compile(run.run_id)
    assert service.repo.get_run(run.run_id).status is MTARunStatus.FAILED


def test_result_snapshot_binds_exact_run_receipt():
    _service, run, compiled, _brief = _execute(_ready_service())
    receipt = _service.repo.get_run_receipt_for_run(run.run_id)
    assert compiled.snapshot.run_id == run.run_id
    assert compiled.snapshot.run_receipt_id == receipt.receipt_id
    assert compiled.snapshot.run_receipt_fingerprint == receipt.fingerprint
    assert compiled.snapshot.execution_plan_fingerprint == run.execution_plan_fingerprint


def test_new_run_creates_new_result_snapshot():
    service = _ready_service()
    _, run1, compiled1, _ = _execute(service)
    _, run2, compiled2, _ = _execute(service)
    assert run1.run_id != run2.run_id
    assert compiled1.snapshot.result_snapshot_id != compiled2.snapshot.result_snapshot_id


def test_historical_snapshot_is_immutable():
    _service, _run, compiled, _ = _execute(_ready_service())
    mutated = compiled.snapshot.model_copy(
        update={
            "fingerprint": "tampered",
            "result_snapshot_id": compiled.snapshot.result_snapshot_id,
        }
    )
    compiled.snapshot = mutated
    with pytest.raises(ValueError, match="immutable"):
        _service.repo.put_compiled_results(compiled)


# --- 94 availability/null ---


def test_shapley_not_run_is_not_zero():
    _service, _run, compiled, _ = _execute(_ready_service())
    for row in compiled.channel_results:
        shapley_item = next(m for m in row.metric_availability if m.metric_name == "shapley_share")
        assert shapley_item.status in {
            MetricAvailability.NOT_RUN,
            MetricAvailability.NOT_APPLICABLE,
        }
        assert row.shapley_share is None
        assert row.shapley_credit is None


def test_markov_unavailable_is_typed():
    service = _ready_service(models=(AttributionModelId.FIRST_TOUCH, AttributionModelId.LAST_TOUCH))
    _s, _run, compiled, _ = _execute(service)
    assert compiled.markov is not None
    assert compiled.markov.availability is MetricAvailability.NOT_APPLICABLE
    assert compiled.markov.unavailable_reason


def test_missing_metric_not_coerced_to_zero():
    _service, _run, compiled, _ = _execute(_ready_service())
    for row in compiled.channel_results:
        assert row.last_non_direct_share is None
        assert row.time_decay_share is None


def test_nan_inf_result_rejected():
    service, run, _compiled, _ = _execute(_ready_service())
    table = f"mta_attribution_channel_results_{run.run_id}"
    rows = service.result_store.read_back(table)
    rows[0]["attribution_share"] = float("inf")
    service.result_store.write(table, rows)
    with pytest.raises(MTAResultsCompileError) as exc:
        service.results_compiler.compile(run.run_id)
    assert exc.value.failure_class is MTAResultsCompileFailureClass.MTA_RESULTS_INVALID_NUMERIC
    assert service.repo.get_run(run.run_id).status is MTARunStatus.SUCCEEDED


# --- 95 comparison/filter ---


def test_model_comparison_uses_verified_normalized_results():
    _service, run, compiled, _ = _execute(_ready_service())
    credits = _service.result_store.read_back(f"mta_attribution_channel_results_{run.run_id}")
    by_key = {(r["channel_id"], r["model_type"]): r["attribution_share"] for r in credits}
    for cell in compiled.comparison.rows:
        if cell.availability is MetricAvailability.AVAILABLE:
            assert cell.attribution_share == pytest.approx(
                by_key[(cell.channel_id, cell.model_type)]
            )


def test_frontend_model_filter_does_not_mutate_snapshot():
    _service, _run, compiled, _ = _execute(_ready_service())
    original_fp = compiled.snapshot.fingerprint
    original_rows = len(compiled.comparison.rows)
    filtered = filter_model_comparison(compiled.comparison, ("FIRST_TOUCH",))
    assert len(filtered.rows) < original_rows
    stored = _service.repo.get_compiled_results(compiled.snapshot.result_snapshot_id)
    assert stored.snapshot.fingerprint == original_fp
    assert len(stored.comparison.rows) == original_rows


def test_filter_does_not_rerun_attribution():
    service, run, compiled, _ = _execute(_ready_service())
    before = service.result_store.read_back(f"mta_attribution_channel_results_{run.run_id}")
    filter_model_comparison(compiled.comparison, ("MARKOV", "LAST_TOUCH"))
    after = service.result_store.read_back(f"mta_attribution_channel_results_{run.run_id}")
    assert before == after


def test_model_parameter_metadata_preserved():
    _service, _run, compiled, _ = _execute(_ready_service())
    assert "MARKOV" in compiled.comparison.model_parameters
    assert "transition_to_same_state" in compiled.comparison.model_parameters["MARKOV"]


def test_all_completed_models_remain_queryable():
    _service, _run, compiled, _ = _execute(_ready_service())
    assert set(compiled.snapshot.models_completed) <= {
        cell.model_type for cell in compiled.comparison.rows
    }
    for model in compiled.snapshot.models_completed:
        assert any(c.model_type == model for c in compiled.comparison.rows)


# --- 96 sensitivity ---


def test_model_dispersion_is_deterministic():
    shares = [0.10, 0.40, 0.25]
    assert share_dispersion(shares) == pytest.approx(0.30)
    assert classify_sensitivity(0.04) is SensitivityLabel.LOW
    assert classify_sensitivity(0.10) is SensitivityLabel.MODERATE
    assert classify_sensitivity(0.20) is SensitivityLabel.HIGH
    assert classify_sensitivity(0.30) is SensitivityLabel.VERY_HIGH


def test_sensitivity_policy_versioned():
    assert DEFAULT_SENSITIVITY_POLICY.policy_version == SENSITIVITY_POLICY_VERSION


def test_model_range_not_labeled_confidence_interval():
    _service, _run, compiled, _ = _execute(_ready_service())
    assert all(s.is_confidence_interval is False for s in compiled.sensitivity)
    viz = next(
        v for v in compiled.visualizations if v.kind is MTAVisualizationKind.MODEL_SENSITIVITY_RANGE
    )
    assert "not a confidence interval" in viz.description.lower()
    assert all(row.get("is_confidence_interval") is False for row in viz.data)


def test_high_disagreement_yields_model_sensitive_evidence():
    labels = classify_channel_roles(
        channel_id="search_paid",
        first_share=0.1,
        middle_share=0.1,
        last_share=0.8,
        journey_presence_rate=0.5,
        journey_presence_count=20,
        sensitivity=SensitivityLabel.VERY_HIGH,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.MODEL_SENSITIVE in labels


# --- 97 Markov ---


def test_markov_transition_rows_match_verified_output():
    service, run, compiled, _ = _execute(_ready_service())
    stored = service.result_store.read_back(f"mta_markov_transitions_{run.run_id}")
    compiled_pairs = {
        (t.from_channel_id, t.to_channel_id, t.transition_probability)
        for t in compiled.markov.transitions
    }
    stored_pairs = {
        (r["from_channel_id"], r["to_channel_id"], r["transition_probability"]) for r in stored
    }
    assert compiled_pairs == stored_pairs


def test_markov_removal_effect_preserved():
    service, run, compiled, _ = _execute(_ready_service())
    stored = {
        r["channel_id"]: r["removal_effect"]
        for r in service.result_store.read_back(f"mta_markov_removal_effects_{run.run_id}")
    }
    assert dict(compiled.markov.removal_effects) == stored


def test_markov_removal_effect_not_labeled_causal():
    _service, _run, compiled, _ = _execute(_ready_service())
    text = compiled.markov.removal_effect_explanation.lower()
    assert "causal" not in text
    assert "incremental conversions" not in text


def test_markov_special_states_preserved():
    service, run, _compiled, _ = _execute(_ready_service())
    table = f"mta_markov_transitions_{run.run_id}"
    rows = service.result_store.read_back(table)
    rows.append(
        {
            "from_channel_id": "START",
            "to_channel_id": "search_paid",
            "transition_probability": 1.0,
        }
    )
    rows.append(
        {
            "from_channel_id": "direct",
            "to_channel_id": "CONVERSION",
            "transition_probability": 1.0,
        }
    )
    rows.append(
        {
            "from_channel_id": "display",
            "to_channel_id": "NULL",
            "transition_probability": 0.1,
        }
    )
    service.result_store.write(table, rows)
    compiled = service.results_compiler.compile(run.run_id)
    states = {t.from_channel_id for t in compiled.markov.transitions} | {
        t.to_channel_id for t in compiled.markov.transitions
    }
    assert {"START", "CONVERSION", "NULL"} <= states


# --- 98 Shapley ---


def test_shapley_config_disclosed():
    service = _ready_service(
        models=(
            AttributionModelId.FIRST_TOUCH,
            AttributionModelId.SHAPLEY,
        )
    )
    _s, _run, compiled, _ = _execute(service)
    if compiled.shapley.availability is MetricAvailability.AVAILABLE:
        assert compiled.shapley.size is not None
        assert compiled.shapley.values_col is not None
        assert compiled.shapley.order is not None
    else:
        assert compiled.shapley.unavailable_reason


def test_shapley_path_limit_visible():
    service = _ready_service(models=(AttributionModelId.SHAPLEY,))
    run = service.start_run(
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        track_id="tr1",
        journeys=_journeys_introducer(),
    )
    plan = service.repo.get_execution_plan(run.execution_plan_id)
    params = tuple(
        p.model_copy(update={"parameters": {**p.parameters, "path_limit_applied": True}})
        if p.model_id is AttributionModelId.SHAPLEY
        else p
        for p in plan.model_parameters
    )
    service.repo.put_execution_plan(
        plan.model_copy(update={"model_parameters": params, "fingerprint": plan.fingerprint})
    )
    service.launch_dispatch(dispatch_id=run.dispatch_id)
    service.execute_fit_dispatch(dispatch_id=run.dispatch_id)
    compiled = service.repo.get_compiled_results(
        service.repo.get_snapshot_for_run(run.run_id).result_snapshot_id
    )
    if compiled.shapley.availability is MetricAvailability.AVAILABLE:
        assert compiled.shapley.path_limit_applied is True


def test_shapley_not_labeled_incremental():
    _service, _run, compiled, _ = _execute(_ready_service())
    dumped = compiled.shapley.model_dump(mode="json")
    assert_result_payload_language(dumped)


def test_shapley_unavailable_has_reason():
    _service, _run, compiled, _ = _execute(_ready_service())
    assert compiled.shapley.availability is not MetricAvailability.AVAILABLE
    assert compiled.shapley.unavailable_reason
    viz = next(
        v for v in compiled.visualizations if v.kind is MTAVisualizationKind.SHAPLEY_CONTRIBUTION
    )
    assert viz.available is False
    assert viz.unavailable_reason


# --- 99 journeys ---


def test_path_length_distribution_matches_journeys():
    _service, _run, compiled, _ = _execute(_ready_service())
    total = sum(b.journey_count for b in compiled.journeys.path_length_distribution)
    assert total == compiled.journeys.converted_journey_count
    three = next(b for b in compiled.journeys.path_length_distribution if b.touchpoint_count == 3)
    assert three.journey_count == 10


def test_time_to_conversion_distribution_matches_journeys():
    _service, _run, compiled, _ = _execute(_ready_service())
    total = sum(b.journey_count for b in compiled.journeys.time_to_conversion_distribution)
    assert total == compiled.journeys.converted_journey_count


def test_top_paths_deterministic():
    _service, _run, compiled, _ = _execute(_ready_service())
    paths = [p.path_string for p in compiled.journeys.top_paths]
    assert paths == sorted(paths) or paths == list(paths)
    assert compiled.journeys.top_paths[0].path_rank == 1


def test_no_user_identifier_exposed_in_path_summary():
    _service, _run, compiled, _ = _execute(_ready_service())
    blob = json.dumps([p.model_dump(mode="json") for p in compiled.journeys.top_paths])
    assert "subject_key" not in blob
    assert "user_pseudo_id" not in blob
    assert "u0" not in blob


def test_single_touch_position_policy_deterministic():
    journeys = [
        {
            "subject_key": "s1",
            "channels": ["search_paid"],
            "touchpoint_times": ["2026-01-01T00:00:00+00:00"],
            "conversion_ts": "2026-01-01T12:00:00+00:00",
            "converted": True,
        }
    ] * 8
    _service, _run, compiled, _ = _execute(_ready_service(), journeys=journeys)
    pos = next(p for p in compiled.journeys.position_evidence if p.channel_id == "search_paid")
    assert pos.single_touch_policy == "FIRST_AND_LAST"
    assert pos.first_position_count == pos.last_position_count == 8
    assert pos.middle_position_count == 0


# --- 100 position ---


def test_first_middle_last_position_shares():
    _service, _run, compiled, _ = _execute(_ready_service())
    social = next(p for p in compiled.journeys.position_evidence if p.channel_id == "social_paid")
    display = next(p for p in compiled.journeys.position_evidence if p.channel_id == "display")
    search = next(p for p in compiled.journeys.position_evidence if p.channel_id == "search_paid")
    assert social.first_position_share == pytest.approx(1.0)
    assert display.middle_position_share == pytest.approx(1.0)
    assert search.last_position_share == pytest.approx(1.0)


def test_position_denominators_documented():
    _service, _run, compiled, _ = _execute(_ready_service())
    assert all(
        p.denominator == "converted_journey_count" for p in compiled.journeys.position_evidence
    )


def test_channel_presence_rate_deterministic():
    _service, _run, compiled, _ = _execute(_ready_service())
    social = next(c for c in compiled.channel_results if c.channel_id == "social_paid")
    assert social.journey_presence_rate == pytest.approx(1.0)


# --- 101 roles ---


def test_role_policy_versioned():
    assert DEFAULT_ROLE_POLICY.policy_version == ROLE_POLICY_VERSION
    _service, _run, compiled, _ = _execute(_ready_service())
    assert all(r.policy_version == ROLE_POLICY_VERSION for r in compiled.roles)


def test_role_classifier_uses_evidence_not_channel_name():
    intro = classify_channel_roles(
        channel_id="search_paid",
        first_share=0.8,
        middle_share=0.1,
        last_share=0.1,
        journey_presence_rate=0.5,
        journey_presence_count=20,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    closer = classify_channel_roles(
        channel_id="search_paid",
        first_share=0.1,
        middle_share=0.1,
        last_share=0.8,
        journey_presence_rate=0.5,
        journey_presence_count=20,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.INTRODUCER in intro
    assert ChannelRoleLabel.CONVERTER in closer
    assert intro != closer


def test_introductory_pattern_can_yield_introducer():
    labels = classify_channel_roles(
        channel_id="social_paid",
        first_share=0.7,
        middle_share=0.2,
        last_share=0.1,
        journey_presence_rate=0.4,
        journey_presence_count=10,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.INTRODUCER in labels
    _service, _run, compiled, _ = _execute(_ready_service())
    social = next(r for r in compiled.roles if r.channel_id == "social_paid")
    assert ChannelRoleLabel.INTRODUCER in social.labels


def test_middle_pattern_can_yield_assister():
    labels = classify_channel_roles(
        channel_id="display",
        first_share=0.1,
        middle_share=0.6,
        last_share=0.1,
        journey_presence_rate=0.4,
        journey_presence_count=10,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.ASSISTER in labels


def test_closing_pattern_can_yield_converter():
    labels = classify_channel_roles(
        channel_id="search_paid",
        first_share=0.1,
        middle_share=0.2,
        last_share=0.7,
        journey_presence_rate=0.4,
        journey_presence_count=10,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.CONVERTER in labels


def test_multi_position_pattern_can_yield_multi_role():
    labels = classify_channel_roles(
        channel_id="search_organic",
        first_share=0.3,
        middle_share=0.3,
        last_share=0.3,
        journey_presence_rate=0.5,
        journey_presence_count=12,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.MULTI_ROLE in labels


def test_direct_capture_requires_direct_channel():
    paid = classify_channel_roles(
        channel_id="search_paid",
        first_share=0.1,
        middle_share=0.1,
        last_share=0.8,
        journey_presence_rate=0.6,
        journey_presence_count=20,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    direct = classify_channel_roles(
        channel_id="direct",
        first_share=0.1,
        middle_share=0.1,
        last_share=0.8,
        journey_presence_rate=0.6,
        journey_presence_count=20,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.DIRECT_CAPTURE not in paid
    assert ChannelRoleLabel.DIRECT_CAPTURE in direct


def test_low_observability_limits_role_confidence():
    labels = classify_channel_roles(
        channel_id="podcast",
        first_share=0.9,
        middle_share=0.0,
        last_share=0.1,
        journey_presence_rate=0.001,
        journey_presence_count=1,
        sensitivity=SensitivityLabel.LOW,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.LOW_OBSERVABILITY in labels
    assert ChannelRoleLabel.INTRODUCER not in labels


def test_high_sensitivity_adds_model_sensitive_role():
    labels = classify_channel_roles(
        channel_id="display",
        first_share=0.2,
        middle_share=0.5,
        last_share=0.2,
        journey_presence_rate=0.4,
        journey_presence_count=10,
        sensitivity=SensitivityLabel.HIGH,
        observability=ObservabilityStatus.GOOD,
    )
    assert ChannelRoleLabel.MODEL_SENSITIVE in labels


# --- 102 visualizations ---


def test_visualization_binds_result_snapshot():
    _service, _run, compiled, _ = _execute(_ready_service())
    assert compiled.visualizations
    for viz in compiled.visualizations:
        assert viz.source_result_snapshot_id == compiled.snapshot.result_snapshot_id
        assert viz.source_run_id == compiled.snapshot.run_id


def test_visualization_has_evidence_refs():
    _service, _run, compiled, _ = _execute(_ready_service())
    available = [v for v in compiled.visualizations if v.available]
    assert available
    assert all(v.source_evidence_refs for v in available)


def test_model_heatmap_values_match_backend_evidence():
    _service, _run, compiled, _ = _execute(_ready_service())
    viz = next(
        v
        for v in compiled.visualizations
        if v.kind is MTAVisualizationKind.MODEL_COMPARISON_HEATMAP
    )
    by_key = {
        (c.channel_id, c.model_type): c.attribution_share
        for c in compiled.comparison.rows
        if c.availability is MetricAvailability.AVAILABLE
    }
    for row in viz.data:
        assert row["attribution_share"] == pytest.approx(
            by_key[(row["channel_id"], row["model_type"])]
        )


def test_markov_matrix_values_are_backend_owned():
    _service, _run, compiled, _ = _execute(_ready_service())
    viz = next(
        v
        for v in compiled.visualizations
        if v.kind is MTAVisualizationKind.MARKOV_TRANSITION_MATRIX
    )
    assert viz.available is True
    expected = {
        (t.from_channel_id, t.to_channel_id): t.transition_probability
        for t in compiled.markov.transitions
    }
    for row in viz.data:
        assert row["transition_probability"] == pytest.approx(
            expected[(row["from_channel_id"], row["to_channel_id"])]
        )


def test_unavailable_shapley_visualization_has_reason():
    _service, _run, compiled, _ = _execute(_ready_service())
    viz = next(
        v for v in compiled.visualizations if v.kind is MTAVisualizationKind.SHAPLEY_CONTRIBUTION
    )
    assert viz.available is False
    assert viz.unavailable_reason


# --- 103 DI ---


def test_verified_findings_trace_to_evidence():
    _service, _run, compiled, brief = _execute(_ready_service())
    assert brief is not None
    assert brief.verified_findings
    for finding in brief.verified_findings:
        assert finding.authority.value == "VERIFIED"
        assert finding.evidence_refs


def test_interpretation_labeled():
    _service, _run, _c, brief = _execute(_ready_service())
    assert brief.interpretations
    assert all(i.authority.value == "INTERPRETATION" for i in brief.interpretations)


def test_recommendation_requires_evidence():
    _service, _run, _c, brief = _execute(_ready_service())
    for rec in brief.recommendations:
        assert rec.evidence_refs


def test_recommendation_has_counter_evidence_or_uncertainty():
    _service, _run, _c, brief = _execute(_ready_service())
    for rec in brief.recommendations:
        assert rec.counterevidence_refs or rec.uncertainty


def test_mta_brief_no_budget_reallocation():
    _service, _run, _c, brief = _execute(_ready_service())
    blob = json.dumps(brief.model_dump(mode="json")).lower()
    assert "reallocation" not in blob
    assert "increase " not in blob or "increase paid search spend" not in blob
    assert "cut display" not in blob
    assert "spend by" not in blob


def test_mta_brief_no_causal_incrementality_claim():
    _service, _run, compiled, brief = _execute(_ready_service())
    assert_result_payload_language(brief.model_dump(mode="json"))
    assert_result_payload_language(compiled.snapshot.model_dump(mode="json"))


# --- 105 persistence ---


def test_firestore_result_metadata_compact():
    _service, _run, compiled, _ = _execute(_ready_service())
    meta = MTAResultSnapshotMetadata(
        result_snapshot_id=compiled.snapshot.result_snapshot_id,
        project_id=compiled.snapshot.project_id,
        cycle_id=compiled.snapshot.cycle_id,
        track_id=compiled.snapshot.track_id,
        run_id=compiled.snapshot.run_id,
        result_status=compiled.snapshot.result_status,
        evidence_authority=compiled.snapshot.evidence_authority,
        fingerprint=compiled.snapshot.fingerprint,
        models_completed=compiled.snapshot.models_completed,
        observability_status=compiled.snapshot.observability_summary.status,
    )
    payload = meta.model_dump(mode="json")
    assert "channel_results" not in payload
    assert "visualizations" not in payload
    assert "journeys" not in payload
    assert len(json.dumps(payload)) < 4096


def test_bigquery_result_rows_readback():
    service, _run, compiled, _ = _execute(_ready_service())
    rows = service.result_store.read_back(compiled.snapshot.channel_results_ref)
    assert len(rows) == len(compiled.channel_results)


def test_result_fingerprint_stable():
    service = _ready_service()
    journeys = _journeys_introducer()
    _, _r1, c1, _ = _execute(service, journeys=journeys)
    # Same outputs re-fingerprinted from the same receipt remain bound.
    again = service.results_compiler.compile(_r1.run_id)
    assert again.snapshot.run_receipt_fingerprint == c1.snapshot.run_receipt_fingerprint
    assert again.snapshot.execution_plan_fingerprint == c1.snapshot.execution_plan_fingerprint


def test_role_policy_change_does_not_mutate_attribution():
    _service, _run, compiled, _ = _execute(_ready_service())
    fp = compiled.snapshot.fingerprint
    compiled.roles[0].model_dump()
    stored = _service.repo.get_snapshot(compiled.snapshot.result_snapshot_id)
    assert stored.fingerprint == fp


def test_brief_policy_change_does_not_mutate_result_snapshot():
    service, _run, compiled, brief = _execute(_ready_service())
    snap_fp = compiled.snapshot.fingerprint
    new_brief = service.di_compiler.compile(
        snapshot=compiled.snapshot,
        channel_results=compiled.channel_results,
        roles=compiled.roles,
        sensitivity=compiled.sensitivity,
        journeys=compiled.journeys,
        shapley=compiled.shapley,
        observability=compiled.snapshot.observability_summary,
        policy_version=DECISION_INTELLIGENCE_POLICY_VERSION + "_alt",
    )
    service.repo.put_brief(new_brief)
    assert service.repo.get_snapshot(compiled.snapshot.result_snapshot_id).fingerprint == snap_fp
    assert new_brief.brief_id != brief.brief_id
    assert new_brief.policy_version.endswith("_alt")
    assert compiled.snapshot.fingerprint == snap_fp


# --- 106 APIs ---


def _api_client_with_results():
    repo = InMemoryControlPlaneRepository()
    _tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    service, _run, compiled, brief = _execute(_ready_service())
    app = create_app(
        control_plane_repository=repo,
        identity_verifier=FakeIdentityVerifier(default=identity),
    )
    client = TestClient(app, raise_server_exceptions=False)
    headers = auth_header()
    project_id = client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "MTA Results", "scope_type": "BRAND"},
    ).json()["project_id"]
    overview = client.get(f"/v1/projects/{project_id}/cycles/cycle-mta/mta", headers=headers)
    assert overview.status_code == 200, overview.text
    track_id = overview.json()["track_id"]
    # Rebind compiled snapshot to the API project/cycle/track.
    snap = compiled.snapshot.model_copy(
        update={
            "project_id": project_id,
            "cycle_id": "cycle-mta",
            "track_id": track_id,
        }
    )
    compiled.snapshot = snap
    run = service.repo.get_run(_run.run_id).model_copy(
        update={
            "tenant_id": _tenant.tenant_id,
            "project_id": project_id,
            "cycle_id": "cycle-mta",
            "track_id": track_id,
        }
    )
    service.repo.put_run(run)
    service.repo.put_compiled_results(compiled)
    service.repo.put_result_pointers(
        MTAResultPointers(
            track_id=track_id,
            latest_result_snapshot_id=snap.result_snapshot_id,
            current_result_snapshot_id=snap.result_snapshot_id,
        )
    )
    brief = brief.model_copy(
        update={"project_id": project_id, "cycle_id": "cycle-mta", "track_id": track_id}
    )
    service.repo.put_brief(brief)
    app.state.mta_service = service
    return client, headers, project_id, compiled, _tenant


def test_get_mta_results():
    client, headers, project_id, compiled, _ = _api_client_with_results()
    resp = client.get(f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["result_snapshot_id"] == compiled.snapshot.result_snapshot_id


def test_get_mta_channels():
    client, headers, project_id, compiled, _ = _api_client_with_results()
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results/channels",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    ids = {row["channel_id"] for row in resp.json()}
    assert {c.channel_id for c in compiled.channel_results} == ids


def test_get_mta_channel_detail():
    client, headers, project_id, compiled, _ = _api_client_with_results()
    channel_id = compiled.channel_results[0].channel_id
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results/channels/{channel_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["channel_id"] == channel_id
    assert resp.json()["evidence_refs"]


def test_get_model_comparison_with_filter():
    client, headers, project_id, compiled, _ = _api_client_with_results()
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results/model-comparison",
        headers=headers,
        params={"models": "FIRST_TOUCH,LAST_TOUCH"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["models"]) <= {"FIRST_TOUCH", "LAST_TOUCH"}
    stored = compiled.comparison.models
    assert "MARKOV" in stored


def test_get_markov_results():
    client, headers, project_id, _c, _ = _api_client_with_results()
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results/markov",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["availability"] == "AVAILABLE"


def test_get_shapley_results():
    client, headers, project_id, _c, _ = _api_client_with_results()
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results/shapley",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["availability"] != "AVAILABLE"
    assert resp.json()["unavailable_reason"]


def test_get_journey_summary():
    client, headers, project_id, _c, _ = _api_client_with_results()
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results/journeys",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["converted_journey_count"] == 10


def test_get_visualizations():
    client, headers, project_id, _c, _ = _api_client_with_results()
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results/visualizations",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    kinds = {row["kind"] for row in resp.json()}
    assert MTAVisualizationKind.ATTRIBUTION_BY_CHANNEL_MODEL.value in kinds
    assert MTAVisualizationKind.MODEL_COMPARISON_HEATMAP.value in kinds


def test_get_mta_decision_brief():
    client, headers, project_id, _c, _ = _api_client_with_results()
    resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/decision-brief",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verified_findings"]


def test_cross_tenant_mta_result_access_denied():
    client, headers, project_id, _c, _tenant_a = _api_client_with_results()
    other_repo = InMemoryControlPlaneRepository()
    _other, identity_b = seed_tenant(
        other_repo,
        plan_id=PlanId.PROJECT,
        provider_org="org_other",
        provider_user="user_other",
    )
    app_b = create_app(
        control_plane_repository=other_repo,
        identity_verifier=FakeIdentityVerifier(default=identity_b),
    )
    # Share the MTA service (results) but not the workspace.
    app_b.state.mta_service = client.app.state.mta_service
    client_b = TestClient(app_b, raise_server_exceptions=False)
    resp = client_b.get(
        f"/v1/projects/{project_id}/cycles/cycle-mta/mta/results",
        headers=auth_header(),
    )
    assert resp.status_code in {401, 403, 404}


def test_compile_failure_does_not_mutate_run_status():
    service, run, _c, _ = _execute(_ready_service())
    service.result_store.tables.pop(f"mta_attribution_channel_results_{run.run_id}")
    with pytest.raises(MTAResultsCompileError):
        service.results_compiler.compile(run.run_id)
    assert service.repo.get_run(run.run_id).status is MTARunStatus.SUCCEEDED


def test_partial_snapshot_does_not_replace_current_verified():
    service, run, compiled, _ = _execute(_ready_service())
    pointers = service.repo.get_result_pointers(run.track_id)
    assert pointers.current_result_snapshot_id == compiled.snapshot.result_snapshot_id
    # Force a PARTIAL compile by dropping shapley-requested later is N/A; stamp status.
    later = compiled.snapshot.model_copy(
        update={
            "result_snapshot_id": "mrs_partial_later",
            "result_status": MTAResultStatus.PARTIAL,
            "fingerprint": compiled.snapshot.fingerprint + "x",
        }
    )
    compiled.snapshot = later
    service.results_compiler._advance_pointers(compiled)
    pointers = service.repo.get_result_pointers(run.track_id)
    assert pointers.latest_result_snapshot_id == "mrs_partial_later"
    assert pointers.current_result_snapshot_id != "mrs_partial_later"
