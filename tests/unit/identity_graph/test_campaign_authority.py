from __future__ import annotations

from app.identity_graph.enums import IdentitySourceAuthority, TrackingImplementationStatus
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_campaign_id_authority_is_prem3_generated(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Authority", actor_id="user-a"
    )
    assert created.campaign.campaign_id_authority == IdentitySourceAuthority.PREM3_GENERATED


def test_market_scope_authority_is_user_declared(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Markets", actor_id="user-a"
    )
    assert created.campaign.market_scope_authority == IdentitySourceAuthority.USER_DECLARED


def test_tracking_not_observed_without_evidence(graph) -> None:
    created = graph.create_campaign(
        tenant_id=TENANT_ID, project_id=PROJECT_ID, name="Tracking", actor_id="user-a"
    )
    assert created.instructions.implementation_status == (
        TrackingImplementationStatus.NOT_IMPLEMENTED
    )
    assert created.instructions.instruction_authority == IdentitySourceAuthority.PREM3_GENERATED
    receipt = graph.validate_campaign(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        campaign_id=created.campaign.campaign_id,
    )
    assert receipt.tracking_instruction_present is True
    assert "TRACKING_STATUS_UNEVIDENCED" not in receipt.issues
