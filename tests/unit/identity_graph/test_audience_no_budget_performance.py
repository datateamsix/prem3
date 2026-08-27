from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.identity_graph.contracts import CanonicalAudience, CanonicalPersona
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.privacy import reject_identity_graph_payload
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_persona_and_audience_have_no_budget_or_performance_fields() -> None:
    for fields in (CanonicalPersona.model_fields, CanonicalAudience.model_fields):
        assert "budget" not in fields
        assert "planned_spend" not in fields
        assert "impressions" not in fields
        assert "estimated_size" not in fields
        assert "match_rate" not in fields
        assert "member_count" not in fields
        assert "reach" not in fields
        assert "needs_summary" not in fields


def test_identity_docs_reject_size_and_match_rate() -> None:
    with pytest.raises(IdentityGraphError) as exc:
        reject_identity_graph_payload(
            {"audience_id": "aud_aaaaaaaaaaaaaaaaaaaa", "estimated_size": 12, "match_rate": 0.4}
        )
    assert exc.value.code == "PERFORMANCE_FORBIDDEN"


def test_research_authoring_fields_are_not_persona_authority() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)):
        CanonicalPersona(
            persona_id="per_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Invented prose",
            needs_summary="would invent BIQ-adjacent authority",  # type: ignore[call-arg]
        )
