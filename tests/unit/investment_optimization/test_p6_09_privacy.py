"""P6-09 privacy: no amount keys in Firestore metadata; HTTP is no-store."""

from __future__ import annotations

from pathlib import Path

from app.control_plane.entitlements import PlanId
from app.investment_optimization.firestore import FirestoreOptimizationMetadataStore
from app.investment_optimization.risk.models import CandidateAllocationArtifact
from app.investment_optimization.store import (
    InMemoryOptimizationMetadataStore,
    assert_optimization_metadata_only,
)
from app.investment_planning.errors import PersistenceBarrierError
from tests.unit.api_support import auth_header
from tests.unit.google_support import google_harness
from tests.unit.investment_optimization.p6_09_support import (
    MODEL,
    NATIVE_SHARES,
    PLAN,
    PROJECT,
    READY,
    RUN,
    TENANT,
    risk_service,
)
from tests.unit.support.fake_firestore import FakeFirestore


def test_allocation_artifact_cannot_be_stored() -> None:
    store = InMemoryOptimizationMetadataStore()
    artifact = CandidateAllocationArtifact(
        candidate_portfolio_id="ocand_x",
        shares=NATIVE_SHARES,
        recommended_total="100.00",
        fingerprint="fp",
    )
    try:
        store.put(artifact)  # type: ignore[arg-type]
        raise AssertionError("amount-bearing artifact must not persist")
    except PersistenceBarrierError:
        pass


def test_policy_and_candidate_are_metadata_only() -> None:
    service = risk_service()
    policy = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
    )
    candidates = service.generate(
        policy=policy,
        native_shares=NATIVE_SHARES,
        optimization_run_id=RUN,
        base_approved_plan_ref=PLAN,
        input_fingerprint="input_fp",
    )
    assert_optimization_metadata_only(policy)
    assert_optimization_metadata_only(candidates[0])
    dumped = candidates[0].model_dump()
    assert "recommended_total" not in dumped
    assert "allocations" not in dumped


def test_risk_frontier_http_is_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    created = harness["client"].post(
        f"/v1/projects/{project_id}/investment-portfolio/risk-frontier/risk-evaluation-policies",
        headers=auth_header(),
        json={
            "objective": "MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
            "model_version_ref": "mmv_accepted_p609",
            "optimization_readiness_ref": "oready_p609",
            "risk_penalties_enabled": False,
        },
    )
    assert created.status_code == 200, created.text
    assert created.headers.get("cache-control") == "private, no-store"
    assert created.headers.get("pragma") == "no-cache"
    policy_id = created.json()["risk_evaluation_policy_id"]
    fetched = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio/risk-frontier/risk-evaluation-policies/{policy_id}",
        headers=auth_header(),
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.headers.get("cache-control") == "private, no-store"


def test_risk_package_does_not_mutate_approved_plan() -> None:
    root = Path("app/investment_optimization/risk")
    joined = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "approve_plan" not in joined
    assert "save_version" not in joined
    assert "APPROVED_PLAN" not in joined or "RiskBaselineKind.APPROVED_PLAN" in joined


def test_role_c_is_not_compiled_to_line_bounds() -> None:
    text = Path("app/investment_optimization/risk/exposure.py").read_text(encoding="utf-8")
    assert "LINE_MIN" not in text
    assert "LINE_MAX" not in text
    assert "spend_constraint" not in text


def test_firestore_risk_metadata_has_no_amount_keys() -> None:
    import json

    service = risk_service()
    policy = service.create_policy(
        tenant_id=TENANT,
        project_id=PROJECT,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
    )
    fs = FirestoreOptimizationMetadataStore(FakeFirestore())
    fs.put(policy)
    dumped = json.dumps(fs._db._docs, default=str)
    assert "recommended_total" not in dumped
    assert "budget_vector" not in dumped
    assert "100.00" not in dumped


def test_frontier_solver_stub_still_raises() -> None:
    text = Path("app/investment_optimization/adapter.py").read_text(encoding="utf-8")
    assert "PREM3_RISK_AWARE_FRONTIER" in text
    assert "CVaR / risk-aware frontier is deferred" in text
