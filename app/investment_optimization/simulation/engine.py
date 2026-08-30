"""Deterministic Monte Carlo engine. Orchestration stays in the service/worker."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.enums import (
    SIMULATION_ENGINE_VERSION,
    OutcomeEvaluatorKind,
    SimulationRunStatus,
)
from app.investment_optimization.errors import SimulationCandidateInvalidError
from app.investment_optimization.ids import (
    new_outcome_distribution_id,
    new_simulation_receipt_id,
)
from app.investment_optimization.risk.downside import outcome_losses
from app.investment_optimization.risk.models import CandidatePortfolio, CandidateShare
from app.investment_optimization.simulation.artifacts import draw_object_name
from app.investment_optimization.simulation.models import (
    MonteCarloSimulationPolicy,
    MonteCarloSimulationReceipt,
    PortfolioOutcomeDistribution,
    ScenarioCorrelationSpec,
    ScenarioDistributionSet,
    SimulationDrawArtifact,
    SimulationRun,
    SimulationRunSpec,
)
from app.investment_optimization.simulation.outcomes import (
    evaluate_planning_economics,
    evaluator_version,
    require_posterior_source,
)
from app.investment_optimization.simulation.sampling import batch_seed, sample_distribution_set
from app.investment_optimization.simulation.summaries import summarize_outcomes
from app.investment_planning.fingerprint import metadata_fingerprint


def _share_map(shares: tuple[CandidateShare, ...]) -> dict[str, float]:
    return {line.channel_id: line.share for line in shares}


def run_engine(
    *,
    run: SimulationRun,
    spec: SimulationRunSpec,
    policy: MonteCarloSimulationPolicy,
    distribution_set: ScenarioDistributionSet,
    correlation: ScenarioCorrelationSpec,
    candidates: tuple[CandidatePortfolio, ...],
    share_lookup: dict[str, tuple[CandidateShare, ...]],
    baseline_shares: tuple[CandidateShare, ...],
    baseline_kpi: float = 100.0,
) -> tuple[
    tuple[PortfolioOutcomeDistribution, ...],
    tuple[SimulationDrawArtifact, ...],
    MonteCarloSimulationReceipt,
]:
    if policy.outcome_evaluator is OutcomeEvaluatorKind.ACCEPTED_POSTERIOR_EVALUATION:
        require_posterior_source(posterior_artifact_ref=spec.posterior_artifact_ref)
    for candidate in candidates:
        if not candidate.feasibility_receipt_id or not candidate.candidate_fingerprint:
            raise SimulationCandidateInvalidError("Candidate lineage or fingerprint is invalid.")
        if candidate.candidate_portfolio_id not in share_lookup:
            raise SimulationCandidateInvalidError("Candidate allocation shares are not loaded.")
    draws, truncations = sample_distribution_set(
        distribution_set,
        correlation,
        seed=policy.random_seed,
        count=policy.number_of_draws,
    )
    created = datetime.now(UTC)
    distributions: list[PortfolioOutcomeDistribution] = []
    artifacts: list[SimulationDrawArtifact] = []
    batches = max(1, (policy.number_of_draws + policy.batch_size - 1) // policy.batch_size)
    for candidate in candidates:
        shares = _share_map(share_lookup[candidate.candidate_portfolio_id])
        candidate_outcomes: list[float] = []
        baseline_outcomes: list[float] = []
        for index in range(policy.number_of_draws):
            realizations = {key: float(values[index]) for key, values in draws.items()}
            candidate_outcomes.append(
                evaluate_planning_economics(
                    shares=shares,
                    realizations=realizations,
                    variables=distribution_set.variables,
                    baseline_kpi=baseline_kpi,
                )
            )
            baseline_outcomes.append(
                evaluate_planning_economics(
                    shares=_share_map(baseline_shares),
                    realizations=realizations,
                    variables=distribution_set.variables,
                    baseline_kpi=baseline_kpi,
                )
            )
        cand = tuple(candidate_outcomes)
        base = tuple(baseline_outcomes)
        summary = summarize_outcomes(
            candidate_outcomes=cand,
            baseline_outcomes=base,
            tail_probability=policy.tail_probability,
        )
        losses = outcome_losses(baseline_outcomes=base, candidate_outcomes=cand)
        artifact = SimulationDrawArtifact(
            simulation_run_id=run.simulation_run_id,
            candidate_portfolio_id=candidate.candidate_portfolio_id,
            draw_count=policy.number_of_draws,
            candidate_outcomes=cand,
            baseline_outcomes=base,
            losses=losses,
            fingerprint=metadata_fingerprint({"candidate": cand, "baseline": base}),
        )
        artifacts.append(artifact)
        object_name = draw_object_name(
            run.simulation_run_id, candidate.candidate_portfolio_id
        )
        distributions.append(
            PortfolioOutcomeDistribution(
                portfolio_outcome_distribution_id=new_outcome_distribution_id(),
                simulation_run_id=run.simulation_run_id,
                candidate_portfolio_id=candidate.candidate_portfolio_id,
                outcome_unit=policy.outcome_unit,
                draw_count=policy.number_of_draws,
                mean=float(summary["mean"]),
                median=float(summary["median"]),
                quantiles=dict(summary["quantiles"]),  # type: ignore[arg-type]
                probability_vs_baseline=summary["probability_vs_baseline"],  # type: ignore[arg-type]
                tail_metric_refs=(evaluator_version(policy.outcome_evaluator),),
                lower_tail_metric=summary["lower_tail_metric"],  # type: ignore[arg-type]
                distribution_artifact_ref=object_name,
                distribution_fingerprint=artifact.fingerprint,
                limitations=truncations,
                created_at=created,
            )
        )
    simulation_fingerprint = metadata_fingerprint(
        {
            "input": spec.input_fingerprint,
            "engine": SIMULATION_ENGINE_VERSION,
            "seed": policy.random_seed,
            "draws": policy.number_of_draws,
            "artifacts": [item.fingerprint for item in artifacts],
        }
    )
    receipt = MonteCarloSimulationReceipt(
        receipt_id=new_simulation_receipt_id(),
        simulation_run_id=run.simulation_run_id,
        tenant_id=run.tenant_id,
        project_id=run.project_id,
        status=SimulationRunStatus.COMPLETE,
        draw_count=policy.number_of_draws,
        effective_draw_count=policy.number_of_draws,
        batch_count=batches,
        engine_version=SIMULATION_ENGINE_VERSION,
        input_fingerprint=spec.input_fingerprint,
        simulation_fingerprint=simulation_fingerprint,
        outcome_distribution_ids=tuple(
            item.portfolio_outcome_distribution_id for item in distributions
        ),
        limitations=truncations,
        warnings=(),
        created_at=created,
    )
    _ = batch_seed(parent_seed=policy.random_seed, batch_index=0)
    return tuple(distributions), tuple(artifacts), receipt
