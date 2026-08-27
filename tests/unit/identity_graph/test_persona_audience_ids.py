from __future__ import annotations

import re

import pytest

from app.identity_graph.contracts import CanonicalAudience, CanonicalPersona
from app.identity_graph.enums import AudienceSourceKind, AudienceType
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID

_URL_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")


def test_persona_id_is_server_generated(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="High intent", actor_id="user-a"
    )
    assert persona.persona_id.startswith("per_")
    assert persona.persona_id != "High intent"
    assert _URL_SAFE.fullmatch(persona.persona_id)


def test_audience_id_is_server_generated(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Site visitors",
        actor_id="user-a",
        audience_type=AudienceType.SITE_BEHAVIOR,
        source_kind=AudienceSourceKind.ANALYTICS_DEFINED,
    )
    assert audience.audience_id.startswith("aud_")
    assert "site" not in audience.audience_id.lower()
    assert _URL_SAFE.fullmatch(audience.audience_id)


def test_persona_id_not_derived_from_name(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="summer_sale_buyer",
        actor_id="user-a",
    )
    assert "summer" not in persona.persona_id.lower()
    assert "sale" not in persona.persona_id.lower()
    assert "buyer" not in persona.persona_id.lower()


def test_persona_id_never_reused(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="One", actor_id="user-a"
    )
    clone = CanonicalPersona(
        persona_id=persona.persona_id,
        tenant_id=TENANT_ID,
        project_id="wsp_otherproject0000001",
        name="Two",
        created_by="user-a",
    )
    with pytest.raises(IdentityGraphError, match="cannot be reused") as exc:
        graph.store.put_persona(clone)
    assert exc.value.code == "ID_REUSED"


def test_audience_id_never_reused(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="One",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
    )
    clone = CanonicalAudience(
        audience_id=audience.audience_id,
        tenant_id=TENANT_ID,
        project_id="wsp_otherproject0000001",
        name="Two",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
        created_by="user-a",
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.store.put_audience(clone)
    assert exc.value.code == "ID_REUSED"


def test_same_name_personas_have_distinct_ids(graph) -> None:
    first = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    second = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Always On", actor_id="user-a"
    )
    assert first.persona_id != second.persona_id


def test_persona_and_audience_ids_are_stable_across_rename(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Original", actor_id="user-a"
    )
    updated = graph.update_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        persona_id=persona.persona_id,
        updates={"name": "Renamed"},
    )
    assert updated.persona_id == persona.persona_id
    assert updated.fingerprint != persona.fingerprint
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Original audience",
        actor_id="user-a",
        audience_type=AudienceType.INTEREST,
        source_kind=AudienceSourceKind.PREM3_DEFINED,
    )
    renamed = graph.update_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        updates={"name": "Renamed audience"},
    )
    assert renamed.audience_id == audience.audience_id
    assert renamed.fingerprint != audience.fingerprint
