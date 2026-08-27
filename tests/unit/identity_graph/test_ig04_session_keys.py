from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.analytics.keys import journey_id, session_id
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def test_session_key_is_property_scoped(graph) -> None:
    fixture = seed_ready_property_per_market(graph)
    graph.analytical_adapter.seed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        rows=(
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["us_source"].ga4_source_binding_id,
                ga4_property_id="analytics_us",
                ga_session_id="same-session",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
            ),
            AnalyticalSessionSeed(
                ga4_source_binding_id=fixture["ca_source"].ga4_source_binding_id,
                ga4_property_id="analytics_ca",
                ga_session_id="same-session",
                subject_key="sub-a",
                session_start_ts="2026-04-01T00:00:00+00:00",
                source="(direct)",
                medium="(none)",
            ),
        ),
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
    rows = graph.analytical_adapter.read_back_sessions(compiled.compilation_id)
    assert len({row.session_id for row in rows}) == 2
    expected_us = session_id(
        ga4_property_id="analytics_us", subject_key="sub-a", ga_session_id="same-session"
    )
    expected_ca = session_id(
        ga4_property_id="analytics_ca", subject_key="sub-a", ga_session_id="same-session"
    )
    assert {row.session_id for row in rows} == {expected_us, expected_ca}
    journeys = graph.analytical_adapter.read_back_journeys(compiled.compilation_id)
    assert len(journeys) == 1
    assert journeys[0].journey_id == journey_id(
        project_id=PROJECT_ID,
        identity_strategy="PSEUDO_ID_ONLY",
        subject_key="sub-a",
    )
    assert journeys[0].multi_market is True
    assert "MULTI_MARKET_JOURNEY" in journeys[0].issues
