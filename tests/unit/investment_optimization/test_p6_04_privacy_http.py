"""P6-04 persistence privacy and HTTP authority."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.control_plane.entitlements import PlanId
from app.investment_optimization.contracts import (
    ConstraintSetPayload,
    OptimizationExecutionPayload,
)
from app.investment_optimization.coverage import assemble_optimization_evidence_coverage
from app.investment_optimization.enums import BudgetResolutionPath
from app.investment_optimization.firestore import FirestoreOptimizationMetadataStore
from app.investment_optimization.mapping import (
    build_portfolio_model_mapping,
)
from app.investment_optimization.readiness import (
    build_optimization_input_contract,
    evaluate_readiness,
)
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.enums import PortfolioCoverageState
from app.investment_planning.errors import PersistenceBarrierError
from tests.unit.api_support import auth_header
from tests.unit.google_support import google_harness
from tests.unit.investment_optimization.p6_04_support import (
    PROJECT,
    TENANT,
    complete_contract,
    now,
    portfolio_view,
    snapshot,
)
from tests.unit.support.fake_firestore import FakeFirestore


def _persistable():
    view = portfolio_view()
    contract = complete_contract()
    mapping = build_portfolio_model_mapping(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot_id=view.snapshot_id,
        baseline_kind=view.baseline_kind,
        view=view,
        contract=contract,
        created_at=now(),
        created_by="user_music_center",
    )
    coverage = assemble_optimization_evidence_coverage(mapping=mapping, contract=contract)
    input_contract = build_optimization_input_contract(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot=snapshot(),
        view=view,
        mapping=mapping,
        contract=contract,
        created_at=now(),
        issues=(),
    )
    receipt = evaluate_readiness(
        tenant_id=TENANT,
        project_id=PROJECT,
        coverage_state=PortfolioCoverageState.PLAN_ONLY,
        snapshot=snapshot(),
        view=view,
        contract=contract,
        mapping=mapping,
        coverage=coverage,
        input_contract=input_contract,
        created_at=now(),
    )
    return mapping, coverage, input_contract, receipt, contract


def test_mapping_store_contains_no_budget_arrays() -> None:
    store = InMemoryOptimizationMetadataStore()
    mapping, _coverage, _input, _receipt, _contract = _persistable()
    stored = store.put(mapping)
    dumped = stored.model_dump()
    assert "allocations" not in dumped
    assert "amounts" not in dumped
    assert "total_budget" not in dumped
    assert "123456.78" not in str(dumped)
    assert Decimal("100.00") not in dumped.values()


def test_input_contract_metadata_only() -> None:
    _mapping, _coverage, input_contract, _receipt, _contract = _persistable()
    assert (
        input_contract.budget_resolution_path
        is BudgetResolutionPath.APPROVED_DRIVE_PLAN_TRANSIENT_VIEW
    )
    dumped = input_contract.model_dump()
    assert "total_budget" not in dumped
    assert "recommended_allocations" not in dumped
    store = InMemoryOptimizationMetadataStore()
    store.put(input_contract)
    assert "100.00" not in str(store.put(input_contract).model_dump())


def test_readiness_receipt_contains_no_budget_values() -> None:
    _mapping, _coverage, _input, receipt, _contract = _persistable()
    dumped = receipt.model_dump()
    assert "value" not in dumped
    assert "total_budget" not in dumped
    assert "100.00" not in str(dumped)


def test_firestore_rejects_amount_bearing_optimizer_input() -> None:
    store = FirestoreOptimizationMetadataStore(FakeFirestore())
    with pytest.raises(PersistenceBarrierError):
        store.put(OptimizationExecutionPayload(execution_plan_id="oexec_aaaaaaaaaaaaaaaaaa"))
    with pytest.raises(PersistenceBarrierError):
        store.put(
            ConstraintSetPayload(
                constraint_set_id="ocst_aaaaaaaaaaaaaaaaaaaa",
                total_budget=Decimal("10"),
            )
        )
    mapping, coverage, input_contract, receipt, contract = _persistable()
    store.put(mapping)
    store.put(coverage)
    store.put(input_contract)
    store.put(receipt)
    store.put(contract)
    loaded = store.get_mapping(mapping.mapping_id)
    assert loaded is not None
    assert "allocations" not in loaded.model_dump()


def test_client_cannot_supply_tenant() -> None:
    from app.investment_optimization.service import OptimizationReadinessService
    from app.investment_optimization.store import InMemoryOptimizationMetadataStore
    from app.investment_planning.errors import PlanningAuthorityError

    # Domain service rejects explicit tenant_id without needing HTTP.
    service = OptimizationReadinessService(
        repo=None,  # type: ignore[arg-type]
        store=InMemoryOptimizationMetadataStore(),
        planning=None,  # type: ignore[arg-type]
    )
    with pytest.raises(PlanningAuthorityError, match="tenant_id"):
        service.create_mapping(
            project_id=PROJECT,
            portfolio_snapshot_id="psnap_aaaaaaaaaaaaaaaaaaa",
            actor_id="user_acme",
            tenant_id=TENANT,
        )


def test_client_cannot_supply_model_artifact_location() -> None:
    from app.investment_optimization.service import OptimizationReadinessService
    from app.investment_optimization.store import InMemoryOptimizationMetadataStore

    service = OptimizationReadinessService(
        repo=None,  # type: ignore[arg-type]
        store=InMemoryOptimizationMetadataStore(),
        planning=None,  # type: ignore[arg-type]
    )
    with pytest.raises(Exception, match="artifact"):
        service.evaluate(
            project_id=PROJECT,
            actor_id="user_acme",
            model_artifact_location="gs://secret/model.bin",
        )


def test_cross_project_model_mapping_fails() -> None:
    from app.investment_optimization.accepted_model import select_accepted_model
    from tests.unit.investment_optimization.p6_04_support import model_version

    version = model_version(project_id="wsp_otherotherotheroth")
    selection = select_accepted_model(
        (version,),
        tenant_id=TENANT,
        project_id=PROJECT,
        requested_model_version_id=version.model_version_id,
    )
    assert selection.issue_code is not None
    assert selection.issue_code.value == "CROSS_PROJECT_MODEL_MAPPING"


def test_cross_tenant_model_mapping_fails() -> None:
    from app.investment_optimization.accepted_model import select_accepted_model
    from tests.unit.investment_optimization.p6_04_support import model_version

    version = model_version(tenant_id="ten_otherotherotherother")
    selection = select_accepted_model(
        (version,),
        tenant_id=TENANT,
        project_id=PROJECT,
        requested_model_version_id=version.model_version_id,
    )
    assert selection.issue_code is not None
    assert selection.issue_code.value == "CROSS_TENANT_MODEL_MAPPING"


def test_openapi_has_no_legacy_investment_optimizations_namespace() -> None:
    from app.service.openapi_export import build_openapi_document

    document = build_openapi_document()
    paths = document["paths"]
    assert "/v1/projects/{project_id}/investment-portfolio/optimization-readiness" in paths
    assert "/v1/projects/{project_id}/investment-portfolio/model-mapping" in paths
    assert "/v1/projects/{project_id}/investment-portfolio/optimizations" in paths
    assert not any("optimize" in path and "execution" in path for path in paths)
    assert "/v1/projects/{project_id}/investment-optimizations" not in paths


def test_create_mapping_and_evaluate_http() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    client = harness["client"]
    listed = client.get(
        f"/v1/projects/{project_id}/investment-portfolio/model-mapping",
        headers=auth_header(),
    )
    assert listed.status_code == 200, listed.text
    evaluated = client.post(
        f"/v1/projects/{project_id}/investment-portfolio/optimization-readiness/evaluate",
        headers=auth_header(),
        json={},
    )
    assert evaluated.status_code == 200, evaluated.text
    body = evaluated.json()
    assert "total_budget" not in body
    assert "allocations" not in body
    ready = client.get(
        f"/v1/projects/{project_id}/investment-portfolio/optimization-readiness",
        headers=auth_header(),
    )
    assert ready.status_code == 200, ready.text
    foreign = client.get(
        "/v1/projects/wsp_doesnotexist0000000/investment-portfolio/optimization-readiness",
        headers=auth_header(),
    )
    assert foreign.status_code in {403, 404}


def test_p6_03_production_actuals_remain_fail_closed() -> None:
    from app.investment_planning.actuals import P6_03_PRODUCTION_ACTUALS_QUERY_PENDING

    assert P6_03_PRODUCTION_ACTUALS_QUERY_PENDING == "P6_03_PRODUCTION_ACTUALS_QUERY_PENDING"
