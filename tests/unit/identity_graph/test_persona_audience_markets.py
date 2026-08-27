from __future__ import annotations

import pytest

from app.identity_graph.enums import AudienceSourceKind, AudienceType, MarketKind
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID, make_canonical_market


def test_empty_market_ids_mean_unspecified_global_scope(graph) -> None:
    persona = graph.create_persona(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Global archetype", actor_id="user-a"
    )
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Global segment",
        actor_id="user-a",
        audience_type=AudienceType.CUSTOM,
        source_kind=AudienceSourceKind.USER_DECLARED,
    )
    assert persona.market_ids == ()
    assert audience.market_ids == ()


def test_nonempty_market_ids_must_be_known_canonical_markets(graph) -> None:
    market = make_canonical_market(graph, name="United States", market_kind=MarketKind.COUNTRY)
    persona = graph.create_persona(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="US buyer",
        actor_id="user-a",
        market_ids=(market.market_id,),
    )
    assert persona.market_ids == (market.market_id,)
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_persona(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Bad market",
            actor_id="user-a",
            market_ids=("mkt_cccccccccccccccccccc",),
        )
    assert exc.value.code == "UNKNOWN_MARKET"


def test_display_labels_never_join_as_market_ids(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_audience(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Label join",
            actor_id="user-a",
            audience_type=AudienceType.GEOGRAPHIC,
            source_kind=AudienceSourceKind.USER_DECLARED,
            market_ids=("United States",),
        )
    assert exc.value.code == "UNKNOWN_MARKET"
