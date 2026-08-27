from __future__ import annotations

from app.identity_graph.enums import (
    AudienceSourceKind,
    AudienceType,
    MarketingIdentityEdgeType,
)
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_audience_may_represent_persona_without_requiring_one_on_create(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Standalone",
        actor_id="user-a",
        audience_type=AudienceType.LOOKALIKE,
        source_kind=AudienceSourceKind.PLATFORM_DEFINED,
    )
    assert audience.persona_ids == ()
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Core", actor_id="user-a"
    )
    linked = graph.update_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        updates={"persona_ids": [persona.persona_id]},
    )
    assert linked.persona_ids == (persona.persona_id,)
    represented = graph.persona_audiences(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
    )
    assert represented[0].audience_id == audience.audience_id
    personas = graph.audience_personas(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )
    assert personas[0].persona_id == persona.persona_id


def test_campaign_target_edges_are_written(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Core", actor_id="user-a"
    )
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Reach",
        actor_id="user-a",
        audience_type=AudienceType.RETARGETING,
        source_kind=AudienceSourceKind.PREM3_DEFINED,
        persona_ids=(persona.persona_id,),
    )
    created = graph.create_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Flight",
        actor_id="user-a",
        persona_ids=(persona.persona_id,),
        audience_ids=(audience.audience_id,),
    )
    edges = graph.store.list_edges(tenant_id=TENANT_ID, project_id=PROJECT_ID)
    types = {(item.edge_type, item.from_node_id, item.to_node_id) for item in edges}
    assert (
        MarketingIdentityEdgeType.CAMPAIGN_TARGETS_PERSONA,
        created.campaign.campaign_id,
        persona.persona_id,
    ) in types
    assert (
        MarketingIdentityEdgeType.CAMPAIGN_TARGETS_AUDIENCE,
        created.campaign.campaign_id,
        audience.audience_id,
    ) in types
    assert (
        MarketingIdentityEdgeType.AUDIENCE_REPRESENTS_PERSONA,
        audience.audience_id,
        persona.persona_id,
    ) in types
    campaigns = graph.persona_campaigns(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, persona_id=persona.persona_id
    )
    assert campaigns[0].campaign_id == created.campaign.campaign_id
    audience_campaigns = graph.audience_campaigns(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )
    assert audience_campaigns[0].campaign_id == created.campaign.campaign_id


def test_derived_from_edge_is_reserved_not_implemented(graph) -> None:
    assert MarketingIdentityEdgeType.AUDIENCE_DERIVED_FROM.value == "AUDIENCE_DERIVED_FROM"
    assert not hasattr(graph, "derive_audience")
