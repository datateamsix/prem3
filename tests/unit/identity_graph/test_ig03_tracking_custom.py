from __future__ import annotations

import pytest

from app.identity_graph.contracts import ObservedCampaignSignals
from app.identity_graph.enums import (
    BindingStatus,
    CampaignIdentitySource,
    CustomIdentifierScope,
    ResolutionAuthority,
    TrackingKind,
)
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_default_prem3_utm_id_binding_reused(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Tracked", actor_id="user-a"
    )
    assert created.tracking.tracking_kind == TrackingKind.PREM3_UTM_ID
    assert created.tracking.parameter_name == "utm_id"


def test_tracking_binding_value_equals_campaign_id(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Tracked", actor_id="user-a"
    )
    assert created.tracking.parameter_value == created.campaign.campaign_id
    assert created.instructions.utm_id == created.campaign.campaign_id


def test_custom_identifier_requires_approved_rule(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Custom", actor_id="user-a"
    )
    with pytest.raises(IdentityGraphError) as exc:
        graph.bind_custom_identifier(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            campaign_id=created.campaign.campaign_id,
            parameter_name="promo_code",
            parameter_value="SPRING",
            actor_id="user-a",
            status=BindingStatus.ACTIVE,
        )
    assert exc.value.code == "CUSTOM_IDENTIFIER_NOT_APPROVED"


def test_tracking_binding_effective_dates_respected(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Dated", actor_id="user-a"
    )
    graph.bind_tracking(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
        tracking_kind=TrackingKind.CUSTOM_EVENT_PARAM,
        parameter_name="promo_code",
        parameter_value="SPRING",
        actor_id="user-a",
        status=BindingStatus.APPROVED,
        effective_start="2026-01-01",
        effective_end="2026-03-31",
    )
    graph.create_custom_identifier_rule(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        parameter_name="promo_code",
        parameter_scope=CustomIdentifierScope.GA4_EVENT_PARAM,
        actor_id="user-a",
    )
    inside = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            custom_parameter_name="promo_code",
            custom_parameter_value="SPRING",
            observed_at="2026-02-01",
        ),
    )
    outside = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            custom_parameter_name="promo_code",
            custom_parameter_value="SPRING",
            observed_at="2026-08-01",
        ),
    )
    assert inside.campaign_id == created.campaign.campaign_id
    assert inside.source == CampaignIdentitySource.CUSTOM_IDENTIFIER
    assert outside.campaign_id is None
    assert outside.status == ResolutionAuthority.UNRESOLVED


def test_conflicting_tracking_bindings_review_required(graph) -> None:
    first = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="One", actor_id="user-a"
    )
    second = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Two", actor_id="user-a"
    )
    graph.bind_custom_identifier(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=first.campaign.campaign_id,
        parameter_name="promo_code",
        parameter_value="SHARED",
        actor_id="user-a",
        status=BindingStatus.APPROVED,
    )
    graph.bind_custom_identifier(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=second.campaign.campaign_id,
        parameter_name="promo_code",
        parameter_value="SHARED",
        actor_id="user-a",
        status=BindingStatus.APPROVED,
    )
    resolved = graph.resolve_observed(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        signals=ObservedCampaignSignals(
            custom_parameter_name="promo_code", custom_parameter_value="SHARED"
        ),
    )
    assert resolved.status == ResolutionAuthority.REVIEW_REQUIRED
    assert "CONFLICTING_EXACT_BINDINGS" in resolved.issues
