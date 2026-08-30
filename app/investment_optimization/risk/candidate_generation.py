"""Native optimum plus deterministic feasible neighbors. No random portfolios."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.errors import (
    CandidateGenerationFailedError,
    CandidateInfeasibleError,
    InsufficientFrontierCandidatesError,
)
from app.investment_optimization.ids import new_candidate_id, new_feasibility_receipt_id
from app.investment_optimization.risk.models import (
    CandidatePortfolio,
    CandidateShare,
    FeasibilityReceipt,
    RiskEvaluationPolicy,
)
from app.investment_planning.fingerprint import metadata_fingerprint


def allocation_fingerprint(shares: tuple[CandidateShare, ...]) -> str:
    return metadata_fingerprint(
        {
            "shares": [
                {"channel_id": line.channel_id, "share": round(line.share, 12)}
                for line in sorted(shares, key=lambda item: item.channel_id)
            ]
        }
    )


def _renormalize(shares: tuple[CandidateShare, ...]) -> tuple[CandidateShare, ...]:
    total = sum(line.share for line in shares)
    if total <= 0.0:
        raise CandidateGenerationFailedError("Allocation shares must sum to a positive total.")
    return tuple(
        CandidateShare(channel_id=line.channel_id, share=line.share / total) for line in shares
    )


def shares_are_feasible(shares: tuple[CandidateShare, ...]) -> bool:
    if not shares:
        return False
    if any(line.share < -1e-12 for line in shares):
        return False
    return abs(sum(line.share for line in shares) - 1.0) < 1e-9


def neighbor_allocations(
    native: tuple[CandidateShare, ...],
    *,
    delta: float,
) -> tuple[tuple[CandidateShare, ...], ...]:
    ordered = _renormalize(native)
    if len(ordered) < 2:
        raise CandidateGenerationFailedError("Neighbor generation requires at least two channels.")
    neighbors: list[tuple[CandidateShare, ...]] = []
    source = ordered[0]
    if source.share <= delta:
        raise CandidateGenerationFailedError("Native lead share is too small for the pinned delta.")
    for index in range(1, len(ordered)):
        moved: list[CandidateShare] = []
        for position, line in enumerate(ordered):
            if position == 0:
                moved.append(CandidateShare(channel_id=line.channel_id, share=line.share - delta))
            elif position == index:
                moved.append(CandidateShare(channel_id=line.channel_id, share=line.share + delta))
            else:
                moved.append(line)
        neighbors.append(_renormalize(tuple(moved)))
    return tuple(neighbors)


def generate_candidates(
    *,
    tenant_id: str,
    project_id: str,
    policy: RiskEvaluationPolicy,
    native_shares: tuple[CandidateShare, ...],
    optimization_run_id: str,
    base_approved_plan_ref: str,
    model_version_ref: str,
    assumption_set_ref: str | None,
    constraint_set_ref: str | None,
    input_fingerprint: str,
    now: datetime | None = None,
) -> tuple[tuple[CandidatePortfolio, FeasibilityReceipt, tuple[CandidateShare, ...]], ...]:
    created = now or datetime.now(UTC)
    native = _renormalize(native_shares)
    if not shares_are_feasible(native):
        raise CandidateInfeasibleError("Native Meridian allocation is not a feasible share vector.")
    bundles: list[tuple[tuple[CandidateShare, ...], bool]] = [(native, True)]
    for neighbor in neighbor_allocations(native, delta=policy.neighbor_share_delta):
        if not shares_are_feasible(neighbor):
            raise CandidateInfeasibleError("Generated neighbor is not feasible.")
        bundles.append((neighbor, False))
    if len(bundles) < policy.minimum_candidate_count:
        raise InsufficientFrontierCandidatesError(
            "Candidate generation produced fewer portfolios than the policy minimum."
        )
    generated: list[tuple[CandidatePortfolio, FeasibilityReceipt, tuple[CandidateShare, ...]]] = []
    for shares, is_native in bundles:
        candidate_id = new_candidate_id()
        receipt_id = new_feasibility_receipt_id()
        alloc_fp = allocation_fingerprint(shares)
        receipt = FeasibilityReceipt(
            receipt_id=receipt_id,
            candidate_portfolio_id=candidate_id,
            feasible=True,
            fingerprint=metadata_fingerprint(
                {"candidate_portfolio_id": candidate_id, "feasible": True, "allocation": alloc_fp}
            ),
        )
        candidate = CandidatePortfolio(
            candidate_portfolio_id=candidate_id,
            tenant_id=tenant_id,
            project_id=project_id,
            base_approved_plan_ref=base_approved_plan_ref,
            optimization_run_id=optimization_run_id,
            generation_authority=f"native_run:{optimization_run_id}",
            assumption_set_ref=assumption_set_ref,
            constraint_set_ref=constraint_set_ref,
            model_version_ref=model_version_ref,
            feasibility_receipt_id=receipt_id,
            allocation_fingerprint=alloc_fp,
            input_fingerprint=input_fingerprint,
            candidate_fingerprint=metadata_fingerprint(
                {
                    "allocation": alloc_fp,
                    "input": input_fingerprint,
                    "run": optimization_run_id,
                    "policy": policy.policy_fingerprint,
                }
            ),
            native_optimum=is_native,
            created_at=created,
        )
        generated.append((candidate, receipt, shares))
    return tuple(generated)
