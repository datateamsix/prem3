from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.enums import (
    AnalyticalCompilationStatus,
    GA4TopologyReadinessState,
    UnifiedAnalyticsReadinessState,
)
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def _seed(source, *, ga_session_id="1", subject="sub-a", property_id="analytics_us"):
    return AnalyticalSessionSeed(
        ga4_source_binding_id=source.ga4_source_binding_id,
        ga4_property_id=property_id,
        ga_session_id=ga_session_id,
        subject_key=subject,
        session_start_ts="2026-04-01T00:00:00+00:00",
        source="google",
        medium="cpc",
    )


def test_compile_requires_ga4_topology_ready(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    graph.store.receipts[(TENANT_ID, PROJECT_ID)] = graph.store.get_topology_receipt(
        tenant_id=TENANT_ID, project_id=PROJECT_ID
    ).model_copy(update={"state": GA4TopologyReadinessState.GA4_TOPOLOGY_INCOMPLETE})
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(_seed(fixture["us_source"]),),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert compiled.status == AnalyticalCompilationStatus.BLOCKED
    assert "GA4_TOPOLOGY_NOT_READY" in compiled.issues


def test_compile_pins_topology_id_and_fingerprint(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    topology = graph.store.get_topology(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(_seed(fixture["us_source"]),),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(
            fixture["us_source"].ga4_source_binding_id,
            fixture["ca_source"].ga4_source_binding_id,
        ),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert compiled.topology_id == topology.topology_id
    assert compiled.topology_fingerprint == topology.fingerprint
    assert compiled.status == AnalyticalCompilationStatus.READY
    assert graph.analytics_readiness(
        tenant_id=TENANT_ID, project_id=PROJECT_ID
    ).state == UnifiedAnalyticsReadinessState.READY
