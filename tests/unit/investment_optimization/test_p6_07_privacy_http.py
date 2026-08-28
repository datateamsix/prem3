"""P6-07 privacy: Firestore metadata, logs, and private HTTP."""

from __future__ import annotations

import json
import logging

import pytest

from app.control_plane.entitlements import PlanId
from app.investment_optimization.enums import OptimizationBudgetMode, OptimizationObjectiveMode
from app.investment_optimization.firestore import FirestoreOptimizationMetadataStore
from app.modeling.common.errors import FitRuntimeError
from app.tools.meridian_optimizer_worker import FORBIDDEN_REQUEST_KEYS, execute_server_owned_request
from tests.unit.api_support import auth_header
from tests.unit.google_support import google_harness
from tests.unit.investment_optimization.p6_04_support import PROJECT
from tests.unit.investment_optimization.p6_05_support import bound, run_service
from tests.unit.investment_optimization.p6_07_support import (
    ScriptedFlexibleBudgetOptimizer,
    advanced_service,
    constraint_set,
    cost_assumption,
    governed_revenue,
    line_bound,
    persist_assumption,
    persist_constraint,
    pinned_assumptions,
)
from tests.unit.support.fake_firestore import FakeFirestore


def _dump_firestore(db: FakeFirestore) -> str:
    return json.dumps(db._docs, default=str)


def test_firestore_metadata_no_values() -> None:
    optimizer = ScriptedFlexibleBudgetOptimizer()
    _service, _receipt, store, *_ = run_service(optimizer=optimizer)
    adv = advanced_service(store=store, object_store=_service._object_store)
    assumption_ref = persist_assumption(
        adv, pinned_assumptions(cost_per_media_unit=(cost_assumption(),))
    )
    constraint_ref = persist_constraint(
        adv, constraint_set(line_bounds=(line_bound(lower="10.00"),))
    )
    dumped = assumption_ref.model_dump()
    assert "12.50" not in str(dumped)
    assert "cost_per_media_unit" not in dumped
    assert "value" not in dumped
    fs = FirestoreOptimizationMetadataStore(FakeFirestore())
    fs.put(assumption_ref)
    fs.put(constraint_ref)
    text = _dump_firestore(fs._db)
    assert "12.50" not in text
    assert "line_bounds" not in text
    assert "total_budget" not in text


def test_logs_no_amounts(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="prem3.investment_optimization")
    optimizer = ScriptedFlexibleBudgetOptimizer()
    service, receipt, store, *_ = run_service(optimizer=optimizer)
    adv = advanced_service(store=store, object_store=service._object_store)
    assumptions = persist_assumption(adv, pinned_assumptions(revenue_per_kpi=governed_revenue()))
    bound(
        lambda: service.create_run(
            project_id=PROJECT,
            actor_id="user_music_center",
            readiness_receipt_id=receipt.receipt_id,
            budget_mode=OptimizationBudgetMode.FLEXIBLE,
            objective_mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
            assumption_set_id=assumptions.assumption_set_id,
            target_roi=2.0,
        )
    )
    text = caplog.text
    assert "12.50" not in text
    assert "100.00" not in text
    assert "budget_array" not in text


def test_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    client = harness["client"]
    headers = auth_header()
    project_id = harness["workspace"]["workspace_id"]
    for path in (
        f"/v1/projects/{project_id}/investment-portfolio/assumption-sets",
        f"/v1/projects/{project_id}/investment-portfolio/constraint-sets",
        f"/v1/projects/{project_id}/investment-portfolio/advanced-optimization-readiness",
        f"/v1/projects/{project_id}/investment-portfolio/optimizations",
    ):
        response = client.get(path, headers=headers)
        assert response.headers.get("cache-control") == "private, no-store"
    paths = client.app.openapi()["paths"]
    assert "/v1/projects/{project_id}/investment-portfolio/assumption-sets" in paths
    assert "/v1/projects/{project_id}/investment-portfolio/constraint-sets" in paths
    assert (
        "/v1/projects/{project_id}/investment-portfolio/constraint-sets/{constraint_set_id}/validate"
        in paths
    )
    assert "/v1/projects/{project_id}/investment-portfolio/advanced-optimization-readiness" in paths


def test_worker_rejects_constraint_assumption_amount_keys() -> None:
    assert "line_bounds" in FORBIDDEN_REQUEST_KEYS
    assert "cost_per_media_unit" in FORBIDDEN_REQUEST_KEYS
    assert "revenue_per_kpi" in FORBIDDEN_REQUEST_KEYS
    with pytest.raises(FitRuntimeError):
        execute_server_owned_request(
            {"optimization_run_id": "orun_aaaaaaaaaaaaaaaaaa", "line_bounds": []}
        )
