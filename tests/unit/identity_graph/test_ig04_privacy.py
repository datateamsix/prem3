from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.identity_graph.analytics.contracts import (
    AnalyticalSessionSeed,
    UnifiedAnalyticsCompilation,
    UnifiedSessionRow,
)
from app.identity_graph.enums import (
    AnalyticalCompilationPhase,
    AnalyticalCompilationStatus,
    ChannelResolutionMethod,
    MarketResolutionMethod,
    RowResolutionStatus,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.privacy import reject_identity_graph_payload
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_control_plane_payloads_reject_person_keys() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)):
        UnifiedAnalyticsCompilation(
            compilation_id="iga_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            phase=AnalyticalCompilationPhase.READY,
            status=AnalyticalCompilationStatus.READY,
            user_pseudo_id="secret",  # type: ignore[call-arg]
        )
    with pytest.raises((IdentityGraphError, ValidationError)):
        AnalyticalSessionSeed(
            ga4_source_binding_id="igs_aaaaaaaaaaaaaaaaaaaa",
            ga4_property_id="123",
            ga_session_id="1",
            subject_key="hashed",
            session_start_ts="2026-04-01T00:00:00+00:00",
            user_id="person",  # type: ignore[call-arg]
        )


def test_session_row_schema_has_no_person_fields() -> None:
    row = UnifiedSessionRow(
        session_id="abc",
        ga4_property_id="analytics_us",
        ga4_source_binding_id="igs_aaaaaaaaaaaaaaaaaaaa",
        market_status=RowResolutionStatus.UNRESOLVED,
        market_method=MarketResolutionMethod.UNRESOLVED,
        channel_status=RowResolutionStatus.UNRESOLVED,
        channel_method=ChannelResolutionMethod.UNRESOLVED,
        session_start_ts="2026-04-01T00:00:00+00:00",
    )
    dumped = row.model_dump()
    assert "user_pseudo_id" not in dumped
    assert "user_id" not in dumped
    reject_identity_graph_payload(dumped)
