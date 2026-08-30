"""Deterministic seeded sampling. No global process RNG."""

from __future__ import annotations

import numpy as np
from numpy.random import PCG64, Generator, SeedSequence

from app.investment_optimization.enums import CorrelationAuthority
from app.investment_optimization.errors import ScenarioCorrelationInvalidError
from app.investment_optimization.simulation.correlation import apply_iman_conover
from app.investment_optimization.simulation.distributions import sample_variable
from app.investment_optimization.simulation.models import (
    ScenarioCorrelationSpec,
    ScenarioDistributionSet,
)


def parent_generator(seed: int) -> Generator:
    return Generator(PCG64(SeedSequence(int(seed))))


def batch_seed(*, parent_seed: int, batch_index: int) -> int:
    spawned = SeedSequence(int(parent_seed)).spawn(batch_index + 1)[batch_index]
    return int(spawned.generate_state(1, dtype=np.uint32)[0])


def sample_distribution_set(
    distribution_set: ScenarioDistributionSet,
    correlation: ScenarioCorrelationSpec,
    *,
    seed: int,
    count: int,
) -> tuple[dict[str, np.ndarray], tuple[str, ...]]:
    generator = parent_generator(seed)
    columns: list[np.ndarray] = []
    truncated: list[str] = []
    for variable in distribution_set.variables:
        draws, was_truncated = sample_variable(variable, generator=generator, count=count)
        columns.append(draws)
        if was_truncated:
            truncated.append(f"TRUNCATED:{variable.variable_id}")
    stacked = np.column_stack(columns) if columns else np.zeros((count, 0))
    ids = tuple(item.variable_id for item in distribution_set.variables)
    if correlation.authority is not CorrelationAuthority.INDEPENDENT:
        if tuple(correlation.variable_ids) != ids:
            raise ScenarioCorrelationInvalidError(
                "Correlation variable set does not match the distribution set."
            )
        if correlation.authority is CorrelationAuthority.EMPIRICAL_CORRELATION:
            if any(len(item.empirical_samples) < 2 for item in distribution_set.variables):
                raise ScenarioCorrelationInvalidError(
                    "EMPIRICAL_CORRELATION requires compatible pinned numeric samples."
                )
        stacked = apply_iman_conover(stacked, correlation, generator=generator)
    realized = {variable_id: stacked[:, index] for index, variable_id in enumerate(ids)}
    return realized, tuple(truncated)
