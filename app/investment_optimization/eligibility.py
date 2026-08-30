"""Model-variable optimization eligibility. Existence is not eligibility."""

from __future__ import annotations

from app.investment_optimization.contracts import ModelConsumptionVariable
from app.investment_optimization.enums import (
    ORGANIC_CHANNEL_IDS,
    ModelVariableOptimizationEligibility,
    ModelVariableRole,
)


def variable_eligibility(
    variable: ModelConsumptionVariable,
) -> ModelVariableOptimizationEligibility:
    if variable.eligibility is not ModelVariableOptimizationEligibility.OPTIMIZABLE:
        return variable.eligibility
    if variable.variable_role is ModelVariableRole.CONTROL:
        return ModelVariableOptimizationEligibility.CONTROL
    if variable.variable_role is ModelVariableRole.OUTCOME:
        return ModelVariableOptimizationEligibility.OUTCOME
    if variable.variable_role is ModelVariableRole.ORGANIC:
        return ModelVariableOptimizationEligibility.CONTEXT_ONLY
    if variable.variable_role is ModelVariableRole.CONTEXT:
        return ModelVariableOptimizationEligibility.CONTEXT_ONLY
    channel = variable.canonical_channel_id or ""
    if channel in ORGANIC_CHANNEL_IDS:
        return ModelVariableOptimizationEligibility.CONTEXT_ONLY
    if variable.variable_role is ModelVariableRole.MEDIA_SPEND:
        return ModelVariableOptimizationEligibility.OPTIMIZABLE
    return ModelVariableOptimizationEligibility.UNSUPPORTED


def is_budget_optimizable(variable: ModelConsumptionVariable) -> bool:
    return variable_eligibility(variable) is ModelVariableOptimizationEligibility.OPTIMIZABLE
