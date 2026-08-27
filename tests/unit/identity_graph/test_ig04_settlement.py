from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.enums import (
    AnalyticalCompilationStatus,
    SettlementCompileStatus,
)
from app.modeling.mta.contracts import GA4SettlementPolicy
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def test_intraday_cannot_mix_into_daily_settled(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="1",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
                table_kind="events_intraday",
            ),
        ),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
    )
    assert compiled.status == AnalyticalCompilationStatus.BLOCKED
    receipt = graph.analytics_readiness(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert receipt.settlement_status == SettlementCompileStatus.INTRADAY_MIXED
    assert "INTRADAY_MIXED_INTO_SETTLED" in compiled.issues


def test_preview_intraday_is_explicit_and_not_ready(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="1",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
                table_kind="events_intraday",
            ),
        ),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
        settlement_policy=GA4SettlementPolicy.PREVIEW_INTRADAY,
    )
    assert compiled.status == AnalyticalCompilationStatus.REVIEW_REQUIRED
    assert "PREVIEW_INTRADAY_NOT_FINAL" in compiled.issues
    receipt = graph.analytics_readiness(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    assert receipt.settlement_status == SettlementCompileStatus.PREVIEW_INTRADAY
