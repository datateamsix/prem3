from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.identity_graph.contracts import CanonicalAudience, CanonicalPersona
from app.identity_graph.enums import AudienceSourceKind, AudienceType
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.privacy import reject_identity_graph_payload
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_persona_and_audience_reject_person_identity_fields() -> None:
    with pytest.raises((IdentityGraphError, ValidationError)) as exc:
        CanonicalPersona(
            persona_id="per_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Leak",
            email="syn_contact_1",  # type: ignore[call-arg]
        )
    assert "PERSON_IDENTITY_FORBIDDEN" in str(exc.value) or "person-identity" in str(exc.value)
    with pytest.raises((IdentityGraphError, ValidationError)) as second:
        CanonicalAudience(
            audience_id="aud_aaaaaaaaaaaaaaaaaaaa",
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Leak",
            audience_type=AudienceType.CUSTOMER_LIST,
            source_kind=AudienceSourceKind.CRM_DEFINED,
            member_list=["syn_member_1"],  # type: ignore[call-arg]
        )
    assert "PERSON_IDENTITY_FORBIDDEN" in str(second.value) or "person-identity" in str(
        second.value
    )


def test_customer_list_type_does_not_store_members() -> None:
    fields = CanonicalAudience.model_fields
    assert "member_list" not in fields
    assert "hashed_member_list" not in fields
    assert "membership_snapshot" not in fields
    assert "audience_members" not in fields


def test_logs_do_not_emit_rejected_person_identifiers() -> None:
    with pytest.raises(IdentityGraphError) as exc:
        reject_identity_graph_payload(
            {
                "email": "syn_contact_not_a_person",
                "member_list": ["syn_member_1"],
                "idfa": "syn_idfa_1",
                "gaid": "syn_gaid_1",
            }
        )
    message = str(exc.value)
    assert exc.value.code == "PERSON_IDENTITY_FORBIDDEN"
    assert "syn_contact_not_a_person" not in message
    assert "syn_member_1" not in message
    assert "syn_idfa_1" not in message
    assert "syn_gaid_1" not in message
    assert "email" in message
    assert "member_list" in message
