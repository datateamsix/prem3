"""Live Music Center SYNTHETIC_DEMO MTA result intelligence proof.

Run:
  uv run pytest tests/integration/test_mta_m5_02_live_bq.py -m live_bq -v

Uses operational journeys already in modelready-m3.prem3_modeling from M5-01A
and the existing MTAService / DP6MAMAdapter path. Does not rewrite the worker.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.domain.channels import AI_SEARCH_CHANNEL_ID, cached_channel_registry
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
from app.modeling.mta.results_contracts import (
    MetricAvailability,
    MTAEvidenceAuthority,
    MTAVisualizationKind,
)
from app.modeling.mta.service import MTAService
from app.modeling.mta.sql.registry import cached_sql_asset_manifest
from app.modeling.mta.sql.renderer import render_sql_asset

pytestmark = pytest.mark.live_bq

REPO = Path(__file__).resolve().parents[2]
PROOF_PATH = REPO / "evaluation" / "meridian_music_center_mta_results_proof.json"


def _project_id() -> str:
    return (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("M3_GCP_PROJECT")
        or "modelready-m3"
    )


def _load_live_journeys(gcp_project: str) -> list[dict]:
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
    LIMIT 2000
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
            }
        )
    return rows


@pytest.fixture(scope="module")
def live_compiled():
    gcp_project = _project_id()
    journeys = _load_live_journeys(gcp_project)
    if not journeys:
        pytest.fail(
            "No operational journeys in prem3_modeling.mta_journeys. "
            "M5-01A refresh must populate live SYNTHETIC_DEMO journeys first."
        )
    service = MTAService(
        dispatcher=FakeMTADispatcher(),
        dp6=DP6MAMAdapter(),
    )
    service.results_compiler.evidence_authority = MTAEvidenceAuthority.SYNTHETIC_DEMO
    contract = build_input_contract(
        input_contract_id="ic_m502_live",
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof",
        track_id="mta",
        ga4_dataset_id="analytics_music_center_synthetic",
        source_schema_version="v1",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        conversion_event="purchase",
        conversion_period_start="2024-01-01",
        conversion_period_end="2024-12-31",
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
            AttributionModelId.SHAPLEY,
        ),
    )
    service.repo.put_contract(contract)
    receipt = service.evaluate_readiness(
        tenant_id="music-center",
        project_id="music-center",
        cycle_id="proof",
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
        cycle_id="proof",
        track_id="mta",
        journeys=journeys,
    )
    run = run.model_copy(update={"proof_label": "SYNTHETIC_DEMO"})
    service.repo.put_run(run)
    service.launch_dispatch(dispatch_id=run.dispatch_id)
    service.execute_fit_dispatch(dispatch_id=run.dispatch_id)
    snap = service.repo.get_snapshot_for_run(run.run_id)
    if snap is None:
        compiled, brief = service.compile_results(
            run_id=run.run_id,
            evidence_authority=MTAEvidenceAuthority.SYNTHETIC_DEMO,
        )
    else:
        compiled = service.repo.get_compiled_results(snap.result_snapshot_id)
        brief = service.repo.get_brief_for_snapshot(snap.result_snapshot_id)
        if compiled.snapshot.evidence_authority is not MTAEvidenceAuthority.SYNTHETIC_DEMO:
            compiled, brief = service.compile_results(
                run_id=run.run_id,
                evidence_authority=MTAEvidenceAuthority.SYNTHETIC_DEMO,
            )
    proof = {
        "evidence_authority": compiled.snapshot.evidence_authority.value,
        "result_snapshot_id": compiled.snapshot.result_snapshot_id,
        "run_id": compiled.snapshot.run_id,
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
        "channel_registry_fingerprint": compiled.snapshot.channel_registry_fingerprint,
    }
    PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return service, compiled, brief, journeys, gcp_project


def test_music_center_result_snapshot_is_synthetic_demo(live_compiled):
    _service, compiled, _brief, _journeys, _gcp = live_compiled
    assert compiled.snapshot.evidence_authority is MTAEvidenceAuthority.SYNTHETIC_DEMO
    assert compiled.snapshot.result_status.value in {"VERIFIED", "PARTIAL"}


def test_music_center_channel_ids_use_registry_v1(live_compiled):
    _service, compiled, _brief, _journeys, _gcp = live_compiled
    registry = cached_channel_registry(1)
    for row in compiled.channel_results:
        assert row.channel_id in registry.channel_ids()
    assert compiled.snapshot.channel_registry_fingerprint == registry.fingerprint


def test_music_center_model_comparison_available(live_compiled):
    _service, compiled, _brief, _journeys, _gcp = live_compiled
    assert compiled.comparison.rows
    assert compiled.snapshot.models_completed


def test_music_center_markov_evidence_available(live_compiled):
    _service, compiled, _brief, _journeys, _gcp = live_compiled
    assert compiled.markov is not None
    assert compiled.markov.availability is MetricAvailability.AVAILABLE
    assert compiled.markov.transitions


def test_music_center_ai_search_visible_if_source_contains_it(live_compiled):
    _service, compiled, _brief, journeys, _gcp = live_compiled
    source_has_ai = any(AI_SEARCH_CHANNEL_ID in (j.get("channels") or []) for j in journeys)
    result_has_ai = any(c.channel_id == AI_SEARCH_CHANNEL_ID for c in compiled.channel_results)
    assert result_has_ai is source_has_ai


def test_music_center_role_evidence_is_derived(live_compiled):
    _service, compiled, _brief, _journeys, _gcp = live_compiled
    assert compiled.roles
    # Roles come from numeric position features, not hardcoded names.
    assert all(r.evidence_refs for r in compiled.roles)


def test_music_center_visualization_contracts_compile(live_compiled):
    _service, compiled, _brief, _journeys, _gcp = live_compiled
    kinds = {v.kind for v in compiled.visualizations}
    assert MTAVisualizationKind.ATTRIBUTION_BY_CHANNEL_MODEL in kinds
    assert MTAVisualizationKind.CHANNEL_ROLE_POSITION in kinds
    assert all(
        v.source_result_snapshot_id == compiled.snapshot.result_snapshot_id
        for v in compiled.visualizations
    )


def test_music_center_shapley_unavailable_reason(live_compiled):
    _service, compiled, _brief, _journeys, _gcp = live_compiled
    if compiled.shapley.availability is MetricAvailability.AVAILABLE:
        assert compiled.shapley.channel_credit
        return
    assert compiled.shapley.unavailable_reason
    assert compiled.shapley.availability in {
        MetricAvailability.NOT_RUN,
        MetricAvailability.BLOCKED_BY_PREFLIGHT,
        MetricAvailability.NOT_APPLICABLE,
    }


def test_music_center_result_summary_ddl_renders(live_compiled):
    _service, _compiled, _brief, _journeys, gcp_project = live_compiled
    entry = cached_sql_asset_manifest().get("create_result_summary_tables_v1")
    sql, _ = render_sql_asset(
        entry,
        params={"project_id": gcp_project, "modeling_dataset": "prem3_modeling"},
    )
    assert "mta_result_snapshots" in sql
    assert "mta_channel_role_evidence" in sql
