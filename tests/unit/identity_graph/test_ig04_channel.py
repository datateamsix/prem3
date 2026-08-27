from __future__ import annotations

from app.identity_graph.analytics.contracts import (
    AnalyticalSessionSeed,
    ApprovedSourceMediumBinding,
)
from app.identity_graph.enums import (
    BindingStatus,
    ChannelResolutionMethod,
    RowResolutionStatus,
)
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    REGISTRY_CHANNEL_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def test_exact_source_medium_binding_resolves_registry_channel(graph) -> None:
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
                source="google",
                medium="cpc",
                provider_id="google_ads",
            ),
        ),
    )
    compiled = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
        approved_source_medium_bindings=(
            ApprovedSourceMediumBinding(
                source="google",
                medium="cpc",
                channel_id=REGISTRY_CHANNEL_ID,
                status=BindingStatus.APPROVED,
            ),
        ),
    )
    session = graph.analytical_adapter.read_back_sessions(compiled.compilation_id)[0]
    assert session.channel_id == REGISTRY_CHANNEL_ID
    assert session.channel_family_id == "search"
    assert session.channel_method == ChannelResolutionMethod.EXACT_SOURCE_MEDIUM_BINDING
    assert session.channel_status == RowResolutionStatus.RESOLVED


def test_direct_is_preserved_and_unknown_source_medium_unresolved(graph) -> None:
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
            ),
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="2",
                subject_key="sub-b",
                session_start_ts="2026-04-01T01:00:00+00:00",
                source="mystery-network",
                medium="mystery-medium",
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
    rows = graph.analytical_adapter.read_back_sessions(compiled.compilation_id)
    direct = next(row for row in rows if row.channel_id == "direct")
    unknown = next(row for row in rows if row.channel_id is None)
    assert direct.channel_method == ChannelResolutionMethod.DIRECT_PRESERVED
    assert unknown.channel_status == RowResolutionStatus.UNRESOLVED
    assert unknown.channel_method == ChannelResolutionMethod.UNRESOLVED
