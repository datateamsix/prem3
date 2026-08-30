"""Idempotent P6-09 frontier orchestration. Does not mutate approved plans."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import (
    ConcentrationDimension,
    FrontierSelectionState,
    RiskFrontierReadinessStatus,
    RiskPosture,
    RiskTaxonomyClass,
)
from app.investment_optimization.errors import (
    CandidateNotFoundError,
    ExposureRiskNotQualifiedError,
    FrontierNotFoundError,
    FrontierSelectionNotAllowedError,
    FrontierSelectionNotFoundError,
    ParityReceiptNotFoundError,
    PosteriorRiskUnavailableError,
    RiskEvaluationNotFoundError,
    RiskInputNotReadyError,
    RiskPolicyNotFoundError,
)
from app.investment_optimization.ids import (
    new_frontier_id,
    new_frontier_selection_id,
    new_risk_evaluation_id,
)
from app.investment_optimization.risk.candidate_generation import generate_candidates
from app.investment_optimization.risk.concentration import concentration_from_shares
from app.investment_optimization.risk.downside import conditional_value_at_risk, outcome_losses
from app.investment_optimization.risk.exposure import (
    exposure_limitations,
    role_c_is_hard_constraint,
)
from app.investment_optimization.risk.frontier import classify_frontier
from app.investment_optimization.risk.models import (
    CandidatePortfolio,
    CandidateShare,
    FeasibilityReceipt,
    FrontierSelection,
    MarketingInvestmentFrontier,
    PortfolioRiskEvaluation,
    RiskEvaluationPolicy,
    RiskNeutralParityReceipt,
)
from app.investment_optimization.risk.parity import build_parity_receipt
from app.investment_optimization.risk.policies import pin_risk_policy
from app.investment_optimization.risk.posterior import (
    expected_outcome,
    median_outcome,
    probability_improvement,
)
from app.investment_optimization.risk.selection import select_candidate
from app.investment_optimization.risk.stability import stability_from_shares
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.exposure_guardrails import ExposureGuardrailQualificationReceipt
from app.investment_planning.exposure_handoff import ExposureRiskHandoff
from app.investment_planning.fingerprint import metadata_fingerprint


class RiskFrontierService:
    def __init__(self, store: OptimizationMetadataStore) -> None:
        self._store = store
        self._shares: dict[str, tuple[CandidateShare, ...]] = {}
        self._receipts: dict[str, FeasibilityReceipt] = {}

    def create_policy(self, **kwargs: object) -> RiskEvaluationPolicy:
        policy = pin_risk_policy(**kwargs)  # type: ignore[arg-type]
        existing = self._store.get_risk_policy_by_fingerprint(
            tenant_id=policy.tenant_id,
            project_id=policy.project_id,
            policy_fingerprint=policy.policy_fingerprint,
        )
        if existing is not None:
            return existing
        stored = self._store.put(policy)
        assert isinstance(stored, RiskEvaluationPolicy)
        return stored

    def get_policy(self, policy_id: str) -> RiskEvaluationPolicy:
        policy = self._store.get_risk_policy(policy_id)
        if policy is None:
            raise RiskPolicyNotFoundError("Risk evaluation policy was not found.")
        return policy

    def generate(
        self,
        *,
        policy: RiskEvaluationPolicy,
        native_shares: tuple[CandidateShare, ...],
        optimization_run_id: str,
        base_approved_plan_ref: str,
        input_fingerprint: str,
    ) -> tuple[CandidatePortfolio, ...]:
        created = []
        for candidate, receipt, shares in generate_candidates(
            tenant_id=policy.tenant_id,
            project_id=policy.project_id,
            policy=policy,
            native_shares=native_shares,
            optimization_run_id=optimization_run_id,
            base_approved_plan_ref=base_approved_plan_ref,
            model_version_ref=policy.model_version_ref,
            assumption_set_ref=policy.future_assumption_set_ref,
            constraint_set_ref=policy.constraint_set_ref,
            input_fingerprint=input_fingerprint,
        ):
            existing = self._store.get_candidate_by_fingerprint(
                tenant_id=candidate.tenant_id,
                project_id=candidate.project_id,
                candidate_fingerprint=candidate.candidate_fingerprint,
            )
            if existing is not None:
                self._shares[existing.candidate_portfolio_id] = shares
                created.append(existing)
                continue
            self._store.put(candidate)
            self._shares[candidate.candidate_portfolio_id] = shares
            self._receipts[receipt.receipt_id] = receipt
            created.append(candidate)
        return tuple(created)

    def get_candidate(self, candidate_id: str) -> CandidatePortfolio:
        candidate = self._store.get_candidate(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError("Candidate portfolio was not found.")
        return candidate

    def evaluate(
        self,
        *,
        policy: RiskEvaluationPolicy,
        candidate: CandidatePortfolio,
        baseline_shares: tuple[CandidateShare, ...],
        candidate_draws: tuple[float, ...] | None,
        baseline_draws: tuple[float, ...] | None,
        handoff: ExposureRiskHandoff | None = None,
        qualifications: tuple[ExposureGuardrailQualificationReceipt, ...] = (),
    ) -> PortfolioRiskEvaluation:
        shares = self._shares.get(candidate.candidate_portfolio_id)
        if shares is None:
            raise RiskInputNotReadyError("Candidate allocation shares are not loaded.")
        limitations: list[str] = []
        expected = median = improvement = tail = None
        posterior_refs: tuple[str, ...] = ()
        if candidate_draws is None or baseline_draws is None:
            limitations.append("POSTERIOR_RISK_UNAVAILABLE")
            if RiskTaxonomyClass.POSTERIOR in policy.evaluation_dimensions:
                raise PosteriorRiskUnavailableError(
                    "Posterior draws are unavailable; missing posterior is not zero risk."
                )
        else:
            losses = outcome_losses(
                baseline_outcomes=baseline_draws, candidate_outcomes=candidate_draws
            )
            expected = expected_outcome(candidate_draws)
            median = median_outcome(candidate_draws)
            improvement = probability_improvement(
                candidate_outcomes=candidate_draws, baseline_outcomes=baseline_draws
            )
            tail = conditional_value_at_risk(losses, tail_probability=policy.tail_probability)
            posterior_refs = ("posterior_fixture",)
        if role_c_is_hard_constraint(qualifications):
            raise ExposureRiskNotQualifiedError(
                "Role C exposure evidence cannot be promoted to a hard constraint."
            )
        limitations.extend(exposure_limitations(handoff, qualifications=qualifications))
        evaluation_id = new_risk_evaluation_id()
        created = datetime.now(UTC)
        evaluation = PortfolioRiskEvaluation(
            portfolio_risk_evaluation_id=evaluation_id,
            candidate_portfolio_id=candidate.candidate_portfolio_id,
            baseline_portfolio_ref=candidate.base_approved_plan_ref,
            risk_evaluation_policy_ref=policy.risk_evaluation_policy_id,
            expected_outcome=expected,
            median_outcome=median,
            probability_improvement=improvement,
            lower_tail_metric=tail,
            posterior_risk_refs=posterior_refs,
            exposure_delivery_risk_refs=(
                () if handoff is None else (handoff.handoff_id,)
            ),
            concentration_metrics=(
                concentration_from_shares(shares, dimension=ConcentrationDimension.CHANNEL),
            ),
            stability_metrics=(
                stability_from_shares(
                    candidate=shares,
                    baseline=baseline_shares,
                    baseline_kind=policy.baseline_kind,
                ),
            ),
            limitations=tuple(dict.fromkeys(limitations)),
            evaluation_fingerprint=metadata_fingerprint(
                {
                    "candidate": candidate.candidate_fingerprint,
                    "policy": policy.policy_fingerprint,
                    "expected": expected,
                    "tail": tail,
                    "limitations": limitations,
                }
            ),
            created_at=created,
        )
        existing = self._store.get_evaluation_by_fingerprint(
            evaluation_fingerprint=evaluation.evaluation_fingerprint
        )
        if existing is not None:
            return existing
        stored = self._store.put(evaluation)
        assert isinstance(stored, PortfolioRiskEvaluation)
        return stored

    def evaluations_for_candidates(
        self, candidate_ids: tuple[str, ...]
    ) -> tuple[PortfolioRiskEvaluation, ...]:
        found: list[PortfolioRiskEvaluation] = []
        for candidate_id in candidate_ids:
            match = self._store.get_evaluation_for_candidate(candidate_id)
            if match is not None:
                found.append(match)
        return tuple(found)

    def get_evaluation(self, evaluation_id: str) -> PortfolioRiskEvaluation:
        evaluation = self._store.get_evaluation(evaluation_id)
        if evaluation is None:
            raise RiskEvaluationNotFoundError("Portfolio risk evaluation was not found.")
        return evaluation

    def build_frontier(
        self,
        *,
        policy: RiskEvaluationPolicy,
        evaluations: tuple[PortfolioRiskEvaluation, ...],
        parity: RiskNeutralParityReceipt | None,
    ) -> MarketingInvestmentFrontier:
        non_dominated, dominated = classify_frontier(
            evaluations, policy=policy.dominance_policy
        )
        created = datetime.now(UTC)
        frontier_id = new_frontier_id()
        frontier = MarketingInvestmentFrontier(
            frontier_id=frontier_id,
            tenant_id=policy.tenant_id,
            project_id=policy.project_id,
            risk_evaluation_policy_id=policy.risk_evaluation_policy_id,
            policy_fingerprint=policy.policy_fingerprint,
            evaluated_candidate_ids=tuple(
                item.candidate_portfolio_id for item in evaluations
            ),
            non_dominated_candidate_ids=non_dominated,
            dominated=dominated,
            readiness=RiskFrontierReadinessStatus.RISK_FRONTIER_READY,
            parity_receipt_id=None if parity is None else parity.parity_receipt_id,
            fingerprint=metadata_fingerprint(
                {
                    "policy": policy.policy_fingerprint,
                    "evaluated": [item.evaluation_fingerprint for item in evaluations],
                    "non_dominated": list(non_dominated),
                }
            ),
            created_at=created,
        )
        existing = self._store.get_frontier_by_fingerprint(fingerprint=frontier.fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(frontier)
        assert isinstance(stored, MarketingInvestmentFrontier)
        return stored

    def get_frontier(self, frontier_id: str) -> MarketingInvestmentFrontier:
        frontier = self._store.get_frontier(frontier_id)
        if frontier is None:
            raise FrontierNotFoundError("Marketing investment frontier was not found.")
        return frontier

    def select(
        self,
        *,
        frontier: MarketingInvestmentFrontier,
        evaluations: tuple[PortfolioRiskEvaluation, ...],
        policy: RiskEvaluationPolicy,
        posture: RiskPosture,
        native_candidate: CandidatePortfolio | None = None,
        candidates: tuple[CandidatePortfolio, ...] = (),
    ) -> tuple[FrontierSelection, RiskNeutralParityReceipt | None]:
        if posture is not RiskPosture.EXPECTED_OUTCOME and not policy.risk_penalties_enabled:
            raise FrontierSelectionNotAllowedError(
                "Risk-neutral policy only authorizes EXPECTED_OUTCOME selection."
            )
        chosen = select_candidate(
            frontier=frontier,
            evaluations=evaluations,
            posture=posture,
            conservative_expected_floor_ratio=policy.conservative_expected_floor_ratio,
            balanced_keys=policy.balanced_keys,
        )
        selected = next(
            item
            for item in candidates
            if item.candidate_portfolio_id == chosen.candidate_portfolio_id
        )
        parity = None
        if not policy.risk_penalties_enabled:
            if native_candidate is None:
                raise FrontierSelectionNotAllowedError(
                    "Risk-neutral selection requires the native Meridian candidate."
                )
            parity = build_parity_receipt(
                tenant_id=policy.tenant_id,
                project_id=policy.project_id,
                policy=policy,
                native_candidate=native_candidate,
                selected_candidate=selected,
            )
            self._store.put(parity)
        created = datetime.now(UTC)
        selection = FrontierSelection(
            selection_id=new_frontier_selection_id(),
            frontier_id=frontier.frontier_id,
            selected_candidate_ref=selected.candidate_portfolio_id,
            risk_posture=posture,
            selection_policy=policy.policy_fingerprint,
            selection_rationale_refs=(chosen.portfolio_risk_evaluation_id,),
            limitations=chosen.limitations,
            state=FrontierSelectionState.MODEL_RECOMMENDED,
            selection_fingerprint=metadata_fingerprint(
                {
                    "frontier": frontier.fingerprint,
                    "candidate": selected.candidate_fingerprint,
                    "posture": posture.value,
                    "policy": policy.policy_fingerprint,
                }
            ),
            created_at=created,
        )
        existing = self._store.get_selection_by_fingerprint(
            selection_fingerprint=selection.selection_fingerprint
        )
        if existing is not None:
            return existing, parity
        stored = self._store.put(selection)
        assert isinstance(stored, FrontierSelection)
        return stored, parity

    def get_selection(self, selection_id: str) -> FrontierSelection:
        selection = self._store.get_selection(selection_id)
        if selection is None:
            raise FrontierSelectionNotFoundError("Frontier selection was not found.")
        return selection

    def get_parity(self, parity_receipt_id: str) -> RiskNeutralParityReceipt:
        receipt = self._store.get_parity_receipt(parity_receipt_id)
        if receipt is None:
            raise ParityReceiptNotFoundError("Risk-neutral parity receipt was not found.")
        return receipt

    def shares_for(self, candidate_id: str) -> tuple[CandidateShare, ...]:
        shares = self._shares.get(candidate_id)
        if shares is None:
            raise RiskInputNotReadyError("Candidate allocation shares are not loaded.")
        return shares
