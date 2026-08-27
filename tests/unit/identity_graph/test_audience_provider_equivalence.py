from __future__ import annotations

from app.identity_graph.contracts import AudienceExternalBinding
from app.identity_graph.enums import MarketingIdentityEdgeType
from app.identity_graph.service import CampaignIdentityService


def test_audience_external_binding_is_reserved_ig03_seam() -> None:
    first = AudienceExternalBinding(
        binding_id="igb_aaaaaaaaaaaaaaaaaaaa",
        audience_id="aud_aaaaaaaaaaaaaaaaaaaa",
        provider_id="google_ads",
        external_audience_id="ext_aud_one",
    )
    second = AudienceExternalBinding(
        binding_id="igb_bbbbbbbbbbbbbbbbbbbb",
        audience_id="aud_aaaaaaaaaaaaaaaaaaaa",
        provider_id="meta",
        external_audience_id="ext_aud_two",
    )
    assert first.audience_id == second.audience_id
    assert first.provider_id != second.provider_id
    assert "membership_identical" not in AudienceExternalBinding.model_fields
    assert "member_list" not in AudienceExternalBinding.model_fields
    assert MarketingIdentityEdgeType.AUDIENCE_BOUND_TO_EXTERNAL.value == (
        "AUDIENCE_BOUND_TO_EXTERNAL"
    )
    assert not hasattr(CampaignIdentityService, "create_audience_external_binding")
    assert not hasattr(CampaignIdentityService, "list_audience_external_bindings")
