"""Attribution model registry — assumption models, not benchmarks of truth."""

from __future__ import annotations

from app.modeling.mta.contracts import AttributionModelId, MTAAttributionModelSpec

_REGISTRY: dict[AttributionModelId, MTAAttributionModelSpec] = {
    AttributionModelId.FIRST_TOUCH: MTAAttributionModelSpec(
        model_id=AttributionModelId.FIRST_TOUCH,
        display_name="First Touch",
        assumption="100% of attributed credit to the introducing observed touchpoint.",
        is_heuristic=True,
    ),
    AttributionModelId.LAST_TOUCH: MTAAttributionModelSpec(
        model_id=AttributionModelId.LAST_TOUCH,
        display_name="Last Touch",
        assumption="100% of attributed credit to the final observed touchpoint.",
        is_heuristic=True,
    ),
    AttributionModelId.LAST_NON_DIRECT: MTAAttributionModelSpec(
        model_id=AttributionModelId.LAST_NON_DIRECT,
        display_name="Last Non-Direct",
        assumption="100% of attributed credit to the last non-Direct observed touchpoint.",
        is_heuristic=True,
    ),
    AttributionModelId.LINEAR: MTAAttributionModelSpec(
        model_id=AttributionModelId.LINEAR,
        display_name="Linear",
        assumption="Equal attributed credit across all observed touchpoints on the path.",
        is_heuristic=True,
    ),
    AttributionModelId.TIME_DECAY: MTAAttributionModelSpec(
        model_id=AttributionModelId.TIME_DECAY,
        display_name="Time Decay",
        assumption="Attributed credit increases as the touchpoint nears conversion.",
        is_heuristic=True,
        requires_path_order=True,
    ),
    AttributionModelId.POSITION_BASED: MTAAttributionModelSpec(
        model_id=AttributionModelId.POSITION_BASED,
        display_name="Position Based",
        assumption="Configured position weights assign attributed credit by path position.",
        is_heuristic=True,
        requires_path_order=True,
    ),
    AttributionModelId.MARKOV: MTAAttributionModelSpec(
        model_id=AttributionModelId.MARKOV,
        display_name="Markov",
        assumption=(
            "Attributed credit and removal effects from observed transition structure. "
            "Not causal incrementality."
        ),
        is_heuristic=False,
        requires_path_order=True,
    ),
    AttributionModelId.SHAPLEY: MTAAttributionModelSpec(
        model_id=AttributionModelId.SHAPLEY,
        display_name="Shapley",
        assumption=(
            "Marginal coalition contribution within observed journey combinations. "
            "Not an incremental causal effect."
        ),
        is_heuristic=False,
        requires_path_order=True,
        compute_bounded=True,
    ),
}


def all_model_specs() -> tuple[MTAAttributionModelSpec, ...]:
    return tuple(_REGISTRY[mid] for mid in AttributionModelId)


def get_model_spec(model_id: AttributionModelId) -> MTAAttributionModelSpec:
    return _REGISTRY[model_id]


def default_enabled_models() -> tuple[AttributionModelId, ...]:
    return (
        AttributionModelId.FIRST_TOUCH,
        AttributionModelId.LAST_TOUCH,
        AttributionModelId.LAST_NON_DIRECT,
        AttributionModelId.LINEAR,
        AttributionModelId.TIME_DECAY,
        AttributionModelId.POSITION_BASED,
        AttributionModelId.MARKOV,
        AttributionModelId.SHAPLEY,
    )
