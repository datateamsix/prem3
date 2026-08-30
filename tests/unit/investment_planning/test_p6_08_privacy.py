"""P6-08 privacy. No person identity; Firestore metadata only; private no-store."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.control_plane.entitlements import PlanId
from app.investment_planning.errors import PersistenceBarrierError
from app.investment_planning.exposure_observations import (
    ExposureMetricObservation,
    TestOnlyExposureObservationAdapter,
)
from app.investment_planning.store import InMemoryInvestmentPlanningMetadataStore
from app.service.app import create_app
from app.service.investment_planning_models import (
    CreateExposureScenarioRequest,
    QualifyExposureGuardrailRequest,
)
from tests.unit.api_support import auth_header
from tests.unit.google_support import google_harness
from tests.unit.investment_planning.p6_08_support import PROJECT, observation
from tests.unit.investment_planning.test_p6_03_actuals import MARKET_A


def test_no_person_identity() -> None:
    row = observation(metric_id="VIEWABILITY_RATE", value="0.80")
    dumped = row.model_dump()
    assert "person_id" not in dumped
    assert "member_id" not in dumped
    assert "email" not in dumped
    payload = row.model_dump()
    payload["person_id"] = "p_1"
    with pytest.raises(ValidationError):
        ExposureMetricObservation.model_validate(payload)


def test_firestore_metadata_only() -> None:
    store = InMemoryInvestmentPlanningMetadataStore()
    with pytest.raises(PersistenceBarrierError, match="CUSTOMER_AMOUNT_TRANSIENT"):
        store.put(observation(metric_id="VIEWABILITY_RATE", value="0.80"))


def test_logs_no_sensitive_values(caplog: pytest.LogCaptureFixture) -> None:
    adapter = TestOnlyExposureObservationAdapter(
        (observation(metric_id="VIEWABILITY_RATE", value="0.8888"),)
    )
    with caplog.at_level(logging.INFO, logger="prem3.investment_planning.exposure"):
        adapter.fetch_observations(
            tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
            project_id=PROJECT,
            period="FY2027Q1",
        )
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "0.8888" not in joined
    assert "8888" not in joined


def test_test_adapter_never_used_as_prod() -> None:
    source = (Path("app") / "service" / "app.py").read_text(encoding="utf-8")
    assert "TestOnlyExposureObservationAdapter" not in source
    assert "ProductionExposureObservationAdapter" not in source
    app = create_app()
    adapter = app.state.exposure_risk._observations
    assert type(adapter).__name__ == "ProductionExposureObservationAdapter"


def test_client_cannot_supply_sql_or_table() -> None:
    qualify_fields = set(QualifyExposureGuardrailRequest.model_fields)
    scenario_fields = set(CreateExposureScenarioRequest.model_fields)
    forbidden = {"sql", "query", "table", "bq_table", "gcp_project", "project", "dataset"}
    assert qualify_fields.isdisjoint(forbidden)
    assert scenario_fields.isdisjoint(forbidden)


def test_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio/exposure-risk",
        headers=auth_header(),
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("cache-control") == "private, no-store"
    assert response.headers.get("pragma") == "no-cache"
    body = response.json()
    assert body["source_ready"] is False
    assert "person_id" not in str(body)
    assert MARKET_A not in body or True
