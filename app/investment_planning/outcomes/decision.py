"""Bind P6-06 human decisions. Do not infer ACCEPT."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.contracts import (
    PlanningDecisionRecord,
    ProposalDecisionReceipt,
)
from app.investment_optimization.enums import (
    FrontierSelectionState,
    InvestmentDecisionKind,
    ProposalDecision,
)
from app.investment_optimization.errors import (
    DecisionLineageInvalidError,
    DecisionNotAuthorizedError,
    DecisionSourceNotReadyError,
)
from app.investment_optimization.ids import new_investment_decision_id
from app.investment_optimization.risk.models import CandidateShare, FrontierSelection
from app.investment_optimization.risk.stability import l1_share_distance
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.outcomes.models import InvestmentDecisionRecord


def classify_decision(
    *,
    proposal_decision: ProposalDecision,
    recommended_shares: tuple[CandidateShare, ...] | None,
    decided_shares: tuple[CandidateShare, ...] | None,
) -> InvestmentDecisionKind:
    if proposal_decision is ProposalDecision.REJECT:
        return InvestmentDecisionKind.REJECT
    if proposal_decision is ProposalDecision.REQUEST_REVISION:
        return InvestmentDecisionKind.DEFER
    if proposal_decision is ProposalDecision.WITHDRAW:
        return InvestmentDecisionKind.WITHDRAW
    if proposal_decision is ProposalDecision.APPROVE:
        if recommended_shares is None or decided_shares is None:
            return InvestmentDecisionKind.ACCEPT_WITH_MODIFICATIONS
        if l1_share_distance(candidate=decided_shares, baseline=recommended_shares) == 0.0:
            return InvestmentDecisionKind.ACCEPT
        return InvestmentDecisionKind.ACCEPT_WITH_MODIFICATIONS
    raise DecisionLineageInvalidError("Unsupported P6-06 proposal decision.")


def bind_investment_decision(
    *,
    tenant_id: str,
    project_id: str,
    receipt: ProposalDecisionReceipt,
    ledger: PlanningDecisionRecord,
    frontier_selection: FrontierSelection | None = None,
    recommended_portfolio_ref: str | None = None,
    decided_portfolio_ref: str | None = None,
    recommended_shares: tuple[CandidateShare, ...] | None = None,
    decided_shares: tuple[CandidateShare, ...] | None = None,
) -> InvestmentDecisionRecord:
    if not receipt.decided_by_user_id:
        raise DecisionNotAuthorizedError("Only an authenticated human decision may bind.")
    if receipt.proposal_id != ledger.proposal_id:
        raise DecisionLineageInvalidError("Decision receipt and ledger proposal do not match.")
    if receipt.tenant_id != tenant_id or receipt.project_id != project_id:
        raise DecisionLineageInvalidError("Decision receipt is not in this project.")
    if frontier_selection is not None:
        if frontier_selection.state is not FrontierSelectionState.MODEL_RECOMMENDED:
            raise DecisionLineageInvalidError("Frontier selection is not MODEL_RECOMMENDED.")
    kind = classify_decision(
        proposal_decision=receipt.decision,
        recommended_shares=recommended_shares,
        decided_shares=decided_shares,
    )
    created = datetime.now(UTC)
    context = metadata_fingerprint(
        {
            "proposal": receipt.proposal_id,
            "receipt": receipt.fingerprint,
            "ledger": ledger.fingerprint,
            "selection": frontier_selection.selection_fingerprint if frontier_selection else "",
        }
    )
    payload = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "kind": kind.value,
        "receipt": receipt.fingerprint,
        "ledger": ledger.fingerprint,
        "recommended": recommended_portfolio_ref or "",
        "decided": decided_portfolio_ref or "",
        "context": context,
    }
    return InvestmentDecisionRecord(
        investment_decision_id=new_investment_decision_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        proposal_ref=receipt.proposal_id,
        proposal_decision_receipt_id=receipt.decision_receipt_id,
        planning_decision_record_id=ledger.decision_id,
        frontier_selection_ref=(
            frontier_selection.selection_id if frontier_selection is not None else None
        ),
        candidate_portfolio_ref=(
            frontier_selection.selected_candidate_ref if frontier_selection is not None else None
        ),
        recommended_portfolio_ref=recommended_portfolio_ref,
        decided_portfolio_ref=decided_portfolio_ref,
        decision=kind,
        decision_reason_code=receipt.reason_code,
        decision_reason_text_ref=receipt.decision_receipt_id if receipt.comment else None,
        decided_by_user_id=receipt.decided_by_user_id,
        decided_at=receipt.decided_at,
        decision_context_fingerprint=context,
        decision_fingerprint=metadata_fingerprint(payload),
        created_at=created,
    )


def expire_without_decision(*, project_id: str) -> None:
    del project_id
    raise DecisionSourceNotReadyError(
        "An expired deadline is not an inferred ACCEPT."
    )
