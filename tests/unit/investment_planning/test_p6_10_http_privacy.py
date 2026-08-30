"""P6-10 HTTP no-store, client authority, and metadata persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.control_plane.entitlements import PlanId
from app.investment_optimization.firestore import FirestoreOptimizationMetadataStore
from app.investment_optimization.store import (
    InMemoryOptimizationMetadataStore,
    assert_optimization_metadata_only,
)
from app.investment_planning.errors import PersistenceBarrierError
from app.investment_planning.outcomes.models import ExecutionAdherenceArtifact
from tests.unit.api_support import auth_header
from tests.unit.google_support import google_harness
from tests.unit.investment_planning.p6_10_support import (
    PROJECT,
    RECOMMENDED_REF,
    RECOMMENDED_SHARES,
    TENANT,
    now,
    outcome_service,
    p6_06_ledger,
    p6_06_receipt,
)
from tests.unit.support.fake_firestore import FakeFirestore


def test_allocation_artifact_cannot_be_stored() -> None:
    store = InMemoryOptimizationMetadataStore()
    artifact = ExecutionAdherenceArtifact(
        execution_adherence_id="oeadh_p610artifact00001",
        planned_vs_actual=(("search", 50.0, 48.0),),
        fingerprint="fp",
    )
    try:
        store.put(artifact)  # type: ignore[arg-type]
        raise AssertionError("amount-bearing artifact must not persist")
    except PersistenceBarrierError:
        pass


def test_outcome_metadata_only() -> None:
    service = outcome_service()
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt)
    decision = service.bind_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=RECOMMENDED_SHARES,
    )
    assert_optimization_metadata_only(decision)
    dumped = decision.model_dump()
    assert "recommended_total" not in dumped
    assert "allocations" not in dumped


def test_outcomes_http_is_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    decision_time = now().isoformat()
    rec_time = (now() - timedelta(days=1)).isoformat()
    pred_time = (now() - timedelta(hours=1)).isoformat()
    created = harness["client"].post(
        f"/v1/projects/{project_id}/investment-portfolio/outcomes/prediction-evidence",
        headers=auth_header(),
        json={
            "predicted_unit": "revenue",
            "recommendation_as_of_time": rec_time,
            "decision_as_of_time": decision_time,
            "prediction_evidence_as_of_time": pred_time,
            "predicted_value": 100.0,
            "frontier_selection_ref": "osel_p610selection000001",
        },
    )
    assert created.status_code == 200, created.text
    assert created.headers.get("cache-control") == "private, no-store"
    assert created.headers.get("pragma") == "no-cache"
    assert "SIMULATION_EVIDENCE_NOT_AVAILABLE" in created.json()["limitations"]
    evidence_id = created.json()["prediction_evidence_id"]
    fetched = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio/outcomes/prediction-evidence/{evidence_id}",
        headers=auth_header(),
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.headers.get("cache-control") == "private, no-store"


def test_client_cannot_submit_prediction_error() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].post(
        f"/v1/projects/{project_id}/investment-portfolio/outcomes/prediction-errors",
        headers=auth_header(),
        json={
            "prediction_evidence_id": "opred_missing",
            "signed_error": 12.5,
            "realized_percentile": 0.9,
            "error_class": "WITHIN_EXPECTED_RANGE",
        },
    )
    assert response.status_code == 422


def test_http_bind_uses_existing_p6_06_receipts() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    tenant_id = harness["tenant"].tenant_id
    store = harness["client"].app.state.optimization_store
    receipt = p6_06_receipt(tenant_id=tenant_id, project_id=project_id)
    ledger = p6_06_ledger(receipt=receipt)
    store.put(receipt)
    store.put(ledger)
    created = harness["client"].post(
        f"/v1/projects/{project_id}/investment-portfolio/outcomes/decisions",
        headers=auth_header(),
        json={
            "proposal_decision_receipt_id": receipt.decision_receipt_id,
            "planning_decision_record_id": ledger.decision_id,
            "recommended_portfolio_ref": RECOMMENDED_REF,
            "decided_portfolio_ref": RECOMMENDED_REF,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["proposal_decision_receipt_id"] == receipt.decision_receipt_id
    assert created.json()["decision"] in {"ACCEPT", "ACCEPT_WITH_MODIFICATIONS"}
    assert created.headers.get("cache-control") == "private, no-store"


def test_no_second_proposal_decision_route() -> None:
    outcomes = Path("app/service/routers/outcomes.py").read_text(encoding="utf-8")
    portfolio = Path("app/service/routers/investment_portfolio.py").read_text(encoding="utf-8")
    assert '"/decisions"' in outcomes
    assert '"/decision"' not in outcomes
    assert '"/proposals/{proposal_id}/decision"' in portfolio
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = {getattr(route, "path", "") for route in harness["client"].app.routes}
    assert not any("outcomes" in path and path.endswith("/decision") for path in paths)


def test_firestore_outcome_metadata_has_no_amount_keys() -> None:
    import json

    service = outcome_service()
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt)
    decision = service.bind_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=RECOMMENDED_SHARES,
    )
    fs = FirestoreOptimizationMetadataStore(FakeFirestore())
    fs.put(decision)
    dumped = json.dumps(fs._db._docs, default=str)
    assert "recommended_total" not in dumped
    assert "allocations" not in dumped
    assert "planned_vs_actual" not in dumped


def test_http_observation_rejects_empty_sources() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].post(
        f"/v1/projects/{project_id}/investment-portfolio/outcomes/outcome-observations",
        headers=auth_header(),
        json={
            "investment_decision_ref": "oidec_p610decision000030",
            "outcome_metric_id": "kpi_revenue",
            "outcome_unit": "revenue",
            "semantic_type": "OBSERVED_REVENUE",
            "observation_window_start": datetime(2026, 4, 1, tzinfo=UTC).isoformat(),
            "observation_window_end": datetime(2026, 6, 30, tzinfo=UTC).isoformat(),
            "as_of_time": datetime(2026, 7, 2, tzinfo=UTC).isoformat(),
            "source_authority": "GOVERNED_BIGQUERY",
            "source_refs": [],
            "observed_value": 100.0,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "OUTCOME_SOURCE_NOT_GOVERNED"
