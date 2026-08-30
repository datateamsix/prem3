"""Bounded distribution families. No silent invented parameters."""

from __future__ import annotations

import math

import numpy as np
from numpy.random import Generator

from app.investment_optimization.enums import (
    DistributionAuthority,
    DistributionFamily,
    SimulationSemanticType,
)
from app.investment_optimization.errors import ScenarioDistributionNotGovernedError
from app.investment_optimization.ids import new_scenario_variable_id
from app.investment_optimization.simulation.models import ScenarioVariableDistribution
from app.investment_planning.fingerprint import metadata_fingerprint

_RATE_TYPES = {
    SimulationSemanticType.VIEWABILITY,
    SimulationSemanticType.IVT,
    SimulationSemanticType.IN_TARGET_RATE,
    SimulationSemanticType.REACH_EFFICIENCY,
    SimulationSemanticType.INVENTORY_QUALITY,
}
_POSITIVE_TYPES = {
    SimulationSemanticType.FUTURE_CPM,
    SimulationSemanticType.COST_PER_MEDIA_UNIT,
    SimulationSemanticType.CONVERSION_VALUE,
    SimulationSemanticType.DEMAND_MULTIPLIER,
    SimulationSemanticType.CHANNEL_MULTIPLIER,
}


def _param(variable: ScenarioVariableDistribution, name: str) -> float:
    raw = variable.parameters.get(name)
    if raw is None or isinstance(raw, tuple):
        raise ScenarioDistributionNotGovernedError(f"{variable.family} requires parameter {name}.")
    return float(raw)


def validate_variable(variable: ScenarioVariableDistribution) -> None:
    if not variable.source_authority or not variable.source_refs:
        raise ScenarioDistributionNotGovernedError(
            "Every distribution requires explicit authority and source refs."
        )
    if variable.approval_state not in {"APPROVED", "PINNED", "GOVERNED"}:
        raise ScenarioDistributionNotGovernedError("Distribution approval_state is not governed.")
    family = variable.family
    if family is DistributionFamily.FIXED:
        _param(variable, "value")
    elif family is DistributionFamily.NORMAL:
        if _param(variable, "std") <= 0:
            raise ScenarioDistributionNotGovernedError("NORMAL std must be positive.")
        _param(variable, "mean")
    elif family is DistributionFamily.LOGNORMAL:
        if _param(variable, "sigma") <= 0:
            raise ScenarioDistributionNotGovernedError("LOGNORMAL sigma must be positive.")
        _param(variable, "mean")
    elif family is DistributionFamily.TRIANGULAR:
        low, mode, high = (
            _param(variable, "low"),
            _param(variable, "mode"),
            _param(variable, "high"),
        )
        if not low <= mode <= high or low == high:
            raise ScenarioDistributionNotGovernedError("TRIANGULAR requires low <= mode <= high.")
    elif family is DistributionFamily.BETA:
        if _param(variable, "a") <= 0 or _param(variable, "b") <= 0:
            raise ScenarioDistributionNotGovernedError("BETA a and b must be positive.")
    elif family is DistributionFamily.DISCRETE:
        values = variable.parameters.get("values")
        weights = variable.parameters.get("weights")
        if not isinstance(values, tuple) or not isinstance(weights, tuple):
            raise ScenarioDistributionNotGovernedError(
                "DISCRETE requires values and weights tuples."
            )
        if len(values) != len(weights) or not values:
            raise ScenarioDistributionNotGovernedError("DISCRETE values and weights must align.")
        if any(weight < 0 for weight in weights) or math.isclose(sum(weights), 0.0):
            raise ScenarioDistributionNotGovernedError("DISCRETE weights must be non-negative.")
    elif family is DistributionFamily.EMPIRICAL:
        if len(variable.empirical_samples) < 2:
            raise ScenarioDistributionNotGovernedError(
                "EMPIRICAL sampling requires a pinned sample population."
            )
    else:
        raise ScenarioDistributionNotGovernedError(f"Unsupported distribution family {family}.")


def _apply_domain(
    values: np.ndarray, variable: ScenarioVariableDistribution
) -> tuple[np.ndarray, bool]:
    truncated = False
    lower = variable.lower_bound
    upper = variable.upper_bound
    if variable.semantic_type in _POSITIVE_TYPES:
        lower = 0.0 if lower is None else max(lower, 0.0)
    if variable.semantic_type in _RATE_TYPES:
        lower = 0.0 if lower is None else max(lower, 0.0)
        upper = 1.0 if upper is None else min(upper, 1.0)
    if lower is not None and np.any(values < lower):
        if not variable.truncate:
            raise ScenarioDistributionNotGovernedError(
                f"{variable.semantic_type} generated values below the governed lower bound."
            )
        values = np.maximum(values, lower)
        truncated = True
    if upper is not None and np.any(values > upper):
        if not variable.truncate:
            raise ScenarioDistributionNotGovernedError(
                f"{variable.semantic_type} generated values above the governed upper bound."
            )
        values = np.minimum(values, upper)
        truncated = True
    return values, truncated


def sample_variable(
    variable: ScenarioVariableDistribution, *, generator: Generator, count: int
) -> tuple[np.ndarray, bool]:
    validate_variable(variable)
    family = variable.family
    if family is DistributionFamily.FIXED:
        draws = np.full(count, _param(variable, "value"), dtype=float)
    elif family is DistributionFamily.NORMAL:
        draws = generator.normal(_param(variable, "mean"), _param(variable, "std"), size=count)
    elif family is DistributionFamily.LOGNORMAL:
        draws = generator.lognormal(_param(variable, "mean"), _param(variable, "sigma"), size=count)
    elif family is DistributionFamily.TRIANGULAR:
        draws = generator.triangular(
            _param(variable, "low"),
            _param(variable, "mode"),
            _param(variable, "high"),
            size=count,
        )
    elif family is DistributionFamily.BETA:
        draws = generator.beta(_param(variable, "a"), _param(variable, "b"), size=count)
    elif family is DistributionFamily.DISCRETE:
        values = np.array(variable.parameters["values"], dtype=float)
        weights = np.array(variable.parameters["weights"], dtype=float)
        probs = weights / weights.sum()
        draws = generator.choice(values, size=count, p=probs)
    else:
        population = np.array(variable.empirical_samples, dtype=float)
        draws = generator.choice(population, size=count, replace=True)
    return _apply_domain(draws, variable)


def pin_variable(
    *,
    semantic_type: SimulationSemanticType,
    family: DistributionFamily,
    parameters: dict[str, float | tuple[float, ...]],
    source_authority: DistributionAuthority,
    source_refs: tuple[str, ...],
    unit: str = "1",
    scope: str = "portfolio",
    time_scope: str = "FY2027Q1",
    approval_state: str = "APPROVED",
    channel_id: str | None = None,
    empirical_samples: tuple[float, ...] = (),
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    truncate: bool = False,
) -> ScenarioVariableDistribution:
    variable_id = new_scenario_variable_id()
    payload = {
        "semantic_type": semantic_type.value,
        "family": family.value,
        "parameters": parameters,
        "source_authority": source_authority.value,
        "source_refs": list(source_refs),
        "channel_id": channel_id or "",
        "empirical_samples": list(empirical_samples),
    }
    variable = ScenarioVariableDistribution(
        variable_id=variable_id,
        semantic_type=semantic_type,
        scope=scope,
        unit=unit,
        time_scope=time_scope,
        channel_id=channel_id,
        family=family,
        parameters=parameters,
        empirical_samples=empirical_samples,
        source_authority=source_authority,
        source_refs=source_refs,
        approval_state=approval_state,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        truncate=truncate,
        fingerprint=metadata_fingerprint(payload),
    )
    validate_variable(variable)
    return variable
