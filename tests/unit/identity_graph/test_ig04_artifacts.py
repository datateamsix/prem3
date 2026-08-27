from __future__ import annotations

from app.identity_graph.analytics.contracts import AnalyticalSessionSeed
from app.identity_graph.enums import AnalyticalArtifactKind, AnalyticalCompilationStatus
from tests.unit.identity_graph.conftest import (
    PROJECT_ID,
    TENANT_ID,
    seed_ready_property_per_market,
)


def test_artifacts_are_compilation_scoped_and_idempotent(graph) -> None:
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
        ),
    )
    first = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    second = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-04-01",
        period_end="2026-04-30",
    )
    assert first.status == AnalyticalCompilationStatus.READY
    assert second.compilation_id == first.compilation_id
    assert second.fingerprint == first.fingerprint
    names = {item.table_name for item in first.artifact_refs}
    assert f"ga4_sessions_unified_{first.compilation_id}" in names
    assert f"mta_session_touchpoints_{first.compilation_id}" in names
    assert f"mta_journeys_{first.compilation_id}" in names
    assert any(item.kind == AnalyticalArtifactKind.CURRENT_POINTER for item in first.artifact_refs)
    assert all(item.dataset_id == "prem3_modeling" for item in first.artifact_refs)
    blocked = graph.compile_analytics(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        selected_source_binding_ids=(fixture["us_source"].ga4_source_binding_id,),
        period_start="2026-05-01",
        period_end="2026-05-31",
    )
    assert blocked.compilation_id != first.compilation_id
