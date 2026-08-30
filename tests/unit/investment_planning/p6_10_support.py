"""P6-10 fixtures: P6-06 receipts, shares, and outcome service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.investment_optimization.contracts import (
    PlanningDecisionRecord,
    ProposalDecisionReceipt,
)
from app.investment_optimization.enums import (
    DecisionRecordType,
    FrontierSelectionState,
    ProposalDecision,
    RiskPosture,
)
from app.investment_optimization.ids import (
    new_planning_decision_id,
    new_proposal_decision_receipt_id,
)
from app.investment_optimization.risk.models import CandidateShare, FrontierSelection
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.service import OutcomeService

TENANT = "ten_p610"
PROJECT = "ws_p610"
PROPOSAL = "oprop_p610proposal000001"
USER = "user_p610_decider"
PLAN = "ipln_p610approved00000001"
RECOMMENDED_REF = "ocand_p610recommended0001"
DECIDED_REF = "ocand_p610decided0000001"

RECOMMENDED_SHARES = (
    CandidateShare(channel_id="search", share=0.50),
    CandidateShare(channel_id="social", share=0.30),
    CandidateShare(channel_id="video", share=0.20),
)
MODIFIED_SHARES = (
    CandidateShare(channel_id="search", share=0.40),
    CandidateShare(channel_id="social", share=0.40),
    CandidateShare(channel_id="video", share=0.20),
)

PLANNED_SPEND = {
    "search": Decimal("50.00"),
    "social": Decimal("30.00"),
    "video": Decimal("20.00"),
}
ACTUAL_SPEND = {
    "search": Decimal("48.00"),
    "social": Decimal("31.00"),
    "video": Decimal("21.00"),
}


def now() -> datetime:
    return datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


def outcome_service() -> OutcomeService:
    return OutcomeService(InMemoryOptimizationMetadataStore())


def p6_06_receipt(
    *,
    tenant_id: str = TENANT,
    project_id: str = PROJECT,
    decision: ProposalDecision = ProposalDecision.APPROVE,
    decided_by_user_id: str = USER,
    comment: str | None = "approved after review",
) -> ProposalDecisionReceipt:
    decided_at = now()
    receipt_id = new_proposal_decision_receipt_id()
    body = {
        "proposal_id": PROPOSAL,
        "decision": decision.value,
        "proposal_fingerprint": "prop_fp_p610",
        "decided_by_user_id": decided_by_user_id,
    }
    return ProposalDecisionReceipt(
        decision_receipt_id=receipt_id,
        proposal_id=PROPOSAL,
        tenant_id=tenant_id,
        project_id=project_id,
        decision=decision,
        decided_by_user_id=decided_by_user_id,
        decided_at=decided_at,
        proposal_fingerprint="prop_fp_p610",
        scenario_fingerprint="scn_fp_p610",
        source_plan_fingerprint="plan_fp_p610",
        optimization_result_fingerprint="res_fp_p610",
        comment=comment,
        created_at=decided_at,
        fingerprint=metadata_fingerprint(body),
    )


def p6_06_ledger(
    *,
    receipt: ProposalDecisionReceipt,
) -> PlanningDecisionRecord:
    return PlanningDecisionRecord(
        decision_id=new_planning_decision_id(),
        decision_type=DecisionRecordType.OPTIMIZATION_PROPOSAL,
        proposal_id=receipt.proposal_id,
        tenant_id=receipt.tenant_id,
        project_id=receipt.project_id,
        decision=receipt.decision,
        owner=receipt.decided_by_user_id,
        evidence_refs=(receipt.decision_receipt_id,),
        decided_at=receipt.decided_at,
        fingerprint=metadata_fingerprint(
            {"proposal_id": receipt.proposal_id, "decision": receipt.decision.value}
        ),
    )


def frontier_selection() -> FrontierSelection:
    return FrontierSelection(
        selection_id="osel_p610selection000001",
        frontier_id="ofrn_p610frontier000001",
        selected_candidate_ref=RECOMMENDED_REF,
        risk_posture=RiskPosture.EXPECTED_OUTCOME,
        selection_policy="EXPECTED_OUTCOME",
        state=FrontierSelectionState.MODEL_RECOMMENDED,
        selection_fingerprint="sel_fp_p610",
        created_at=now(),
    )


def seed_decision_authority(
    store: InMemoryOptimizationMetadataStore,
    *,
    decision: ProposalDecision = ProposalDecision.APPROVE,
    with_selection: bool = True,
) -> tuple[ProposalDecisionReceipt, PlanningDecisionRecord, FrontierSelection | None]:
    receipt = p6_06_receipt(decision=decision)
    ledger = p6_06_ledger(receipt=receipt)
    store.put(receipt)
    store.put(ledger)
    selection = None
    if with_selection:
        selection = frontier_selection()
        store.put(selection)
    return receipt, ledger, selection
