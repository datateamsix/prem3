from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.enums import (
    AnalyticalCompilationStatus,
    MarketResolutionMethod,
    RowResolutionStatus,
)
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def test_property_bound_market_resolves(graph) -> None:
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
                geo_country="CA",
            ),
        ),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert compiled.status == AnalyticalCompilationStatus.READY
    session = graph.analytical_adapter.read_back_sessions(compiled.compilation_id)[0]
    assert session.market_id == fixture["us_market"].market_id
    assert session.market_method == MarketResolutionMethod.PROPERTY_BOUND
    assert session.market_status == RowResolutionStatus.RESOLVED
    assert session.market_id != "CA"


def test_geo_country_is_not_implicit_market(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    multi = graph.upsert_ga4_source(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        ga4_property_id="analytics_multi",
        bq_project_id="modelready-m3",
        bq_dataset_id="analytics_multi",
        bq_location="US",
        declared_market_ids=(fixture["us_market"].market_id, fixture["ca_market"].market_id),
    )
    graph.upsert_topology(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        topology_kind=graph.store.get_topology(
            tenant_id=TENANT_ID, project_id=PROJECT_ID
        ).topology_kind,
        source_binding_ids=(multi.ga4_source_binding_id,),
        overlap_policy=graph.store.get_topology(
            tenant_id=TENANT_ID, project_id=PROJECT_ID
        ).overlap_policy,
        market_resolution_policy_id=fixture["policy"].policy_id,
    )
    graph.validate_ga4_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=multi.ga4_source_binding_id,
                ga4_property_id="analytics_multi",
                ga_session_id="1",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                geo_country="US",
                source="(direct)",
                medium="(none)",
            ),
        ),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(multi.ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    session = graph.analytical_adapter.read_back_sessions(compiled.compilation_id)[0]
    assert session.market_id is None
    assert session.market_status == RowResolutionStatus.UNRESOLVED
    assert "GEO_COUNTRY_NOT_IMPLICIT_MARKET" in session.issues
