"""MTAExecutionPlan compile and fingerprint."""

from __future__ import annotations

from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta import ADAPTER_VERSION, DP6_MAM_PINNED_VERSION
from app.modeling.mta.contracts import (
    AttributionModelId,
    MTAInputContract,
    ShapleyPreflight,
    ShapleyPreflightState,
)
from app.modeling.mta.runtime_contracts import (
    ModelParameterSet,
    MTAAnalysisConfig,
    MTAExecutionPlan,
    MTAInputMode,
    MTAModelRequirement,
)


def default_model_parameters(
    models: tuple[AttributionModelId, ...] | list[AttributionModelId],
    *,
    analysis_params: dict[str, Any] | None = None,
) -> tuple[ModelParameterSet, ...]:
    analysis_params = analysis_params or {}
    out: list[ModelParameterSet] = []
    for model_id in models:
        req = (
            MTAModelRequirement.OPTIONAL
            if model_id is AttributionModelId.SHAPLEY
            else MTAModelRequirement.REQUIRED
        )
        params: dict[str, Any] = {}
        if model_id is AttributionModelId.TIME_DECAY:
            params = {
                "decay_over_time": analysis_params.get("decay_over_time", 7),
                "frequency": analysis_params.get("frequency", 2),
            }
        elif model_id is AttributionModelId.POSITION_BASED:
            params = {
                "first_weight": analysis_params.get("first_weight", 0.4),
                "middle_weight": analysis_params.get("middle_weight", 0.2),
                "last_weight": analysis_params.get("last_weight", 0.4),
            }
            total = params["first_weight"] + params["middle_weight"] + params["last_weight"]
            if abs(total - 1.0) > 1e-9:
                raise ValueError("POSITION_BASED weights must sum to 1.0")
        elif model_id is AttributionModelId.MARKOV:
            params = {
                "transition_to_same_state": analysis_params.get(
                    "transition_to_same_state", False
                ),
                "conversion_value_as_frequency": analysis_params.get(
                    "conversion_value_as_frequency", True
                ),
            }
        elif model_id is AttributionModelId.SHAPLEY:
            params = {
                "size": analysis_params.get("shapley_size", 4),
                "order": analysis_params.get("shapley_order", True),
                "values_col": analysis_params.get("values_col", "conversions"),
            }
        out.append(
            ModelParameterSet(model_id=model_id, requirement=req, parameters=params)
        )
    return tuple(out)


def build_analysis_config(
    contract: MTAInputContract,
    *,
    channel_registry_version: int,
    channel_grouping_version: int,
    model_parameters: dict[str, Any] | None = None,
) -> MTAAnalysisConfig:
    models = contract.attribution_models
    payload = {
        "conversion_event": contract.conversion_event,
        "conversion_period_start": contract.conversion_period_start,
        "conversion_period_end": contract.conversion_period_end,
        "lookback_window_days": contract.lookback_window_days,
        "identity_strategy": contract.identity_strategy.value,
        "sessionization_policy": contract.sessionization_policy.value,
        "traffic_source_policy": contract.traffic_source_policy.value,
        "direct_treatment_policy": contract.direct_treatment_policy.value,
        "channel_registry_version": channel_registry_version,
        "channel_grouping_version": channel_grouping_version,
        "include_nonconverting_paths": contract.include_nonconverting_paths,
        "conversion_value_strategy": contract.conversion_value_strategy.value,
        "models": [m.value for m in models],
        "journey_definition": contract.journey_definition.model_dump(mode="json"),
        "model_parameters": model_parameters or {},
    }
    return MTAAnalysisConfig(
        conversion_event=contract.conversion_event,
        conversion_period_start=contract.conversion_period_start,
        conversion_period_end=contract.conversion_period_end,
        lookback_window_days=contract.lookback_window_days,
        identity_strategy=contract.identity_strategy,
        sessionization_policy=contract.sessionization_policy,
        traffic_source_policy=contract.traffic_source_policy,
        direct_treatment_policy=contract.direct_treatment_policy,
        channel_registry_version=channel_registry_version,
        channel_grouping_version=channel_grouping_version,
        include_nonconverting_paths=contract.include_nonconverting_paths,
        conversion_value_strategy=contract.conversion_value_strategy,
        models=models,
        journey_definition=contract.journey_definition,
        model_parameters=model_parameters or {},
        fingerprint=canonical_fingerprint(payload),
    )


def compile_execution_plan(
    *,
    execution_plan_id: str,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    track_id: str,
    contract: MTAInputContract,
    readiness_receipt_id: str,
    analysis: MTAAnalysisConfig,
    channel_grouping_fingerprint: str,
    journey_fingerprint: str,
    shapley_preflight: ShapleyPreflight | None = None,
    worker_image_digest: str | None = None,
    source_commit_sha: str | None = None,
    input_mode: MTAInputMode = MTAInputMode.GROUPED_PATH_FREQUENCY,
    runtime_mode: str = "FAKE_TEST",
) -> MTAExecutionPlan:
    model_params = default_model_parameters(
        analysis.models, analysis_params=analysis.model_parameters
    )
    # Drop Shapley when preflight forbids auto-run.
    models = list(analysis.models)
    if AttributionModelId.SHAPLEY in models and shapley_preflight is not None:
        if shapley_preflight.state in (
            ShapleyPreflightState.REVIEW_REQUIRED,
            ShapleyPreflightState.NOT_RECOMMENDED,
        ):
            models = [m for m in models if m is not AttributionModelId.SHAPLEY]
            model_params = tuple(
                p for p in model_params if p.model_id is not AttributionModelId.SHAPLEY
            )
    output_targets = (
        f"mta_attribution_channel_results_{execution_plan_id}",
        f"mta_model_comparison_{execution_plan_id}",
        f"mta_run_manifest_{execution_plan_id}",
    )
    if AttributionModelId.MARKOV in models:
        output_targets = output_targets + (
            f"mta_markov_transitions_{execution_plan_id}",
            f"mta_markov_removal_effects_{execution_plan_id}",
        )
    if AttributionModelId.SHAPLEY in models:
        output_targets = output_targets + (f"mta_shapley_results_{execution_plan_id}",)

    payload = {
        "execution_plan_id": execution_plan_id,
        "input_contract_id": contract.input_contract_id,
        "input_contract_fingerprint": contract.fingerprint,
        "readiness_receipt_id": readiness_receipt_id,
        "analysis_fingerprint": analysis.fingerprint,
        "models": [m.value for m in models],
        "model_parameters": [p.model_dump(mode="json") for p in model_params],
        "channel_registry_version": analysis.channel_registry_version,
        "channel_grouping_version": analysis.channel_grouping_version,
        "channel_grouping_fingerprint": channel_grouping_fingerprint,
        "journey_fingerprint": journey_fingerprint,
        "dp6_version": DP6_MAM_PINNED_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "input_mode": input_mode.value,
        "worker_image_digest": worker_image_digest,
        "source_commit_sha": source_commit_sha,
    }
    return MTAExecutionPlan(
        execution_plan_id=execution_plan_id,
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=track_id,
        input_contract_id=contract.input_contract_id,
        readiness_receipt_id=readiness_receipt_id,
        analysis_config_fingerprint=analysis.fingerprint,
        models=tuple(models),
        model_parameters=model_params,
        channel_registry_version=analysis.channel_registry_version,
        channel_grouping_version=analysis.channel_grouping_version,
        channel_grouping_fingerprint=channel_grouping_fingerprint,
        journey_fingerprint=journey_fingerprint,
        input_mode=input_mode,
        dp6_version=DP6_MAM_PINNED_VERSION,
        adapter_version=ADAPTER_VERSION,
        worker_image_digest=worker_image_digest,
        source_commit_sha=source_commit_sha,
        output_targets=output_targets,
        runtime_mode=runtime_mode,
        fingerprint=canonical_fingerprint(payload),
    )
