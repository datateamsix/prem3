"""P6-10 decision bind and adherence math."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.investment_optimization.enums import (
    AdherenceClass,
    ExecutionAdherenceStatus,
    FrontierSelectionState,
    InvestmentDecisionKind,
    ProposalDecision,
)
from app.investment_optimization.errors import (
    DecisionLineageInvalidError,
    DecisionNotAuthorizedError,
    DecisionSourceNotReadyError,
    ExecutionEvidenceIncompleteError,
    RecommendationAdherenceNotComputableError,
)
from app.investment_optimization.risk.models import CandidateShare
from app.investment_planning.outcomes.decision import (
    bind_investment_decision,
    classify_decision,
    expire_without_decision,
)
from app.investment_planning.outcomes.execution_adherence import compute_execution_adherence
from app.investment_planning.outcomes.recommendation_adherence import (
    compute_recommendation_adherence,
    max_percentage_line_deviation,
)
from tests.unit.investment_planning.p6_10_support import (
    ACTUAL_SPEND,
    DECIDED_REF,
    MODIFIED_SHARES,
    PLAN,
    PLANNED_SPEND,
    PROJECT,
    RECOMMENDED_REF,
    RECOMMENDED_SHARES,
    TENANT,
    frontier_selection,
    outcome_service,
    p6_06_ledger,
    p6_06_receipt,
)


def test_approve_matching_shares_is_accept() -> None:
    assert (
        classify_decision(
            proposal_decision=ProposalDecision.APPROVE,
            recommended_shares=RECOMMENDED_SHARES,
            decided_shares=RECOMMENDED_SHARES,
        )
        is InvestmentDecisionKind.ACCEPT
    )


def test_approve_share_delta_is_accept_with_modifications() -> None:
    assert (
        classify_decision(
            proposal_decision=ProposalDecision.APPROVE,
            recommended_shares=RECOMMENDED_SHARES,
            decided_shares=MODIFIED_SHARES,
        )
        is InvestmentDecisionKind.ACCEPT_WITH_MODIFICATIONS
    )


def test_p6_06_decisions_map_without_inferred_accept() -> None:
    assert (
        classify_decision(
            proposal_decision=ProposalDecision.REJECT,
            recommended_shares=None,
            decided_shares=None,
        )
        is InvestmentDecisionKind.REJECT
    )
    assert (
        classify_decision(
            proposal_decision=ProposalDecision.REQUEST_REVISION,
            recommended_shares=None,
            decided_shares=None,
        )
        is InvestmentDecisionKind.DEFER
    )
    assert (
        classify_decision(
            proposal_decision=ProposalDecision.WITHDRAW,
            recommended_shares=None,
            decided_shares=None,
        )
        is InvestmentDecisionKind.WITHDRAW
    )


def test_expired_deadline_is_not_accept() -> None:
    with pytest.raises(DecisionSourceNotReadyError, match="not an inferred ACCEPT"):
        expire_without_decision(project_id=PROJECT)


def test_bind_requires_authenticated_human() -> None:
    receipt = p6_06_receipt(decided_by_user_id="")
    ledger = p6_06_ledger(receipt=receipt)
    with pytest.raises(DecisionNotAuthorizedError):
        bind_investment_decision(
            tenant_id=TENANT,
            project_id=PROJECT,
            receipt=receipt,
            ledger=ledger,
        )


def test_bind_requires_model_recommended_selection() -> None:
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt)
    selection = frontier_selection().model_copy(
        update={"state": FrontierSelectionState.MODEL_RECOMMENDED}
    )
    # FrozenModel: construct a non-recommended state by rebuilding if enum ever grows.
    # V1 only has MODEL_RECOMMENDED; lineage still requires the object when supplied.
    item = bind_investment_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        frontier_selection=selection,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=RECOMMENDED_SHARES,
    )
    assert item.proposal_decision_receipt_id == receipt.decision_receipt_id
    assert item.planning_decision_record_id == ledger.decision_id
    assert item.decision is InvestmentDecisionKind.ACCEPT
    assert item.decision_reason_text_ref == receipt.decision_receipt_id


def test_bind_rejects_mismatched_proposal_lineage() -> None:
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt).model_copy(
        update={"proposal_id": "oprop_otherproposal00001"}
    )
    with pytest.raises(DecisionLineageInvalidError):
        bind_investment_decision(
            tenant_id=TENANT,
            project_id=PROJECT,
            receipt=receipt,
            ledger=ledger,
        )


def test_accept_with_modifications_keeps_both_portfolio_refs() -> None:
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt)
    item = bind_investment_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=DECIDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=MODIFIED_SHARES,
    )
    assert item.decision is InvestmentDecisionKind.ACCEPT_WITH_MODIFICATIONS
    assert item.recommended_portfolio_ref == RECOMMENDED_REF
    assert item.decided_portfolio_ref == DECIDED_REF


def test_reject_does_not_require_plan_revision_refs() -> None:
    receipt = p6_06_receipt(decision=ProposalDecision.REJECT)
    ledger = p6_06_ledger(receipt=receipt)
    item = bind_investment_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
    )
    assert item.decision is InvestmentDecisionKind.REJECT
    assert item.decided_portfolio_ref is None


def test_recommendation_adherence_reports_l1_and_channel_sets() -> None:
    item = compute_recommendation_adherence(
        tenant_id=TENANT,
        project_id=PROJECT,
        investment_decision_ref="oidec_p610decision000001",
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=DECIDED_REF,
        recommended=RECOMMENDED_SHARES,
        decided=MODIFIED_SHARES,
    )
    assert item.l1_distance == pytest.approx(0.2)
    assert item.max_absolute_line_deviation == pytest.approx(0.1)
    assert item.adherence_class is AdherenceClass.MODIFIED
    assert item.channels_added == ()
    assert item.channels_removed == ()


def test_recommendation_adherence_refuses_percent_when_base_is_zero() -> None:
    recommended = (CandidateShare(channel_id="search", share=0.0),)
    decided = (CandidateShare(channel_id="search", share=0.1),)
    assert max_percentage_line_deviation(recommended=recommended, decided=decided) is None
    added = compute_recommendation_adherence(
        tenant_id=TENANT,
        project_id=PROJECT,
        investment_decision_ref="oidec_p610decision000002",
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=DECIDED_REF,
        recommended=(CandidateShare(channel_id="search", share=0.5),),
        decided=(
            CandidateShare(channel_id="search", share=0.5),
            CandidateShare(channel_id="display", share=0.1),
        ),
    )
    assert added.channels_added == ("display",)
    assert added.max_percentage_deviation == 0.0


def test_recommendation_adherence_requires_both_share_sets() -> None:
    with pytest.raises(RecommendationAdherenceNotComputableError):
        compute_recommendation_adherence(
            tenant_id=TENANT,
            project_id=PROJECT,
            investment_decision_ref="oidec_x",
            recommended_portfolio_ref=RECOMMENDED_REF,
            decided_portfolio_ref=DECIDED_REF,
            recommended=(),
            decided=RECOMMENDED_SHARES,
        )


def test_execution_adherence_incomplete_is_not_zero_spend() -> None:
    item = compute_execution_adherence(
        tenant_id=TENANT,
        project_id=PROJECT,
        approved_plan_ref=PLAN,
        planned=PLANNED_SPEND,
        actual={"search": Decimal("48.00"), "social": None, "video": None},
    )
    assert item.status is ExecutionAdherenceStatus.INCOMPLETE
    assert item.adherence_class is AdherenceClass.INCOMPLETE
    assert item.incomplete_line_count == 2
    assert item.comparable_line_count == 1
    assert "EXECUTION_ADHERENCE_INCOMPLETE" in item.limitations


def test_missing_actuals_never_treated_as_zero() -> None:
    item = compute_execution_adherence(
        tenant_id=TENANT,
        project_id=PROJECT,
        approved_plan_ref=PLAN,
        planned=PLANNED_SPEND,
        actual={},
    )
    assert item.status is ExecutionAdherenceStatus.INCOMPLETE
    assert "EXECUTION_EVIDENCE_INCOMPLETE" in item.limitations
    with pytest.raises(ExecutionEvidenceIncompleteError):
        compute_execution_adherence(
            tenant_id=TENANT,
            project_id=PROJECT,
            approved_plan_ref=PLAN,
            planned=PLANNED_SPEND,
            actual={},
            require_complete=True,
        )


def test_complete_execution_adherence_matches_when_all_lines_present() -> None:
    item = compute_execution_adherence(
        tenant_id=TENANT,
        project_id=PROJECT,
        approved_plan_ref=PLAN,
        planned=PLANNED_SPEND,
        actual=ACTUAL_SPEND,
        actual_spend_source_ref="asrc_p610actuals",
        exposure_handoff_ref="xrh_p610handoff",
    )
    assert item.status is ExecutionAdherenceStatus.COMPLETE
    assert item.incomplete_line_count == 0
    assert item.exposure_handoff_ref == "xrh_p610handoff"


def test_bind_is_idempotent_by_fingerprint() -> None:
    service = outcome_service()
    receipt = p6_06_receipt()
    ledger = p6_06_ledger(receipt=receipt)
    first = service.bind_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=RECOMMENDED_SHARES,
    )
    second = service.bind_decision(
        tenant_id=TENANT,
        project_id=PROJECT,
        receipt=receipt,
        ledger=ledger,
        recommended_portfolio_ref=RECOMMENDED_REF,
        decided_portfolio_ref=RECOMMENDED_REF,
        recommended_shares=RECOMMENDED_SHARES,
        decided_shares=RECOMMENDED_SHARES,
    )
    assert first.investment_decision_id == second.investment_decision_id
