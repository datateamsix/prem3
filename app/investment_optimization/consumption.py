"""Compile a Planning projection of accepted MMM. MMM remains source of truth."""

from __future__ import annotations

from typing import Protocol

from app.investment_optimization.accepted_model import is_accepted_model
from app.investment_optimization.contracts import (
    ModelConsumptionContract,
    ModelConsumptionVariable,
    OptimizationIssue,
)
from app.investment_optimization.enums import (
    ORGANIC_CHANNEL_IDS,
    PINNED_MERIDIAN_RUNTIME,
    ModelGeoSemantics,
    ModelVariableOptimizationEligibility,
    ModelVariableRole,
    OptimizationIssueCode,
    SpendSemantics,
)
from app.investment_optimization.ids import new_consumption_contract_id
from app.investment_planning.fingerprint import metadata_fingerprint
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.mmm.contracts import (
    MeridianModelArtifactManifest,
    MMMModelVersion,
    ModelAcceptanceApproval,
    ModelPlan,
)
from app.modeling.mmm.states import MMMModelingStage


class MemoryModelConsumptionSource:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], ModelConsumptionContract] = {}

    def put(self, contract: ModelConsumptionContract) -> ModelConsumptionContract:
        key = (contract.tenant_id, contract.project_id, contract.model_version_id)
        self._items[key] = contract
        return contract

    def get_contract(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> ModelConsumptionContract | None:
        return self._items.get((tenant_id, project_id, model_version_id))


class ModelConsumptionSource(Protocol):
    def get_contract(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> ModelConsumptionContract | None: ...


def _issue(
    code: OptimizationIssueCode, *, blocking: bool, review: bool = False
) -> OptimizationIssue:
    return OptimizationIssue(
        code=code,
        blocking=blocking,
        review_required=review,
        message_key=code.value,
    )


def _geo_semantics(*, scope: str, n_geos: int | None) -> ModelGeoSemantics:
    normalized = scope.strip().upper()
    if normalized in {item.value for item in ModelGeoSemantics}:
        return ModelGeoSemantics(normalized)
    if normalized == "NATIONAL" or n_geos == 1:
        return ModelGeoSemantics.NATIONAL
    if n_geos is not None and n_geos > 1:
        return ModelGeoSemantics.GEO
    return ModelGeoSemantics.NATIONAL


def _variable_from_channel(
    channel: str, *, role: ModelVariableRole
) -> ModelConsumptionVariable:
    organic = channel in ORGANIC_CHANNEL_IDS or role is ModelVariableRole.ORGANIC
    if organic:
        eligibility = ModelVariableOptimizationEligibility.CONTEXT_ONLY
        variable_role = ModelVariableRole.ORGANIC
    elif role is ModelVariableRole.CONTROL:
        eligibility = ModelVariableOptimizationEligibility.CONTROL
        variable_role = role
    else:
        eligibility = ModelVariableOptimizationEligibility.OPTIMIZABLE
        variable_role = role
    return ModelConsumptionVariable(
        model_variable_id=channel,
        model_variable_name=channel,
        variable_role=variable_role,
        eligibility=eligibility,
        spend_semantics=(
            None
            if variable_role is not ModelVariableRole.MEDIA_SPEND
            else SpendSemantics.APPROVED_MEDIA_SPEND
        ),
        canonical_channel_id=None,
    )


def validate_consumption_contract(
    contract: ModelConsumptionContract,
) -> ModelConsumptionContract:
    issues: list[OptimizationIssue] = list(contract.issues)
    complete = True
    required = (
        contract.model_version_id,
        contract.model_plan_fingerprint,
        contract.model_acceptance_ref,
        contract.meridian_version,
        contract.runtime_mode,
        contract.modeled_window_start,
        contract.modeled_window_end,
        contract.currency,
        contract.kpi,
        contract.accepted_model_state,
    )
    if any(not item for item in required) or not contract.variables:
        complete = False
        issues.append(
            _issue(OptimizationIssueCode.MODEL_CONSUMPTION_CONTRACT_INCOMPLETE, blocking=True)
        )
    if contract.accepted_model_state != MMMModelingStage.MODEL_ACCEPTED.value:
        complete = False
        issues.append(_issue(OptimizationIssueCode.NO_ACCEPTED_MODEL, blocking=True))
    if not contract.optimizer_artifact_ref and not contract.response_evidence_ref:
        complete = False
        issues.append(
            _issue(OptimizationIssueCode.OPTIMIZER_INPUT_ARTIFACT_MISSING, blocking=True)
        )
    runtime = contract.meridian_version or ""
    if runtime and runtime != PINNED_MERIDIAN_RUNTIME and runtime != PINNED_RUNTIME_VERSION:
        complete = False
        issues.append(
            _issue(OptimizationIssueCode.MODEL_RUNTIME_INCOMPATIBLE, blocking=True)
        )
    unique_issues: list[OptimizationIssue] = []
    seen: set[str] = set()
    for issue in issues:
        if issue.code.value in seen:
            continue
        seen.add(issue.code.value)
        unique_issues.append(issue)
    fingerprint = metadata_fingerprint(
        {
            "model_version_id": contract.model_version_id,
            "model_plan_fingerprint": contract.model_plan_fingerprint,
            "model_acceptance_ref": contract.model_acceptance_ref,
            "meridian_version": contract.meridian_version,
            "runtime_mode": contract.runtime_mode,
            "window": [contract.modeled_window_start, contract.modeled_window_end],
            "geo": contract.geo_semantics.value,
            "currency": contract.currency,
            "kpi": contract.kpi,
            "variables": [
                item.model_dump(mode="json") for item in contract.variables
            ],
            "optimizer_artifact_ref": contract.optimizer_artifact_ref,
            "response_evidence_ref": contract.response_evidence_ref,
        }
    )
    return contract.model_copy(
        update={
            "complete": complete and not any(issue.blocking for issue in unique_issues),
            "issues": tuple(unique_issues),
            "model_consumption_contract_fingerprint": fingerprint,
            "fingerprint": fingerprint,
        }
    )


def compile_model_consumption_contract(
    *,
    version: MMMModelVersion,
    plan: ModelPlan | None,
    acceptance: ModelAcceptanceApproval | None,
    artifact: MeridianModelArtifactManifest | None,
    response_evidence_ref: str | None,
    currency: str | None,
    kpi: str | None,
    runtime_mode: str | None,
    n_geos: int | None = None,
    canonical_channel_bindings: dict[str, str] | None = None,
) -> ModelConsumptionContract:
    """Compile from accepted MMM public fields. Never infer canonical IDs from names."""
    bindings = canonical_channel_bindings or {}
    variables: list[ModelConsumptionVariable] = []
    if plan is not None:
        for channel in plan.media_channels:
            variable = _variable_from_channel(channel, role=ModelVariableRole.MEDIA_SPEND)
            bound = bindings.get(channel)
            if bound:
                variable = variable.model_copy(update={"canonical_channel_id": bound})
            variables.append(variable)
        for channel in plan.rf_channels:
            variable = _variable_from_channel(channel, role=ModelVariableRole.MEDIA_SPEND)
            bound = bindings.get(channel)
            if bound:
                variable = variable.model_copy(update={"canonical_channel_id": bound})
            variables.append(variable)
        for channel in plan.non_media_treatments or ():
            variables.append(
                _variable_from_channel(channel, role=ModelVariableRole.CONTROL)
            )
    contract = ModelConsumptionContract(
        consumption_contract_id=new_consumption_contract_id(),
        tenant_id=version.tenant_id,
        project_id=version.project_id,
        model_version_id=version.model_version_id,
        model_plan_fingerprint=version.model_plan_fingerprint or (plan.fingerprint if plan else ""),
        model_consumption_contract_fingerprint="",
        model_acceptance_ref="" if acceptance is None else acceptance.approval_id,
        meridian_version=version.meridian_version,
        runtime_mode=runtime_mode or "",
        accepted_model_state=version.state.value,
        modeled_window_start=version.model_window_start
        or (plan.model_window_start if plan else ""),
        modeled_window_end=version.model_window_end
        or (plan.model_window_end if plan else ""),
        geo_semantics=_geo_semantics(scope=plan.scope if plan else "NATIONAL", n_geos=n_geos),
        currency=currency or "",
        kpi=kpi or "",
        variables=tuple(variables),
        optimizer_artifact_ref=None if artifact is None else artifact.binary_model_ref,
        response_evidence_ref=response_evidence_ref,
        model_spec_ref=None if plan is None else plan.model_plan_id,
        future_horizon_allowed=True,
        fingerprint="",
    )
    compiled = validate_consumption_contract(contract)
    return bind_projection_to_accepted_model(compiled, version)


def bind_projection_to_accepted_model(
    contract: ModelConsumptionContract,
    version: MMMModelVersion,
) -> ModelConsumptionContract:
    """Fail closed if a cached Planning projection diverges from accepted MMM."""
    extra: list[OptimizationIssue] = []
    if not is_accepted_model(version):
        extra.append(_issue(OptimizationIssueCode.NO_ACCEPTED_MODEL, blocking=True))
    identity_mismatch = (
        contract.tenant_id != version.tenant_id
        or contract.project_id != version.project_id
        or contract.model_version_id != version.model_version_id
    )
    fingerprint_mismatch = bool(
        version.model_plan_fingerprint
        and contract.model_plan_fingerprint != version.model_plan_fingerprint
    )
    window_mismatch = (
        bool(version.model_window_start)
        and contract.modeled_window_start != version.model_window_start
    ) or (
        bool(version.model_window_end)
        and contract.modeled_window_end != version.model_window_end
    )
    if identity_mismatch or fingerprint_mismatch or window_mismatch:
        extra.append(
            _issue(OptimizationIssueCode.MODEL_CONSUMPTION_PROJECTION_STALE, blocking=True)
        )
    if version.meridian_version and contract.meridian_version != version.meridian_version:
        extra.append(_issue(OptimizationIssueCode.MODEL_RUNTIME_INCOMPATIBLE, blocking=True))
    rebound = contract.model_copy(update={"issues": tuple(extra) + contract.issues})
    return validate_consumption_contract(rebound)
