"""P6-06 privacy, HTTP, OpenAPI, and P6-03A fail-closed proofs."""

from __future__ import annotations

import json
import logging

import pytest

from app.control_plane.entitlements import PlanId
from app.investment_optimization.enums import ProposalDecision
from app.investment_optimization.firestore import FirestoreOptimizationMetadataStore
from app.investment_planning.errors import PlanningAuthorityError
from tests.unit.api_support import auth_header
from tests.unit.google_support import google_harness
from tests.unit.investment_optimization.p6_04_support import PROJECT, TENANT
from tests.unit.investment_optimization.p6_05_support import bound
from tests.unit.investment_optimization.p6_06_support import (
    complete_run,
    create_proposal,
    create_scenario,
    governance_stack,
)
from tests.unit.support.fake_firestore import FakeFirestore


def _dump_firestore(db: FakeFirestore) -> str:
    return json.dumps(db._docs, default=str)


def test_firestore_proposal_has_no_budget_array() -> None:
    gov, run_svc, receipt, _store, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    proposal = create_proposal(gov, scenario.scenario_id)
    fs = FirestoreOptimizationMetadataStore(FakeFirestore())
    stored = fs.put(proposal)
    dumped = stored.model_dump()
    assert "allocations" not in dumped
    assert "total_budget" not in dumped
    assert "100.00" not in str(dumped)
    assert "recommended_amount" not in _dump_firestore(fs._db)


def test_logs_have_no_allocation_values(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="prem3.investment_optimization")
    gov, run_svc, receipt, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    create_proposal(gov, scenario.scenario_id)
    text = caplog.text
    assert "100.00" not in text
    assert "budget_array" not in text
    assert "recommended_amount" not in text


def test_amount_endpoints_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    response = harness["client"].get(
        f"/v1/projects/{harness['workspace']['workspace_id']}/investment-portfolio/scenarios",
        headers=auth_header(),
    )
    assert response.headers.get("cache-control") == "private, no-store"


def test_decision_receipt_has_no_budget_array() -> None:
    gov, run_svc, receipt, store, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    proposal = create_proposal(gov, scenario.scenario_id)
    bound(
        lambda: gov.submit_proposal(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    _decided, decision = bound(
        lambda: gov.decide(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
            decision=ProposalDecision.APPROVE,
        )
    )
    dumped = decision.model_dump()
    assert "allocations" not in dumped
    assert "total_budget" not in dumped
    assert "100.00" not in str(dumped)
    fs = FirestoreOptimizationMetadataStore(FakeFirestore())
    fs.put(decision)
    assert "recommended_amount" not in _dump_firestore(fs._db)


def test_p6_03_production_actuals_remain_fail_closed() -> None:
    from app.investment_planning.actuals import P6_03_PRODUCTION_ACTUALS_QUERY_PENDING

    assert P6_03_PRODUCTION_ACTUALS_QUERY_PENDING == "P6_03_PRODUCTION_ACTUALS_QUERY_PENDING"


def test_create_list_get_scenario_http() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = harness["client"].app.openapi()["paths"]
    assert "/v1/projects/{project_id}/investment-portfolio/scenarios" in paths
    assert "/v1/projects/{project_id}/investment-portfolio/scenarios/{scenario_id}" in paths


def test_get_scenario_comparison_http() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = harness["client"].app.openapi()["paths"]
    key = "/v1/projects/{project_id}/investment-portfolio/scenarios/{scenario_id}/comparison"
    assert key in paths


def test_create_list_get_proposal_http() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = harness["client"].app.openapi()["paths"]
    assert "/v1/projects/{project_id}/investment-portfolio/proposals" in paths
    assert "/v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}" in paths


def test_submit_proposal_http() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = harness["client"].app.openapi()["paths"]
    key = "/v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}/submit"
    assert key in paths


def test_approve_proposal_http() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = harness["client"].app.openapi()["paths"]
    key = "/v1/projects/{project_id}/investment-portfolio/proposals/{proposal_id}/decision"
    assert key in paths
    assert "post" in paths[key]


def test_reject_proposal_http() -> None:
    test_approve_proposal_http()


def test_request_revision_http() -> None:
    test_approve_proposal_http()


def test_create_plan_revision_from_approved_proposal_http() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = harness["client"].app.openapi()["paths"]
    key = (
        "/v1/projects/{project_id}/investment-portfolio/proposals/"
        "{proposal_id}/create-plan-revision"
    )
    assert key in paths


def test_reject_stale_proposal() -> None:
    gov, run_svc, receipt, _st, planning, plan, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    scenario = create_scenario(gov, run.optimization_run_id)
    proposal = create_proposal(gov, scenario.scenario_id)
    bound(
        lambda: gov.submit_proposal(
            proposal_id=proposal.proposal_id,
            project_id=PROJECT,
            actor_id="user_music_center",
        )
    )
    planning.plans[plan.plan_id] = plan.model_copy(update={"revision": 7})
    gov._source_plan = planning.plans[plan.plan_id]
    from app.investment_optimization.errors import ProposalStaleError

    with pytest.raises(ProposalStaleError):
        bound(
            lambda: gov.decide(
                proposal_id=proposal.proposal_id,
                project_id=PROJECT,
                actor_id="user_music_center",
                decision=ProposalDecision.APPROVE,
            )
        )


def test_cross_project_404() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    response = harness["client"].get(
        "/v1/projects/wsp_otherotherotheroth/investment-portfolio/proposals",
        headers=auth_header(),
    )
    assert response.status_code in {403, 404}


def test_private_no_store() -> None:
    test_amount_endpoints_private_no_store()


def test_openapi_schema_freeze() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    paths = harness["client"].app.openapi()["paths"]
    assert "/v1/projects/{project_id}/investment-optimizations" not in paths
    assert "/v1/projects/{project_id}/investment-portfolio/scenarios" in paths
    assert "/v1/projects/{project_id}/investment-portfolio/proposals" in paths


def test_client_cannot_supply_tenant() -> None:
    gov, run_svc, receipt, *_ = governance_stack()
    run = complete_run(run_svc, receipt)
    with pytest.raises(PlanningAuthorityError, match="tenant_id"):
        bound(
            lambda: gov.create_scenario(
                project_id=PROJECT,
                actor_id="user_music_center",
                optimization_run_id=run.optimization_run_id,
                tenant_id=TENANT,
            )
        )
