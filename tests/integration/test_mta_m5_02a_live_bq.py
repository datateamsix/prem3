"""LIVE_BQ Music Center v2 → real DP6 → BQ read-back → new snapshot.

Run:
  uv run pytest tests/integration/test_mta_m5_02a_live_bq.py -m live_bq -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.domain.channels import AI_SEARCH_CHANNEL_ID, cached_channel_registry
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.adapters.dp6_mam_v1_0_11 import DP6MAMAdapter
from app.modeling.mta.bq_executor import client_for_project, run_query
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
from app.modeling.mta.music_center_fixture_v2 import (
    DEMO_ATTRIBUTION_MODELS,
    WINDOW_END,
    WINDOW_START,
    fixture_contract,
    music_center_v2_events,
)
from app.modeling.mta.provisioning_service import MTAProvisioningService
from app.modeling.mta.results_contracts import (
    MetricAvailability,
    MTAEvidenceAuthority,
    MTAVisualizationKind,
)
from app.modeling.mta.runtime_contracts import MTAComputationAuthority, MTARefreshWindow
from app.modeling.mta.service import MTAService
from app.modeling.mta.synthetic_music_center import load_synthetic_ga4_events

pytestmark = [pytest.mark.live_bq, pytest.mark.real_dp6]

REPO = Path(__file__).resolve().parents[2]
PROOF_PATH = REPO / "evaluation" / "meridian_music_center_mta_real_dp6_demo_proof.json"
HISTORICAL_FAKE_SNAPSHOT = "mrs_11ec341be2c8486a"
P0_VIZ = (
    MTAVisualizationKind.ATTRIBUTION_BY_CHANNEL_MODEL,
    MTAVisualizationKind.MODEL_COMPARISON_HEATMAP,
    MTAVisualizationKind.CHANNEL_ROLE_POSITION,
    MTAVisualizationKind.MARKOV_TRANSITION_MATRIX,
    MTAVisualizationKind.MARKOV_REMOVAL_EFFECT,
    MTAVisualizationKind.SHAPLEY_CONTRIBUTION,
    MTAVisualizationKind.TOP_CONVERSION_PATHS,
    MTAVisualizationKind.PATH_LENGTH_DISTRIBUTION,
    MTAVisualizationKind.TIME_TO_CONVERSION_DISTRIBUTION,
    MTAVisualizationKind.MODEL_SENSITIVITY_RANGE,
)


def _project_id() -> str:
    return (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("M3_GCP_PROJECT")
        or "modelready-m3"
    )


def _load_sept_journeys(gcp_project: str) -> list[dict]:
    client = client_for_project(gcp_project)
    sql = f"""
    SELECT
      journey_id,
      subject_key,
      conversion_event,
      CAST(conversion_ts AS STRING) AS conversion_ts,
      CAST(conversion_value AS FLOAT64) AS conversion_value,
      channels,
      ARRAY(SELECT CAST(ts AS STRING) FROM UNNEST(touchpoint_timestamps) AS ts) AS touchpoint_times,
      path_string,
      touchpoint_count
    FROM `{gcp_project}.prem3_modeling.mta_journeys`
    WHERE conversion_date BETWEEN '{WINDOW_START.isoformat()}' AND '{WINDOW_END.isoformat()}'
    LIMIT 5000
    """
    result = run_query(client, sql, fetch=True)
    rows: list[dict] = []
    for raw in result.rows:
        channels = [str(c) for c in (raw.get("channels") or [])]
        rows.append(
            {
                "subject_key": str(raw.get("subject_key") or raw.get("journey_id")),
                "channels": channels,
                "touchpoint_times": list(raw.get("touchpoint_times") or []),
                "conversion_ts": raw.get("conversion_ts"),
                "converted": True,
                "conversion_value": float(raw.get("conversion_value") or 1.0),
                "path_string": raw.get("path_string") or " > ".join(channels),
                "conversion_event": raw.get("conversion_event") or "purchase",
                "journey_id": raw.get("journey_id"),
            }
        )
    return rows


@pytest.fixture(scope="module")
def live_v2_compiled():
    gcp_project = _project_id()
    fixture = fixture_contract(project_id=gcp_project)
    events = music_center_v2_events()
    load_synthetic_ga4_events(project_id=gcp_project, events=events, replace=True)

    provisioning = MTAProvisioningService(live=True)
    plan = provisioning.compile_infrastructure_plan(
        plan_id="live_mc_v2",
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof-v2",
        track_id="mta",
        gcp_project_id=gcp_project,
    )
    provisioning.provision_infrastructure(plan, approved=True, dry_run_first=True)
    window = MTARefreshWindow(
        run_date="2024-10-04",
        settlement_days=3,
        source_overlap_days=2,
        lookback_window_days=30,
        source_start_date=WINDOW_START.isoformat(),
        source_end_date=WINDOW_END.isoformat(),
        affected_conversion_start=WINDOW_START.isoformat(),
        affected_conversion_end=WINDOW_END.isoformat(),
        fingerprint=canonical_fingerprint({"forced": True, "label": "SYNTHETIC_DEMO_V2"}),
        calculation_trace=("SYNTHETIC_DEMO Music Center fixture v2 window",),
    )
    provisioning.execute_refresh(
        gcp_project_id=gcp_project,
        window=window,
        lookback_window_days=30,
    )
    journeys = _load_sept_journeys(gcp_project)
    if not journeys:
        pytest.fail("No September v2 journeys after refresh.")

    adapter = DP6MAMAdapter(fake=False)
    assert adapter.is_fake is False
    service = MTAService(dispatcher=FakeMTADispatcher(), dp6=adapter)
    service.results_compiler.evidence_authority = MTAEvidenceAuthority.SYNTHETIC_DEMO
    contract = build_input_contract(
        input_contract_id="ic_m502a_live",
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof-v2",
        track_id="mta",
        ga4_dataset_id="analytics_music_center_synthetic",
        source_schema_version="v1",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        conversion_event="purchase",
        conversion_period_start=WINDOW_START.isoformat(),
        conversion_period_end=WINDOW_END.isoformat(),
        lookback_window_days=30,
        identity_strategy=IdentityStrategy.PSEUDO_ID_ONLY,
        sessionization_policy=SessionizationPolicy.GA4_SESSION_ID_V1,
        traffic_source_policy=SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1,
        channel_grouping_version="v1",
        attribution_models=DEMO_ATTRIBUTION_MODELS,
    )
    service.repo.put_contract(contract)
    receipt = service.evaluate_readiness(
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof-v2",
        track_id="mta",
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
    run = service.start_run(
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof-v2",
        track_id="mta",
        journeys=journeys,
        proof_label="SYNTHETIC_DEMO",
        runtime_mode="SYNTHETIC_DEMO",
    )
    service.launch_dispatch(dispatch_id=run.dispatch_id)
    run_receipt = service.execute_fit_dispatch(dispatch_id=run.dispatch_id)
    compiled, brief = service.compile_results(
        run_id=run.run_id,
        evidence_authority=MTAEvidenceAuthority.SYNTHETIC_DEMO,
    )
    proof = {
        "class": "LIVE_BQ",
        "evidence_authority": compiled.snapshot.evidence_authority.value,
        "computation_authority": compiled.snapshot.computation_authority.value,
        "result_snapshot_id": compiled.snapshot.result_snapshot_id,
        "historical_fake_snapshot_id": HISTORICAL_FAKE_SNAPSHOT,
        "run_id": compiled.snapshot.run_id,
        "receipt_id": run_receipt.receipt_id,
        "fingerprint": compiled.snapshot.fingerprint,
        "models_completed": list(compiled.snapshot.models_completed),
        "shapley_availability": compiled.shapley.availability.value,
        "shapley_reason": compiled.shapley.unavailable_reason,
        "channel_ids": [c.channel_id for c in compiled.channel_results],
        "roles": {r.channel_id: [lab.value for lab in r.labels] for r in compiled.roles},
        "ai_search_present": any(
            c.channel_id == AI_SEARCH_CHANNEL_ID for c in compiled.channel_results
        ),
        "visualization_kinds": [v.kind.value for v in compiled.visualizations],
        "brief_id": None if brief is None else brief.brief_id,
        "journey_count": compiled.journeys.converted_journey_count,
        "source": f"{gcp_project}.analytics_music_center_synthetic",
        "date_range": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
        "fixture_fingerprint": fixture.fixture_fingerprint,
        "dp6_version": "1.0.11",
        "adapter_is_fake": adapter.is_fake,
        "channel_registry_fingerprint": compiled.snapshot.channel_registry_fingerprint,
    }
    PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return service, compiled, brief, journeys, gcp_project, run_receipt


def test_v2_snapshot_is_synthetic_demo_real_runtime(live_v2_compiled):
    _service, compiled, _brief, _journeys, _gcp, receipt = live_v2_compiled
    assert compiled.snapshot.evidence_authority is MTAEvidenceAuthority.SYNTHETIC_DEMO
    assert compiled.snapshot.computation_authority == MTAComputationAuthority.REAL_PINNED_RUNTIME
    assert receipt.computation_authority == MTAComputationAuthority.REAL_PINNED_RUNTIME
    assert compiled.snapshot.result_snapshot_id != HISTORICAL_FAKE_SNAPSHOT


def test_v2_channel_ids_use_registry_v1(live_v2_compiled):
    _service, compiled, _brief, _journeys, _gcp, _receipt = live_v2_compiled
    registry = cached_channel_registry(1)
    for row in compiled.channel_results:
        assert row.channel_id in registry.channel_ids()


def test_v2_includes_last_non_direct(live_v2_compiled):
    _service, compiled, _brief, _journeys, _gcp, _receipt = live_v2_compiled
    assert AttributionModelId.LAST_NON_DIRECT.value in compiled.snapshot.models_requested or (
        "LAST_NON_DIRECT" in compiled.snapshot.models_completed
    )


def test_v2_p0_visualizations(live_v2_compiled):
    _service, compiled, _brief, _journeys, _gcp, _receipt = live_v2_compiled
    kinds = {v.kind for v in compiled.visualizations}
    for kind in P0_VIZ:
        assert kind in kinds
    shapley_viz = next(
        v for v in compiled.visualizations if v.kind is MTAVisualizationKind.SHAPLEY_CONTRIBUTION
    )
    if compiled.shapley.availability is not MetricAvailability.AVAILABLE:
        assert shapley_viz.available is False
        assert shapley_viz.unavailable_reason


def test_v2_ai_search_visible(live_v2_compiled):
    _service, compiled, _brief, journeys, _gcp, _receipt = live_v2_compiled
    source_has_ai = any(AI_SEARCH_CHANNEL_ID in (j.get("channels") or []) for j in journeys)
    result_has_ai = any(c.channel_id == AI_SEARCH_CHANNEL_ID for c in compiled.channel_results)
    assert result_has_ai is source_has_ai
    assert source_has_ai is True


def test_v2_brief_compiled(live_v2_compiled):
    _service, _compiled, brief, _journeys, _gcp, _receipt = live_v2_compiled
    assert brief is not None
    assert brief.brief_id
