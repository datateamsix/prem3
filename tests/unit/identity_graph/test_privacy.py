from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.identity_graph.contracts import CanonicalCampaign
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.privacy import reject_identity_graph_payload
from app.identity_graph.store import (
    FIRESTORE_GRAPH_COLLECTION,
    InMemoryIdentityGraphStore,
    firestore_graph_path,
)
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_identity_graph_rejects_person_identity_fields() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)) as exc:
        CanonicalCampaign(
            campaign_id="cmp_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Leak",
            email="person@example.com",  # type: ignore[call-arg]
        )
    assert "PERSON_IDENTITY_FORBIDDEN" in str(exc.value) or "person-identity" in str(exc.value)


def test_identity_graph_contains_no_budget_values() -> None:
    with pytest.raises(IdentityGraphError) as exc:
        reject_identity_graph_payload({"name": "Spend", "planned_spend": 1000})
    assert exc.value.code == "BUDGET_FORBIDDEN"
    fields = CanonicalCampaign.model_fields
    assert "budget" not in fields
    assert "planned_spend" not in fields
    assert "actual_spend" not in fields
    assert "recommended_spend" not in fields


def test_identity_graph_contains_no_event_rows() -> None:
    with pytest.raises(IdentityGraphError) as exc:
        reject_identity_graph_payload({"ga4_events": [{"event_name": "page_view"}]})
    assert exc.value.code == "EVENT_ROWS_FORBIDDEN"
    assert not hasattr(InMemoryIdentityGraphStore, "put_events")
    assert FIRESTORE_GRAPH_COLLECTION == "identity_graph"
    assert "events" not in firestore_graph_path(
        tenant_id=TENANT_ID, workspace_id=PROJECT_ID
    )


def test_campaign_tracking_id_is_non_secret(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Public", actor_id="user-a"
    )
    campaign_id = created.campaign.campaign_id
    assert "@" not in campaign_id
    assert not campaign_id.startswith("sk_")
    assert created.instructions.utm_id == campaign_id
    assert created.tracking.parameter_value == campaign_id
