from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.enums import (
    AudienceSourceKind,
    AudienceType,
    RowResolutionStatus,
)
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def test_audience_id_only_when_external_binding_matches(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="CRM buyers",
        actor_id="user-a",
        audience_type=AudienceType.CRM_SEGMENT,
        source_kind=AudienceSourceKind.CRM_DEFINED,
    )
    binding = graph.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="google_ads",
        external_audience_id="ext-aud-1",
        actor_id="user-a",
    )
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
                audience_provider_id="google_ads",
                audience_external_id="ext-aud-1",
            ),
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="2",
                subject_key="sub-b",
                session_start_ts="2026-04-01T01:00:00+00:00",
                source="(direct)",
                medium="(none)",
                audience_provider_id="google_ads",
                audience_external_id="unknown-aud",
            ),
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="3",
                subject_key="sub-c",
                session_start_ts="2026-04-01T02:00:00+00:00",
                source="(direct)",
                medium="(none)",
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
    matched = next(row for row in rows if row.audience_id == audience.audience_id)
    unknown = next(row for row in rows if row.audience_status == RowResolutionStatus.UNRESOLVED)
    absent = next(row for row in rows if row.audience_status == RowResolutionStatus.NOT_APPLICABLE)
    assert matched.audience_id == binding.audience_id
    assert unknown.audience_id is None
    assert absent.audience_id is None
