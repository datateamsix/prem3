"""Successor ModelVersion after a human identifiability decision. Never mutates v1."""

from __future__ import annotations

from typing import Any

from app.control_plane.ids import new_model_plan_id
from app.modeling.common.errors import (
    FabricatedGeoVariationError,
    IdentifiabilityDecisionRequiredError,
    ModelSpecInvalidError,
)
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.compiler import default_priors
from app.modeling.mmm.contracts import (
    DataFoundationWorkRequest,
    IdentifiabilityAlternativeId,
    KnotStrategyProposal,
    ModelDecision,
    ModelPlan,
)
from app.modeling.mmm.identifiability import MUSIC_CENTER_PROMO_VARIABLE

PROMOTION_NOT_EXPLICITLY_MODELED = "PROMOTION_NOT_EXPLICITLY_MODELED"
ITERATION_REASON_IDENTIFIABILITY = "MODEL_SPEC_IDENTIFIABILITY_ERROR"


def selected_alternative(decision: ModelDecision) -> IdentifiabilityAlternativeId:
    chosen = decision.chosen_value
    if not isinstance(chosen, dict):
        raise IdentifiabilityDecisionRequiredError(
            "Human identifiability decision must select A, B, or C."
        )
    raw = chosen.get("selected_alternative")
    try:
        return IdentifiabilityAlternativeId(str(raw))
    except ValueError as exc:
        raise IdentifiabilityDecisionRequiredError(
            "Human identifiability decision must select A, B, or C."
        ) from exc


def selected_configuration(decision: ModelDecision) -> dict[str, Any]:
    chosen = decision.chosen_value
    if not isinstance(chosen, dict):
        return {}
    config = chosen.get("selected_configuration")
    return dict(config) if isinstance(config, dict) else {}


def compile_successor_model_plan(
    *,
    predecessor: ModelPlan,
    successor_model_version_id: str,
    decision: ModelDecision,
    knot_proposal: KnotStrategyProposal | None = None,
) -> ModelPlan | DataFoundationWorkRequest:
    alternative = selected_alternative(decision)
    config = selected_configuration(decision)
    spec = predecessor.spec
    treatments = predecessor.non_media_treatments
    if treatments is None:
        treatments = (MUSIC_CENTER_PROMO_VARIABLE,)
    if alternative is IdentifiabilityAlternativeId.C:
        if config.get("fabricate_geo_variation"):
            raise FabricatedGeoVariationError(
                "Geo variation in music_center_promo cannot be fabricated."
            )
        return DataFoundationWorkRequest(
            reason=(
                "Alternative C requires new governed geo-varying promotion evidence, "
                "a new Data Foundation validation, and a new ModelReady artifact. "
                "The current ModelReady fingerprint must not be mutated."
            ),
            required_evidence=(
                "regional promotion spend or intensity",
                "geo coverage spanning the model window",
                "governed transform provenance",
            ),
            blocks_successor_fit=True,
        )
    if alternative is IdentifiabilityAlternativeId.A:
        n_knots = config.get("n_knots")
        if n_knots is None:
            raise IdentifiabilityDecisionRequiredError(
                "Alternative A requires a human-approved n_knots less than n_time."
            )
        n_knots = int(n_knots)
        n_time = None if knot_proposal is None else knot_proposal.current_n_time
        if n_time is not None and n_knots >= n_time:
            raise ModelSpecInvalidError("Alternative A requires n_knots < n_time.")
        spec = spec.model_copy(update={"knots": n_knots, "enable_aks": False})
        treatments = (MUSIC_CENTER_PROMO_VARIABLE,)
    elif alternative is IdentifiabilityAlternativeId.B:
        treatments = tuple(
            item for item in treatments if item != MUSIC_CENTER_PROMO_VARIABLE
        )
    fingerprint = canonical_fingerprint(
        {
            "input": predecessor.model_ready_manifest_fingerprint,
            "window": [predecessor.model_window_start, predecessor.model_window_end],
            "spec": spec.model_dump(mode="json"),
            "priors": [item.model_dump(mode="json") for item in predecessor.priors],
            "mcmc": predecessor.mcmc,
            "meridian_version": PINNED_RUNTIME_VERSION,
            "scope": predecessor.scope,
            "channels": {
                "media": predecessor.media_channels,
                "rf": predecessor.rf_channels,
                "non_media_treatments": treatments,
            },
            "source_model_decision_id": decision.decision_id,
            "predecessor_plan_fingerprint": predecessor.fingerprint,
        }
    )
    return ModelPlan(
        model_plan_id=new_model_plan_id(),
        model_version_id=successor_model_version_id,
        model_ready_run_id=predecessor.model_ready_run_id,
        model_ready_manifest_fingerprint=predecessor.model_ready_manifest_fingerprint,
        business_profile_snapshot_id=predecessor.business_profile_snapshot_id,
        meridian_version=predecessor.meridian_version,
        model_window_start=predecessor.model_window_start,
        model_window_end=predecessor.model_window_end,
        scope=predecessor.scope,
        spec=spec,
        priors=predecessor.priors or default_priors(),
        mcmc=dict(predecessor.mcmc),
        compute_profile=predecessor.compute_profile,
        rf_channels=predecessor.rf_channels,
        media_channels=predecessor.media_channels,
        non_media_treatments=treatments,
        fingerprint=fingerprint,
    )
