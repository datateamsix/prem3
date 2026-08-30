"""P6-03A production BigQuery actual-spend adapter. No new financial semantics."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.control_plane.entitlements import PlanId
from app.control_plane.models import BigQueryWorkspaceBinding
from app.data_foundation.context import DataFoundationContext
from app.data_foundation.contracts import (
    ContractStructureAssessment,
    DataQualityAssessment,
    MeasurementCoverageAssessment,
    OperationalHealthAssessment,
    PhysicalMetadata,
    ResourceIdentity,
    SourceAssessment,
    SourceBinding,
    SourceContract,
)
from app.data_foundation.enums import ConnectionLifecycle, LocationType, QualityStatus
from app.data_foundation.ids import new_source_id
from app.data_foundation.store import InMemoryDataFoundationStore
from app.integrations.google.adapters import BigQueryTableInfo, FakeBigQueryClient
from app.investment_planning.actuals import (
    DataFoundationActualSpendAdapter,
    TestOnlyActualSpendAdapter,
    query_actuals,
)
from app.investment_planning.bigquery_actuals import (
    QUERY_TEMPLATE_VERSION,
    BigQueryActualSpendAdapter,
    compile_actual_spend_query,
    fiscal_year_date_window,
)
from app.investment_planning.contracts import ActualSpendAllocation
from app.investment_planning.enums import (
    ActualsFreshnessState,
    PortfolioBaselineKind,
    PortfolioCoverageState,
)
from app.investment_planning.errors import (
    ActualsChannelMappingRequiredError,
    ActualsDuplicateGrainError,
    ActualsMarketMappingRequiredError,
    BqAuthorizationFailedError,
    CurrencyReviewRequiredError,
    PeriodMappingRequiredError,
)
from app.investment_planning.ids import new_actuals_source_id
from app.investment_planning.store import InMemoryInvestmentPlanningMetadataStore
from tests.unit.api_support import auth_header
from tests.unit.business_iq.conftest import ready_payload
from tests.unit.google_support import connect_google, google_harness
from tests.unit.investment_planning.test_p6_03_actuals import MARKET_A
from tests.unit.investment_planning.test_p6_03_privacy_http import _approve_plan, _seed_market
from tests.unit.test_prem3_drive_governance import _setup_drive

TENANT = "ten_bbbbbbbbbbbbbbbbbbbb"
PROJECT = "wsp_cccccccccccccccccccc"
BQ_PROJECT = "acme_analytics"
DATASET = "marketing"
TABLE = "spend_daily"
NOW = datetime(2027, 2, 1, tzinfo=UTC)


def _context(**overrides: object) -> DataFoundationContext:
    payload = {
        "tenant_id": TENANT,
        "workspace_id": PROJECT,
        "actor_id": "user_test",
        "source_project_ids": (BQ_PROJECT,),
        "source_dataset_ids": (DATASET,),
        "destination_project_id": BQ_PROJECT,
        "destination_location": "US",
        "google_connection_id": "gconn_aaaaaaaaaaaaaaaaaa",
        "bq_lifecycle": ConnectionLifecycle.DISCOVERY_READY,
    }
    payload.update(overrides)
    return DataFoundationContext(**payload)


def _binding(**overrides: object) -> SourceBinding:
    payload = {
        "source_id": new_source_id(),
        "tenant_id": TENANT,
        "workspace_id": PROJECT,
        "requirement_id": None,
        "provider_id": None,
        "location_type": LocationType.BIGQUERY,
        "resource": ResourceIdentity(
            location_type=LocationType.BIGQUERY,
            project_id=BQ_PROJECT,
            dataset_id=DATASET,
            table_id=TABLE,
        ),
        "contract": SourceContract(
            grain="daily",
            date_field="date",
            currency="USD",
            timezone="UTC",
            required_fields=("date", "market_id", "channel_id", "spend", "currency"),
            schema_fingerprint="fp_schema_actuals",
        ),
        "lifecycle_state": "BOUND",
        "governance_import_ready": True,
        "canonical": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return SourceBinding(**payload)


def _seed_bq(
    client: FakeBigQueryClient,
    *,
    rows: list[dict[str, object]],
    location: str = "US",
    project_id: str = BQ_PROJECT,
    dataset_id: str = DATASET,
    table_id: str = TABLE,
) -> None:
    key_table = BigQueryTableInfo(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        object_type="TABLE",
        schema_fingerprint="date:market_id:channel_id:spend:currency",
        etag="etag-spend",
        last_modified="2027-02-01T00:00:00Z",
        num_bytes=128,
        num_rows=len(rows),
        location=location,
    )
    client.tables[f"{project_id}.{dataset_id}.{table_id}"] = key_table
    client.seed_dataset(project_id=project_id, dataset_id=dataset_id, location=location)
    client.seed_table_rows(
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=table_id,
        columns=["date", "market_id", "channel_id", "spend", "currency"],
        rows=rows,
    )


def _stack(
    *,
    rows: list[dict[str, object]] | None = None,
    binding: SourceBinding | None = None,
    context: DataFoundationContext | None = None,
    assessment: SourceAssessment | None = None,
) -> tuple[DataFoundationActualSpendAdapter, FakeBigQueryClient, SourceBinding]:
    store = InMemoryDataFoundationStore()
    source_binding = binding or _binding()
    store.put_binding(source_binding)
    store.put_physical(
        source_binding.source_id,
        PhysicalMetadata(object_type="TABLE", dataset_location="US", row_count=len(rows or ())),
    )
    if assessment is not None:
        store.put_assessment(
            assessment.model_copy(update={"source_id": source_binding.source_id})
        )
    bq = FakeBigQueryClient()
    _seed_bq(bq, rows=rows or ())
    adapter = DataFoundationActualSpendAdapter(
        store,
        rows=BigQueryActualSpendAdapter(
            store,
            bigquery=bq,
            context=context or _context(),
            access_token="ya29.actuals",
        ),
    )
    return adapter, bq, source_binding


def _row(
    *,
    day: str = "2027-01-15",
    amount: str = "40.00",
    market_id: str = MARKET_A,
    channel_id: str = "search_paid",
    currency: str = "USD",
) -> dict[str, object]:
    return {
        "date": day,
        "market_id": market_id,
        "channel_id": channel_id,
        "spend": amount,
        "currency": currency,
    }


def test_prod_actuals_requires_df_binding() -> None:
    store = InMemoryDataFoundationStore()
    bq = FakeBigQueryClient()
    adapter = DataFoundationActualSpendAdapter(
        store,
        rows=BigQueryActualSpendAdapter(
            store, bigquery=bq, context=_context(), access_token="ya29.actuals"
        ),
    )
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.error_code in {
        "ACTUALS_SOURCE_NOT_CONFIGURED",
        "PRODUCTION_ACTUALS_SOURCE_NOT_READY",
    }
    assert result.allocations == ()


def test_client_cannot_supply_bq_table() -> None:
    compiled = compile_actual_spend_query(
        project_id=BQ_PROJECT,
        dataset_id=DATASET,
        table_id=TABLE,
        date_field="date",
        market_field="market_id",
        channel_field="channel_id",
        spend_field="spend",
        currency_field="currency",
        timezone="UTC",
    )
    assert "evil_table" not in compiled.sql
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
        params={"table": "evil_table", "bq_table": "other.spend", "dataset": "other"},
    )
    assert response.status_code == 200
    assert response.json()["coverage_state"] == "NEITHER"


def test_client_cannot_supply_sql() -> None:
    with pytest.raises(TypeError):
        compile_actual_spend_query(
            project_id=BQ_PROJECT,
            dataset_id=DATASET,
            table_id=TABLE,
            date_field="date",
            market_field="market_id",
            channel_field="channel_id",
            spend_field="spend",
            currency_field="currency",
            timezone="UTC",
            sql="SELECT 1",
        )
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    injected = "SELECT 999 AS spend FROM `evil.spend`"
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
        params={"sql": injected},
    )
    assert response.status_code == 200
    last = getattr(harness["bigquery"], "last_bounded_query", None)
    if last is not None:
        assert injected not in str(last.get("sql"))


def test_cross_project_source_rejected() -> None:
    binding = _binding()
    store = InMemoryDataFoundationStore()
    store.put_binding(binding)
    store.put_physical(
        binding.source_id, PhysicalMetadata(object_type="TABLE", dataset_location="US")
    )
    bq = FakeBigQueryClient()
    _seed_bq(bq, rows=[_row()])
    adapter = DataFoundationActualSpendAdapter(
        store,
        rows=BigQueryActualSpendAdapter(
            store,
            bigquery=bq,
            context=_context(
                source_project_ids=("other_analytics",),
                destination_project_id="other_analytics",
            ),
            access_token="ya29.actuals",
        ),
    )
    source = adapter.resolve_source(tenant_id=TENANT, project_id=PROJECT)
    assert source is not None
    with pytest.raises(BqAuthorizationFailedError):
        adapter.query_allocations(
            source=source,
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_test_adapter_never_used_as_prod() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    actuals = harness["client"].app.state.investment_planning._actuals
    assert not isinstance(actuals, TestOnlyActualSpendAdapter)
    assert isinstance(actuals, DataFoundationActualSpendAdapter)
    assert isinstance(actuals._rows, BigQueryActualSpendAdapter)


def test_bq_rows_normalize_to_actual_spend_allocation() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(amount="12.50")])
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.error_code is None
    assert len(result.allocations) == 1
    row = result.allocations[0]
    assert isinstance(row, ActualSpendAllocation)
    assert row.fiscal_year == 2027
    assert row.quarter == 1
    assert row.market_id == MARKET_A
    assert row.channel_id == "search_paid"
    assert row.amount == Decimal("12.50")
    assert row.missing is False


def test_amount_uses_decimal() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(amount="8.10")])
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert isinstance(result.allocations[0].amount, Decimal)
    assert result.allocations[0].amount == Decimal("8.10")


def test_market_id_canonical() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(market_id="United States")])
    source = adapter.resolve_source(tenant_id=TENANT, project_id=PROJECT)
    assert source is not None
    with pytest.raises(ActualsMarketMappingRequiredError):
        adapter.query_allocations(
            source=source,
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_channel_id_canonical() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(channel_id="Paid Search")])
    source = adapter.resolve_source(tenant_id=TENANT, project_id=PROJECT)
    assert source is not None
    with pytest.raises(ActualsChannelMappingRequiredError):
        adapter.query_allocations(
            source=source,
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_duplicate_grain_rejected() -> None:
    adapter, _bq, _binding = _stack(
        rows=[_row(amount="10.00"), _row(amount="5.00")],
    )
    source = adapter.resolve_source(tenant_id=TENANT, project_id=PROJECT)
    assert source is not None
    with pytest.raises(ActualsDuplicateGrainError):
        adapter.query_allocations(
            source=source,
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_zero_distinct_from_missing() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(amount="0.00")])
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.allocations[0].missing is False
    assert result.allocations[0].amount == Decimal("0.00")
    empty_adapter, _bq2, _binding2 = _stack(rows=[])
    empty = query_actuals(
        empty_adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert empty.error_code is None
    assert empty.allocations == ()


def test_daily_to_quarter_period_mapping() -> None:
    adapter, bq, _binding = _stack(
        rows=[_row(day="2027-01-15", amount="10.00"), _row(day="2027-02-01", amount="5.00")]
    )
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.allocations[0].quarter == 1
    assert result.allocations[0].amount == Decimal("15.00")
    start, end = fiscal_year_date_window(2027, 1)
    assert start == date(2027, 1, 1)
    assert end == date(2027, 12, 31)
    assert bq.last_bounded_query is not None
    assert bq.last_bounded_query["parameters"]["start_date"] == "2027-01-01"
    assert bq.last_bounded_query["parameters"]["end_date"] == "2027-12-31"
    assert "@start_date" in bq.last_bounded_query["sql"]
    assert "GROUP BY" in bq.last_bounded_query["sql"]


def test_timezone_policy_pinned() -> None:
    compiled = compile_actual_spend_query(
        project_id=BQ_PROJECT,
        dataset_id=DATASET,
        table_id=TABLE,
        date_field="date",
        market_field="market_id",
        channel_field="channel_id",
        spend_field="spend",
        currency_field="currency",
        timezone="America/New_York",
    )
    assert compiled.timezone == "America/New_York"
    assert compiled.query_template_version == QUERY_TEMPLATE_VERSION
    adapter, bq, _binding = _stack(rows=[_row()])
    query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert bq.last_bounded_query is not None
    assert bq.last_bounded_query["parameters"]["timezone"] == "UTC"


def test_missing_fiscal_policy_fails() -> None:
    adapter, _bq, _binding = _stack(rows=[_row()])
    source = adapter.resolve_source(tenant_id=TENANT, project_id=PROJECT)
    assert source is not None
    with pytest.raises(PeriodMappingRequiredError):
        adapter.query_allocations(
            source=source,
            fiscal_year=None,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def test_currency_match() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(currency="USD", amount="3.00")])
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.allocations[0].currency == "USD"


def test_currency_mismatch_review_required() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(currency="EUR")])
    source = adapter.resolve_source(tenant_id=TENANT, project_id=PROJECT)
    assert source is not None
    with pytest.raises(CurrencyReviewRequiredError):
        adapter.query_allocations(
            source=source,
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )


def _install_prod_source(
    harness,
    *,
    market_id: str,
    amount: str = "40.00",
    stale: bool = False,
) -> SourceBinding:
    connection_id = connect_google(harness, capabilities=["BIGQUERY_READ"])
    workspace_id = harness["workspace"]["workspace_id"]
    tenant_id = harness["tenant"].tenant_id
    now = datetime(2027, 2, 1, tzinfo=UTC)
    harness["repo"].put_bigquery_binding(
        BigQueryWorkspaceBinding(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            connection_id=connection_id,
            source_project_ids=(BQ_PROJECT,),
            source_dataset_ids=(DATASET,),
            destination_project_id=BQ_PROJECT,
            location="US",
            read_verified=True,
            write_verified=False,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            last_verified_at=now,
        )
    )
    store = harness["client"].app.state.data_foundation_store
    binding = SourceBinding(
        source_id=new_source_id(),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        requirement_id=None,
        provider_id=None,
        location_type=LocationType.BIGQUERY,
        resource=ResourceIdentity(
            location_type=LocationType.BIGQUERY,
            project_id=BQ_PROJECT,
            dataset_id=DATASET,
            table_id=TABLE,
        ),
        contract=SourceContract(
            grain="daily",
            date_field="date",
            currency="USD",
            timezone="UTC",
            required_fields=("date", "market_id", "channel_id", "spend", "currency"),
            schema_fingerprint="fp_http_actuals",
        ),
        lifecycle_state="BOUND",
        governance_import_ready=True,
        canonical=True,
        created_at=now,
        updated_at=now,
    )
    store.put_binding(binding)
    store.put_physical(
        binding.source_id, PhysicalMetadata(object_type="TABLE", dataset_location="US")
    )
    if stale:
        store.put_assessment(
            SourceAssessment(
                source_id=binding.source_id,
                registry_version="v1",
                operational=OperationalHealthAssessment(
                    access_works=True,
                    expected_cadence="daily",
                    authorization_state=ConnectionLifecycle.DISCOVERY_READY,
                    freshness_known=True,
                    status=QualityStatus.BLOCKER,
                ),
                contract=ContractStructureAssessment(
                    required_fields_present=True,
                    schema_fingerprint="fp_http_actuals",
                    currency_known=True,
                    timezone_known=True,
                    status=QualityStatus.PASS,
                ),
                quality=DataQualityAssessment(checks=(), status=QualityStatus.PASS),
                coverage=MeasurementCoverageAssessment(status=QualityStatus.PASS),
                overall_status=QualityStatus.BLOCKER,
                assessed_at=now,
            )
        )
    _seed_bq(
        harness["bigquery"],
        rows=[_row(market_id=market_id, amount=amount)],
    )
    return binding


def test_plan_plus_prod_actuals_is_plan_and_actuals() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    _connection_id, binding = _setup_drive(harness)
    project_id = harness["workspace"]["workspace_id"]
    market_id = _seed_market(harness, project_id=project_id)
    _approve_plan(harness, project_id=project_id, binding=binding, market_id=market_id)
    _install_prod_source(harness, market_id=market_id, amount="40.00")
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["coverage_state"] == PortfolioCoverageState.PLAN_AND_ACTUALS.value
    assert body["baseline_kind"] == PortfolioBaselineKind.APPROVED_PLAN.value
    kinds = {item["kind"]: item for item in body["summary"]}
    assert kinds["ACTUAL"]["value"] == "40.00"


def test_prod_actuals_only_is_actuals_only() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    market_id = _seed_market(harness, project_id=project_id)
    profile = harness["client"].post(
        f"/v1/workspaces/{project_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    assert profile.status_code == 200, profile.text
    _install_prod_source(harness, market_id=market_id, amount="40.00")
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
        params={"fiscal_year": 2027},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["coverage_state"] == PortfolioCoverageState.ACTUALS_ONLY.value
    assert body["baseline_kind"] == PortfolioBaselineKind.ACTUAL_YTD.value


def test_unavailable_prod_source_does_not_fabricate_actuals() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    _connection_id, binding = _setup_drive(harness)
    project_id = harness["workspace"]["workspace_id"]
    market_id = _seed_market(harness, project_id=project_id)
    _approve_plan(harness, project_id=project_id, binding=binding, market_id=market_id)
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["coverage_state"] == PortfolioCoverageState.PLAN_ONLY.value
    kinds = {item["kind"]: item for item in body["summary"]}
    assert "ACTUAL" not in kinds or kinds["ACTUAL"]["missing"] is True
    if "ACTUAL" in kinds:
        assert kinds["ACTUAL"]["value"] is None
    types = {item["observation_type"] for item in body.get("observations") or []}
    assert "MISSING_ACTUALS_SOURCE" in types


def test_stale_source_not_current_actuals() -> None:
    adapter, _bq, _binding = _stack(
        rows=[_row(amount="9.00")],
        assessment=SourceAssessment(
            source_id="dfsrc_staleaaaaaaaaaaaa",
            registry_version="v1",
            operational=OperationalHealthAssessment(
                access_works=True,
                expected_cadence="daily",
                authorization_state=ConnectionLifecycle.DISCOVERY_READY,
                freshness_known=True,
                status=QualityStatus.BLOCKER,
            ),
            contract=ContractStructureAssessment(
                required_fields_present=True,
                schema_fingerprint="fp",
                currency_known=True,
                timezone_known=True,
                status=QualityStatus.PASS,
            ),
            quality=DataQualityAssessment(checks=(), status=QualityStatus.PASS),
            coverage=MeasurementCoverageAssessment(status=QualityStatus.PASS),
            overall_status=QualityStatus.BLOCKER,
            assessed_at=NOW,
        ),
    )
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.error_code is None
    assert result.freshness is ActualsFreshnessState.STALE
    assert result.source is not None
    assert result.source.status.value == "STALE"
    assert result.allocations[0].amount == Decimal("9.00")


def test_query_receipt_has_no_amounts() -> None:
    adapter, _bq, _binding = _stack(rows=[_row(amount="77.00")])
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    receipt = result.query_receipt
    assert receipt is not None
    dumped = receipt.model_dump()
    assert "amount" not in dumped
    assert "spend" not in dumped
    assert "allocations" not in dumped
    assert "77.00" not in str(dumped)
    assert receipt.row_count == 1
    assert receipt.query_template_version == QUERY_TEMPLATE_VERSION
    store = InMemoryInvestmentPlanningMetadataStore()
    stored = store.put(receipt)
    assert stored.query_receipt_id == receipt.query_receipt_id


def test_firestore_has_no_actual_rows() -> None:
    store = InMemoryInvestmentPlanningMetadataStore()
    with pytest.raises(Exception, match="CUSTOMER_AMOUNT_TRANSIENT"):
        store.put(
            ActualSpendAllocation(
                fiscal_year=2027,
                quarter=1,
                market_id=MARKET_A,
                channel_id="search_paid",
                amount=Decimal("10.00"),
                currency="USD",
                source_ref=new_actuals_source_id(),
                missing=False,
            )
        )


def test_logs_have_no_spend_values(caplog: pytest.LogCaptureFixture) -> None:
    adapter, _bq, _binding = _stack(rows=[_row(amount="8888.88")])
    with caplog.at_level(logging.DEBUG, logger="prem3.investment_planning.bigquery_actuals"):
        query_actuals(
            adapter,
            tenant_id=TENANT,
            project_id=PROJECT,
            fiscal_year=2027,
            fiscal_start_month=1,
            known_market_ids={MARKET_A},
            expected_currency="USD",
        )
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "8888.88" not in joined
    assert "8888" not in joined


def test_portfolio_amount_response_private_no_store() -> None:
    harness = google_harness(plan_id=PlanId.PORTFOLIO)
    project_id = harness["workspace"]["workspace_id"]
    market_id = _seed_market(harness, project_id=project_id)
    profile = harness["client"].post(
        f"/v1/workspaces/{project_id}/business-iq/profile",
        headers=auth_header(),
        json=ready_payload(),
    )
    assert profile.status_code == 200, profile.text
    _install_prod_source(harness, market_id=market_id, amount="40.00")
    response = harness["client"].get(
        f"/v1/projects/{project_id}/investment-portfolio",
        headers=auth_header(),
        params={"fiscal_year": 2027},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("cache-control") == "private, no-store"
    assert response.headers.get("pragma") == "no-cache"


def test_compile_rejects_unsafe_identifiers() -> None:
    with pytest.raises(ValueError):
        compile_actual_spend_query(
            project_id=BQ_PROJECT,
            dataset_id="marketing; DROP",
            table_id=TABLE,
            date_field="date",
            market_field="market_id",
            channel_field="channel_id",
            spend_field="spend",
            currency_field="currency",
            timezone="UTC",
        )


def test_source_not_ready_without_governance_flag() -> None:
    adapter, _bq, _source = _stack(
        rows=[_row()],
        binding=_binding(governance_import_ready=False),
    )
    result = query_actuals(
        adapter,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        fiscal_start_month=1,
        known_market_ids={MARKET_A},
        expected_currency="USD",
    )
    assert result.error_code in {
        "ACTUALS_SOURCE_NOT_CONFIGURED",
        "PRODUCTION_ACTUALS_SOURCE_NOT_READY",
    }
    assert result.allocations == ()
