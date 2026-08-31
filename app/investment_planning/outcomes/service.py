"""Idempotent P6-10 outcome orchestration. HTTP does not invent numbers."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.investment_optimization.contracts import (
    PlanningDecisionRecord,
    ProposalDecisionReceipt,
)
from app.investment_optimization.enums import ExperienceBoundary
from app.investment_optimization.errors import (
    DecisionSourceNotReadyError,
    OutcomeRecordNotFoundError,
)
from app.investment_optimization.risk.models import CandidateShare, FrontierSelection
from app.investment_optimization.store import OptimizationMetadataStore
from app.investment_planning.outcomes.decision import bind_investment_decision
from app.investment_planning.outcomes.execution_adherence import compute_execution_adherence
from app.investment_planning.outcomes.learning import emit_learning_receipt
from app.investment_planning.outcomes.models import (
    DecisionOutcomeLearningReceipt,
    DecisionOutcomeObservation,
    ExecutionAdherence,
    InvestmentDecisionRecord,
    PredictionErrorSummary,
    PredictionEvidenceSet,
    RecommendationAdherence,
    RecommendationOutcomeReceipt,
)
from app.investment_planning.outcomes.observations import pin_outcome_observation
from app.investment_planning.outcomes.prediction import (
    compute_prediction_error,
    pin_prediction_evidence,
)
from app.investment_planning.outcomes.receipts import close_outcome_receipt
from app.investment_planning.outcomes.recommendation_adherence import (
    compute_recommendation_adherence,
)


class _ProjectScoped(Protocol):
    @property
    def project_id(self) -> str: ...


class _TenantScoped(_ProjectScoped, Protocol):
    @property
    def tenant_id(self) -> str: ...


def _owned[T: _TenantScoped](item: T | None, *, tenant_id: str, project_id: str, message: str) -> T:
    """Return the record only when the caller's workspace owns it.

    A record owned by another workspace is reported as not found, so the read
    path cannot be used as an existence oracle for foreign identifiers.
    """
    if item is None or item.tenant_id != tenant_id or item.project_id != project_id:
        raise OutcomeRecordNotFoundError(message)
    return item


def _owned_by_project[T: _ProjectScoped](item: T | None, *, project_id: str, message: str) -> T:
    """Scope a record that carries a project but no tenant of its own."""
    if item is None or item.project_id != project_id:
        raise OutcomeRecordNotFoundError(message)
    return item


class OutcomeService:
    def __init__(self, store: OptimizationMetadataStore) -> None:
        self._store = store

    def bind_decision_from_ids(
        self,
        *,
        tenant_id: str,
        project_id: str,
        proposal_decision_receipt_id: str,
        planning_decision_record_id: str,
        frontier_selection_id: str | None = None,
        recommended_portfolio_ref: str | None = None,
        decided_portfolio_ref: str | None = None,
        recommended_shares: tuple[CandidateShare, ...] | None = None,
        decided_shares: tuple[CandidateShare, ...] | None = None,
    ) -> InvestmentDecisionRecord:
        receipt = self._store.get_decision_receipt(proposal_decision_receipt_id)
        ledger = self._store.get_decision_record(planning_decision_record_id)
        if receipt is None or ledger is None:
            raise DecisionSourceNotReadyError(
                "P6-06 decision receipt and ledger must exist before outcome bind."
            )
        selection = None
        if frontier_selection_id:
            selection = self._store.get_selection(frontier_selection_id)
            if selection is None:
                raise DecisionSourceNotReadyError("Frontier selection was not found.")
        return self.bind_decision(
            tenant_id=tenant_id,
            project_id=project_id,
            receipt=receipt,
            ledger=ledger,
            frontier_selection=selection,
            recommended_portfolio_ref=recommended_portfolio_ref,
            decided_portfolio_ref=decided_portfolio_ref,
            recommended_shares=recommended_shares,
            decided_shares=decided_shares,
        )

    def bind_decision(
        self,
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
        item = bind_investment_decision(
            tenant_id=tenant_id,
            project_id=project_id,
            receipt=receipt,
            ledger=ledger,
            frontier_selection=frontier_selection,
            recommended_portfolio_ref=recommended_portfolio_ref,
            decided_portfolio_ref=decided_portfolio_ref,
            recommended_shares=recommended_shares,
            decided_shares=decided_shares,
        )
        existing = self._store.get_investment_decision_by_fingerprint(
            fingerprint=item.decision_fingerprint
        )
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, InvestmentDecisionRecord)
        return stored

    def create_recommendation_adherence(
        self,
        *,
        tenant_id: str,
        project_id: str,
        investment_decision_ref: str,
        recommended_portfolio_ref: str,
        decided_portfolio_ref: str,
        recommended: tuple[CandidateShare, ...],
        decided: tuple[CandidateShare, ...],
    ) -> RecommendationAdherence:
        item = compute_recommendation_adherence(
            tenant_id=tenant_id,
            project_id=project_id,
            investment_decision_ref=investment_decision_ref,
            recommended_portfolio_ref=recommended_portfolio_ref,
            decided_portfolio_ref=decided_portfolio_ref,
            recommended=recommended,
            decided=decided,
        )
        existing = self._store.get_recommendation_adherence_by_fingerprint(
            fingerprint=item.fingerprint
        )
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, RecommendationAdherence)
        return stored

    def create_execution_adherence(
        self,
        *,
        tenant_id: str,
        project_id: str,
        approved_plan_ref: str,
        planned: dict[str, Decimal | None],
        actual: dict[str, Decimal | None],
        actual_spend_source_ref: str | None = None,
        exposure_handoff_ref: str | None = None,
        require_complete: bool = False,
    ) -> ExecutionAdherence:
        item = compute_execution_adherence(
            tenant_id=tenant_id,
            project_id=project_id,
            approved_plan_ref=approved_plan_ref,
            planned=planned,
            actual=actual,
            actual_spend_source_ref=actual_spend_source_ref,
            exposure_handoff_ref=exposure_handoff_ref,
            require_complete=require_complete,
        )
        existing = self._store.get_execution_adherence_by_fingerprint(fingerprint=item.fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, ExecutionAdherence)
        return stored

    def create_observation(self, **kwargs: object) -> DecisionOutcomeObservation:
        item = pin_outcome_observation(**kwargs)  # type: ignore[arg-type]
        existing = self._store.get_outcome_observation_by_fingerprint(
            fingerprint=item.observation_fingerprint
        )
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, DecisionOutcomeObservation)
        return stored

    def create_prediction_evidence(self, **kwargs: object) -> PredictionEvidenceSet:
        item = pin_prediction_evidence(**kwargs)  # type: ignore[arg-type]
        existing = self._store.get_prediction_evidence_by_fingerprint(fingerprint=item.fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, PredictionEvidenceSet)
        return stored

    def create_prediction_error(
        self,
        *,
        evidence: PredictionEvidenceSet,
        observation: DecisionOutcomeObservation | None,
    ) -> PredictionErrorSummary:
        item = compute_prediction_error(
            evidence=evidence, observation=observation, store=self._store
        )
        existing = self._store.get_prediction_error_by_fingerprint(fingerprint=item.fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, PredictionErrorSummary)
        return stored

    def create_receipt(
        self,
        *,
        tenant_id: str,
        project_id: str,
        decision: InvestmentDecisionRecord,
        prediction: PredictionEvidenceSet | None,
        observation: DecisionOutcomeObservation | None = None,
        recommendation_adherence: RecommendationAdherence | None = None,
        execution_adherence: ExecutionAdherence | None = None,
        prediction_error: PredictionErrorSummary | None = None,
        approved_plan_ref: str | None = None,
        outcome_not_observed: bool = False,
    ) -> RecommendationOutcomeReceipt:
        item = close_outcome_receipt(
            tenant_id=tenant_id,
            project_id=project_id,
            decision=decision,
            prediction=prediction,
            observation=observation,
            recommendation_adherence=recommendation_adherence,
            execution_adherence=execution_adherence,
            prediction_error=prediction_error,
            approved_plan_ref=approved_plan_ref,
            outcome_not_observed=outcome_not_observed,
        )
        existing = self._store.get_outcome_receipt_by_fingerprint(
            fingerprint=item.receipt_fingerprint
        )
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, RecommendationOutcomeReceipt)
        return stored

    def create_learning_receipt(
        self,
        *,
        project_id: str,
        receipt: RecommendationOutcomeReceipt,
        adherence: RecommendationAdherence | None = None,
        error: PredictionErrorSummary | None = None,
        experience_boundary: ExperienceBoundary = ExperienceBoundary.LOCAL_ONLY,
    ) -> DecisionOutcomeLearningReceipt:
        item = emit_learning_receipt(
            project_id=project_id,
            receipt=receipt,
            adherence=adherence,
            error=error,
            experience_boundary=experience_boundary,
        )
        existing = self._store.get_learning_receipt_by_fingerprint(fingerprint=item.fingerprint)
        if existing is not None:
            return existing
        stored = self._store.put(item)
        assert isinstance(stored, DecisionOutcomeLearningReceipt)
        return stored

    def get_decision(
        self, decision_id: str, *, tenant_id: str, project_id: str
    ) -> InvestmentDecisionRecord:
        return _owned(
            self._store.get_investment_decision(decision_id),
            tenant_id=tenant_id,
            project_id=project_id,
            message="Investment decision was not found.",
        )

    def get_recommendation_adherence(
        self, adherence_id: str, *, tenant_id: str, project_id: str
    ) -> RecommendationAdherence:
        return _owned(
            self._store.get_recommendation_adherence(adherence_id),
            tenant_id=tenant_id,
            project_id=project_id,
            message="Recommendation adherence was not found.",
        )

    def get_execution_adherence(
        self, adherence_id: str, *, tenant_id: str, project_id: str
    ) -> ExecutionAdherence:
        return _owned(
            self._store.get_execution_adherence(adherence_id),
            tenant_id=tenant_id,
            project_id=project_id,
            message="Execution adherence was not found.",
        )

    def get_observation(
        self, observation_id: str, *, tenant_id: str, project_id: str
    ) -> DecisionOutcomeObservation:
        del tenant_id  # record carries a project but no tenant of its own
        return _owned_by_project(
            self._store.get_outcome_observation(observation_id),
            project_id=project_id,
            message="Outcome observation was not found.",
        )

    def get_prediction_evidence(
        self, evidence_id: str, *, tenant_id: str, project_id: str
    ) -> PredictionEvidenceSet:
        del tenant_id  # record carries a project but no tenant of its own
        return _owned_by_project(
            self._store.get_prediction_evidence(evidence_id),
            project_id=project_id,
            message="Prediction evidence was not found.",
        )

    def get_prediction_error(
        self, error_id: str, *, tenant_id: str, project_id: str
    ) -> PredictionErrorSummary:
        del tenant_id  # record carries a project but no tenant of its own
        return _owned_by_project(
            self._store.get_prediction_error(error_id),
            project_id=project_id,
            message="Prediction error was not found.",
        )

    def get_receipt(
        self, receipt_id: str, *, tenant_id: str, project_id: str
    ) -> RecommendationOutcomeReceipt:
        return _owned(
            self._store.get_outcome_receipt(receipt_id),
            tenant_id=tenant_id,
            project_id=project_id,
            message="Outcome receipt was not found.",
        )

    def get_learning_receipt(
        self, receipt_id: str, *, tenant_id: str, project_id: str
    ) -> DecisionOutcomeLearningReceipt:
        del tenant_id  # record carries a project but no tenant of its own
        return _owned_by_project(
            self._store.get_learning_receipt(receipt_id),
            project_id=project_id,
            message="Learning receipt was not found.",
        )
