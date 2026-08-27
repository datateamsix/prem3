from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.identity_graph.contracts import (
    CanonicalMarket,
    GA4PropertySourceBinding,
    GA4SourceTopology,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.privacy import reject_identity_graph_payload
from app.identity_graph.store import InMemoryIdentityGraphStore
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_market_graph_rejects_person_identity_fields() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)) as exc:
        CanonicalMarket(
            market_id="mkt_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Leak",
            user_id="person-1",  # type: ignore[call-arg]
        )
    assert "PERSON_IDENTITY_FORBIDDEN" in str(exc.value) or "person-identity" in str(
        exc.value
    )


def test_ga4_topology_does_not_persist_event_rows() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)) as exc:
        GA4SourceTopology(
            topology_id="igto_aaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            topology_kind="SINGLE_MASTER_PROPERTY",
            ga4_events=[{"event_name": "session_start"}],  # type: ignore[call-arg]
        )
    assert "EVENT_ROWS_FORBIDDEN" in str(exc.value) or "event-scale" in str(exc.value)
    assert not hasattr(InMemoryIdentityGraphStore, "put_events")


def test_source_metadata_contains_no_budget_values() -> None:
    fields = GA4PropertySourceBinding.model_fields
    assert "budget" not in fields
    assert "planned_spend" not in fields
    assert "actual_spend" not in fields
    with pytest.raises(IdentityGraphError) as exc:
        reject_identity_graph_payload(
            {
                "ga4_property_id": "123",
                "bq_project_id": "p",
                "bq_dataset_id": "analytics_123",
                "planned_spend": 5000,
            }
        )
    assert exc.value.code == "BUDGET_FORBIDDEN"


def test_no_audience_membership_in_identity_graph() -> None:
    with pytest.raises(IdentityGraphError) as exc:
        reject_identity_graph_payload(
            {"market_id": "mkt_aaaaaaaaaaaaaaaaaaaa", "audience_members": ["user_1"]}
        )
    assert exc.value.code == "PERSON_IDENTITY_FORBIDDEN"
    assert "audience_members" not in CanonicalMarket.model_fields
    assert "membership" not in CanonicalMarket.model_fields
