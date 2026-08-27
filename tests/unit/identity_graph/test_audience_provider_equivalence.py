from __future__ import annotations

import pytest

from app.identity_graph.contracts import AudienceExternalBinding
from app.identity_graph.enums import (
    AudienceSourceKind,
    AudienceType,
    MarketingIdentityEdgeType,
)
from app.identity_graph.errors import IdentityGraphError
from app.identity_graph.service import CampaignIdentityService
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def _audience(graph):
    return graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="CRM buyers",
        actor_id="user-a",
        audience_type=AudienceType.CRM_SEGMENT,
        source_kind=AudienceSourceKind.CRM_DEFINED,
    )


def test_audience_external_binding_uses_canonical_audience(graph) -> None:
    audience = _audience(graph)
    binding = graph.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="google_ads",
        external_audience_id="ext_aud_one",
        actor_id="user-a",
    )
    assert binding.audience_id == audience.audience_id
    assert binding.audience_id.startswith("aud_")
    assert binding.external_audience_id != binding.audience_id


def test_unknown_audience_rejected(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_audience_external(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            audience_id="aud_doesnotexist00000000",
            provider_id="google_ads",
            external_audience_id="ext_aud_missing",
            actor_id="user-a",
        )
    assert exc.value.code == "UNKNOWN_AUDIENCE"


def test_cross_project_audience_binding_rejected(graph) -> None:
    audience = _audience(graph)
    other_project = "wsp_projectb000000001"
    graph.create_market(
        tenant_id=TENANT_ID,
        project_id=other_project,
        name="Other market",
        actor_id="user-a",
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_audience_external(
            tenant_id=TENANT_ID,
            project_id=other_project,
            audience_id=audience.audience_id,
            provider_id="google_ads",
            external_audience_id="ext_aud_cross",
            actor_id="user-a",
        )
    assert exc.value.code == "UNKNOWN_AUDIENCE"


def test_same_canonical_audience_can_map_to_multiple_providers(graph) -> None:
    audience = _audience(graph)
    first = graph.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="google_ads",
        external_audience_id="ext_aud_one",
        actor_id="user-a",
    )
    second = graph.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="meta_ads",
        external_audience_id="ext_aud_two",
        actor_id="user-a",
    )
    assert first.audience_id == second.audience_id
    assert first.provider_id != second.provider_id
    rows = graph.list_audience_external_bindings(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )
    assert len(rows) == 2
    edges = [
        item
        for item in graph.store.list_edges(tenant_id=TENANT_ID, project_id=PROJECT_ID)
        if item.edge_type == MarketingIdentityEdgeType.AUDIENCE_BOUND_TO_EXTERNAL
    ]
    assert len(edges) == 2


def test_multi_provider_binding_does_not_assert_member_equivalence(graph) -> None:
    audience = _audience(graph)
    graph.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="google_ads",
        external_audience_id="ext_aud_one",
        actor_id="user-a",
    )
    graph.bind_audience_external(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        audience_id=audience.audience_id,
        provider_id="meta_ads",
        external_audience_id="ext_aud_two",
        actor_id="user-a",
    )
    assert "membership_identical" not in AudienceExternalBinding.model_fields
    assert "member_list" not in AudienceExternalBinding.model_fields
    dumped = graph.list_audience_external_bindings(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )[0].model_dump()
    assert "membership_identical" not in dumped
    assert hasattr(CampaignIdentityService, "create_audience_external_binding")
    assert hasattr(CampaignIdentityService, "list_audience_external_bindings")


def test_archived_audience_new_binding_rejected_or_reviewed(graph) -> None:
    audience = _audience(graph)
    graph.archive_audience(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, audience_id=audience.audience_id
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_audience_external(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            audience_id=audience.audience_id,
            provider_id="google_ads",
            external_audience_id="ext_aud_archived",
            actor_id="user-a",
        )
    assert exc.value.code == "ARCHIVED_TARGET"
