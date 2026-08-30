"""Assemble exposure-risk evidence for a Marketing Investment Portfolio."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.contracts import ModelConsumptionContract
from app.investment_planning.contracts import ActualSpendAllocation
from app.investment_planning.enums import ExposureOptimizationRole
from app.investment_planning.errors import ExposureSourceNotReadyError
from app.investment_planning.exposure_actuals import (
    actual_spend_unchanged,
    high_spend_low_quality_flags,
)
from app.investment_planning.exposure_evidence import (
    DeliveryHealthEvidence,
    compile_delivery_health_evidence,
    default_exposure_risk_policy,
)
from app.investment_planning.exposure_guardrails import (
    ExposureGuardrail,
    ExposureGuardrailQualificationReceipt,
)
from app.investment_planning.exposure_handoff import (
    ExposureRiskHandoff,
    compile_p6_09_handoff,
    proposal_exposure_limitations,
)
from app.investment_planning.exposure_observations import (
    ExposureMetricObservation,
    ExposureObservationSource,
    ProductionExposureObservationAdapter,
    normalize_observation,
)
from app.investment_planning.exposure_profile import (
    PortfolioExposureCoverage,
    PortfolioExposureRiskProfile,
    assemble_exposure_profile,
    compute_exposure_coverage,
)
from app.investment_planning.exposure_qualify import qualify_exposure_guardrail
from app.investment_planning.exposure_scenarios import (
    ExposureRiskScenario,
    pin_exposure_risk_scenario,
)
from app.investment_planning.store import InvestmentPlanningMetadataStore


class ExposureRiskService:
    """Interprets delivery/exposure as portfolio risk evidence. Not provider truth."""

    def __init__(
        self,
        store: InvestmentPlanningMetadataStore,
        *,
        observations: ExposureObservationSource | None = None,
    ) -> None:
        self._store = store
        self._observations = observations or ProductionExposureObservationAdapter()

    def load_observations(
        self,
        *,
        tenant_id: str,
        project_id: str,
        period: str,
        known_market_ids: frozenset[str] | set[str],
        known_campaign_ids: frozenset[str] | set[str] | None = None,
    ) -> tuple[ExposureMetricObservation, ...]:
        try:
            raw = self._observations.fetch_observations(
                tenant_id=tenant_id, project_id=project_id, period=period
            )
        except ExposureSourceNotReadyError:
            return ()
        return tuple(
            normalize_observation(
                item,
                known_market_ids=known_market_ids,
                known_campaign_ids=known_campaign_ids,
            )
            for item in raw
        )

    def assemble_profile(
        self,
        *,
        tenant_id: str,
        project_id: str,
        period: str,
        known_market_ids: frozenset[str] | set[str],
        known_channel_ids: frozenset[str] | set[str],
        known_campaign_ids: frozenset[str] | set[str] | None = None,
        allocations: tuple[ActualSpendAllocation, ...] = (),
        consumption: ModelConsumptionContract | None = None,
        market_id: str | None = None,
        channel_id: str | None = None,
        campaign_id: str | None = None,
        portfolio_snapshot_id: str | None = None,
    ) -> tuple[PortfolioExposureRiskProfile, DeliveryHealthEvidence, PortfolioExposureCoverage]:
        del consumption
        now = datetime.now(UTC)
        policy = default_exposure_risk_policy(created_at=now)
        observations = self.load_observations(
            tenant_id=tenant_id,
            project_id=project_id,
            period=period,
            known_market_ids=known_market_ids,
            known_campaign_ids=known_campaign_ids,
        )
        if market_id:
            observations = tuple(item for item in observations if item.market_id == market_id)
        if channel_id:
            observations = tuple(item for item in observations if item.channel_id == channel_id)
        evidence = compile_delivery_health_evidence(
            project_id=project_id,
            period=period,
            observations=observations,
            policy=policy,
            created_at=now,
        )
        extra = high_spend_low_quality_flags(
            allocations=actual_spend_unchanged(allocations),
            observations=observations,
            evidence=evidence,
        )
        if extra:
            evidence = evidence.model_copy(update={"flags": evidence.flags + extra})
        coverage = compute_exposure_coverage(
            project_id=project_id,
            period=period,
            observations=observations,
            known_market_ids=known_market_ids,
            known_channel_ids=known_channel_ids,
        )
        profile = assemble_exposure_profile(
            project_id=project_id,
            period=period,
            evidence=evidence,
            coverage=coverage,
            created_at=now,
            portfolio_snapshot_id=portfolio_snapshot_id,
            market_id=market_id,
            channel_id=channel_id,
            campaign_id=campaign_id,
            role_eligibility=(ExposureOptimizationRole.SCENARIO_OR_REVIEW_GUARDRAIL,),
        )
        self._store.put(profile)
        self._store.put(coverage)
        self._store.put(evidence)
        return profile, evidence, coverage

    def qualify(
        self,
        guardrail: ExposureGuardrail,
        *,
        tenant_id: str,
        project_id: str,
        period: str,
        known_market_ids: frozenset[str] | set[str],
        consumption: ModelConsumptionContract | None = None,
    ) -> ExposureGuardrailQualificationReceipt:
        now = datetime.now(UTC)
        policy = default_exposure_risk_policy(created_at=now)
        observations = self.load_observations(
            tenant_id=tenant_id,
            project_id=project_id,
            period=period,
            known_market_ids=known_market_ids,
        )
        receipt = qualify_exposure_guardrail(
            guardrail,
            observations=observations,
            policy=policy,
            known_market_ids=known_market_ids,
            consumption=consumption,
            created_at=now,
        )
        self._store.put(receipt)
        self._store.put(guardrail)
        return receipt

    def create_scenario(
        self,
        *,
        project_id: str,
        period: str,
        scope: str,
        source_rationale: str,
        assumptions: tuple[tuple[str, str, str, str], ...],
    ) -> ExposureRiskScenario:
        scenario = pin_exposure_risk_scenario(
            project_id=project_id,
            period=period,
            scope=scope,
            source_rationale=source_rationale,
            assumptions=assumptions,
            created_at=datetime.now(UTC),
        )
        self._store.put(scenario)
        return scenario

    def p6_09_handoff(
        self,
        *,
        profile: PortfolioExposureRiskProfile,
        qualifications: tuple[ExposureGuardrailQualificationReceipt, ...] = (),
        scenarios: tuple[ExposureRiskScenario, ...] = (),
    ) -> ExposureRiskHandoff:
        handoff = compile_p6_09_handoff(
            profile=profile,
            qualifications=qualifications,
            scenarios=scenarios,
            created_at=datetime.now(UTC),
        )
        self._store.put(handoff)
        return handoff

    def proposal_limitations(self, profile: PortfolioExposureRiskProfile):
        return proposal_exposure_limitations(profile)
