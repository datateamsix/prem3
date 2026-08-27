from __future__ import annotations

import pytest

from app.identity_graph.enums import AudienceSourceKind, AudienceStatus, AudienceType, PersonaStatus
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_persona_default_status_is_draft(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Draft", actor_id="user-a"
    )
    assert persona.status == PersonaStatus.DRAFT


def test_persona_lifecycle_transitions(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Life", actor_id="user-a"
    )
    active = graph.update_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        persona_id=persona.persona_id,
        updates={"status": PersonaStatus.ACTIVE},
    )
    inactive = graph.update_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        persona_id=persona.persona_id,
        updates={"status": PersonaStatus.INACTIVE},
    )
    archived = graph.archive_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
    )
    assert active.status == PersonaStatus.ACTIVE
    assert inactive.status == PersonaStatus.INACTIVE
    assert archived.status == PersonaStatus.ARCHIVED
    assert archived.persona_id == persona.persona_id


def test_invalid_persona_transition_rejected(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Jump", actor_id="user-a"
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.update_persona(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            persona_id=persona.persona_id,
            updates={"status": PersonaStatus.INACTIVE},
        )
    assert exc.value.code == "STATUS_TRANSITION"


def test_referenced_persona_not_hard_deleted(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Used", actor_id="user-a"
    )
    graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Uses persona",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
        persona_ids=(persona.persona_id,),
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.delete_persona(
            tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
        )
    assert exc.value.code == "PERSONA_REFERENCED"


def test_unreferenced_draft_persona_can_be_hard_deleted(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Disposable", actor_id="user-a"
    )
    graph.delete_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.get_persona(
            tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
        )
    assert exc.value.code == "UNKNOWN_PERSONA"


def test_referenced_audience_not_hard_deleted(graph) -> None:
    parent = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Parent",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
    )
    graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Child",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
        parent_audience_id=parent.audience_id,
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.delete_audience(
            tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=parent.audience_id
        )
    assert exc.value.code == "AUDIENCE_REFERENCED"


def test_unknown_biq_snapshot_fails_closed(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_persona(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Snapshot",
            actor_id="user-a",
            business_profile_snapshot_id="bps_missing000000000001",
        )
    assert exc.value.code == "UNKNOWN_SNAPSHOT"


def test_known_biq_snapshot_is_metadata_only(graph, biq_store) -> None:
    profile = biq_store.get_profile(tenant_id=TENANT_ID, workspace_id=PROJECT_ID)
    assert profile is not None
    persona = graph.create_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Linked snapshot",
        actor_id="user-a",
        business_profile_snapshot_id=profile.current_snapshot_id,
        business_segment_ref="seg_core",
    )
    assert persona.business_profile_snapshot_id == profile.current_snapshot_id
    assert persona.definition_authority.value == "USER_DECLARED"


def test_audience_default_status_is_draft(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Draft audience",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
    )
    assert audience.status == AudienceStatus.DRAFT
