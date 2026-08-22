from app.business_iq.enums import (
    BusinessContextReadyStatus,
    ChannelLifecycle,
    ClarificationAnswer,
    KnowledgeState,
    ProposalDecision,
)
from tests.unit.business_iq.conftest import ready_payload


def test_create_edit_versions_and_custom_text(biq, tenant_ctx) -> None:
    del tenant_ctx
    created = biq.create_profile(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="user-a",
        payload=ready_payload(),
        organization_display_name="Acme Org",
    )
    assert created.version == 1
    assert created.kpi_custom_text == "Net revenue after refunds, not Gross Merchandise Value"
    assert created.metadata.organization_display_name == "Acme Org"
    assert created.metadata.logo_asset_ref == "drive:logo"
    first_fp = created.fingerprint
    snapshot_id = created.current_snapshot_id
    updated = biq.patch_profile(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="user-a",
        payload={"competition_notes": "Retail marketplace pressure"},
    )
    assert updated.version == 2
    assert updated.fingerprint != first_fp
    historical = biq.get_snapshot(tenant_id="tenant-a", snapshot_id=snapshot_id)
    assert historical.profile.competition_notes is None
    assert historical.profile.version == 1
    versions = biq.list_versions(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert [item.version for item in versions] == [1, 2]


def test_unknown_acknowledged_and_readiness(biq, tenant_ctx) -> None:
    del tenant_ctx
    payload = {
        "business_identity": {"brand_name": "Solo"},
        "knowledge_gaps": [
            {
                "gap_id": "bgap_obj",
                "concept": "measurement_objective",
                "question": "What is the objective?",
                "acknowledged": True,
                "knowledge_state": KnowledgeState.UNKNOWN_ACKNOWLEDGED.value,
            },
            {
                "gap_id": "bgap_kpi",
                "concept": "kpi",
                "question": "What KPI?",
                "acknowledged": True,
                "knowledge_state": KnowledgeState.UNKNOWN_ACKNOWLEDGED.value,
            },
            {
                "gap_id": "bgap_mkt",
                "concept": "markets",
                "question": "Which markets?",
                "acknowledged": True,
                "knowledge_state": KnowledgeState.UNKNOWN_ACKNOWLEDGED.value,
            },
            {
                "gap_id": "bgap_ch",
                "concept": "marketing_portfolio",
                "question": "Which channels?",
                "acknowledged": True,
                "knowledge_state": KnowledgeState.UNKNOWN_ACKNOWLEDGED.value,
            },
        ],
    }
    biq.create_profile(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="user-a",
        payload=payload,
    )
    receipt = biq.evaluate_ready(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert receipt.status is BusinessContextReadyStatus.BUSINESS_CONTEXT_READY
    assert "kpi" in receipt.unknown_acknowledged


def test_channel_lifecycle_prior_evidence_and_brief(biq, tenant_ctx) -> None:
    del tenant_ctx
    profile = biq.create_profile(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="user-a",
        payload=ready_payload(),
    )
    audio = next(item for item in profile.marketing_portfolio if item.canonical_name == "Streaming Audio")
    assert audio.active_from == "2026-04-01"
    assert audio.lifecycle_status is ChannelLifecycle.ACTIVE
    assert profile.prior_evidence[0].evidence_type == "geo_holdout"
    ready = biq.evaluate_ready(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert ready.status is BusinessContextReadyStatus.BUSINESS_CONTEXT_READY
    brief = biq.regenerate_brief(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert brief.advisory is True
    assert "bfact_kpi" in brief.evidence_refs
    assert brief.plain_language_summary.evidence_refs == brief.evidence_refs
    after = biq.get_profile(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert after.fingerprint == profile.fingerprint


def test_proposal_accept_reject_and_no_silent_mutate(biq, tenant_ctx) -> None:
    del tenant_ctx
    profile = biq.create_profile(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="user-a",
        payload=ready_payload(),
    )
    rejected = biq.create_proposal(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="df-agent",
        previous_fact={"concept": "Paid Social", "lifecycle_status": "ACTIVE"},
        observed_evidence={"gap": "2025-04"},
        proposed_fact={"concept": "channel_lifecycle", "lifecycle_status": "PAUSED", "channel": "Paid Search"},
    )
    decided = biq.decide_proposal(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        proposal_id=rejected.proposal_id,
        actor_id="user-a",
        accept=False,
    )
    assert decided.decision is ProposalDecision.REJECTED
    unchanged = biq.get_profile(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert unchanged.version == profile.version
    accepted = biq.create_proposal(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        actor_id="df-agent",
        previous_fact=None,
        observed_evidence={"gap": "2025-04"},
        proposed_fact={"concept": "always_on_conflict", "value": "intentional_pause"},
    )
    biq.decide_proposal(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        proposal_id=accepted.proposal_id,
        actor_id="user-a",
        accept=True,
    )
    mutated = biq.get_profile(tenant_id="tenant-a", workspace_id="wsp_test00000000000001")
    assert mutated.version == profile.version + 1
    clarification = biq.create_clarification(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        coverage_gap_id="dfgap_demo",
        fact_id="bfact_kpi",
        question="Was Paid Social intentionally paused?",
    )
    answered = biq.answer_clarification(
        tenant_id="tenant-a",
        workspace_id="wsp_test00000000000001",
        clarification_id=clarification.clarification_id,
        actor_id="user-a",
        answer=ClarificationAnswer.CONFIRMED_BUSINESS_PAUSE,
        observed_evidence={"months": "2025-04"},
    )
    assert answered.proposal_id is not None
