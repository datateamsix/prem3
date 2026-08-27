from __future__ import annotations

import pytest

from app.identity_graph.enums import AudienceSourceKind, AudienceType
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_audience_parent_same_project(graph) -> None:
    parent = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Parent",
        actor_id="user-a",
        audience_type=AudienceType.FIRST_PARTY,
        source_kind=AudienceSourceKind.PREM3_DEFINED,
    )
    child = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Child",
        actor_id="user-a",
        audience_type=AudienceType.FIRST_PARTY,
        source_kind=AudienceSourceKind.PREM3_DEFINED,
        parent_audience_id=parent.audience_id,
    )
    assert child.parent_audience_id == parent.audience_id
    children = graph.audience_children(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=parent.audience_id
    )
    assert children[0].audience_id == child.audience_id
    lineage = graph.audience_lineage(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=child.audience_id
    )
    assert lineage.parent_audience_id == parent.audience_id
    assert parent.audience_id in lineage.ancestors


def test_audience_cannot_parent_itself(graph) -> None:
    created = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Solo",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.update_audience(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            audience_id=created.audience_id,
            updates={"parent_audience_id": created.audience_id},
        )
    assert exc.value.code == "SELF_PARENT"


def test_audience_hierarchy_rejects_cycle(graph) -> None:
    first = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="A",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
    )
    second = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="B",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
        parent_audience_id=first.audience_id,
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.update_audience(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            audience_id=first.audience_id,
            updates={"parent_audience_id": second.audience_id},
        )
    assert exc.value.code == "HIERARCHY_CYCLE"


def test_child_does_not_imply_membership_subset(graph) -> None:
    parent = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Parent",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOMER_LIST,
        source_kind=AudienceSourceKind.CRM_DEFINED,
    )
    child = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Child",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOMER_LIST,
        source_kind=AudienceSourceKind.CRM_DEFINED,
        parent_audience_id=parent.audience_id,
    )
    dumped = child.model_dump()
    assert "membership" not in dumped
    assert "member_list" not in dumped
    assert child.parent_audience_id == parent.audience_id
