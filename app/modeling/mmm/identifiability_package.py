"""Evidence-grounded identifiability decision package. PreM3 recommends; humans decide."""

from __future__ import annotations

from typing import Any

from app.control_plane.ids import new_identifiability_package_id
from app.core.contracts import utc_now
from app.eda.extended_contracts import KNOT_FALLBACK_STATEMENT, KNOTS_NORMATIVE_REF
from app.eda.fingerprint import eda_receipt_fingerprint, knowledge_version
from app.eda.music_center import (
    MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
    MUSIC_CENTER_CYCLE_ID,
    MUSIC_CENTER_DATASET_FINGERPRINT,
    MUSIC_CENTER_FINDING_IDS,
    MUSIC_CENTER_MODEL_READY_FINGERPRINT,
    music_center_business_context,
    music_center_receipt,
)
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.contracts import (
    DecisionType,
    FitFailureClass,
    FitFailureStage,
    GeoPromotionEvidenceStatus,
    IdentifiabilityAlternative,
    IdentifiabilityAlternativeId,
    IdentifiabilityOfficialFailure,
    IdentifiabilityPackageStatus,
    IdentifiabilityRecommendation,
    KnotCandidate,
    KnotStrategyProposal,
    MMMIdentifiabilityDecisionPackage,
    PromotionMateriality,
)
from app.modeling.mmm.coverage import MUSIC_CENTER_MODEL_READY_COVERAGE
from app.modeling.mmm.geo_promotion import inspect_music_center_promotion_evidence
from app.modeling.mmm.identifiability import (
    MUSIC_CENTER_PROMO_VARIABLE,
    OFFICIAL_MERIDIAN_LIBRARY,
    extract_invariant_treatment,
    prem3_identifiability_summary,
)

IDENTIFIABILITY_POLICY_VERSION = "identifiability-decision/v1"
EDA_ONLY_SOURCE = "PRE_MODELING_EDA_ONLY"

_COLLINEARITY_FINDINGS = tuple(
    item for item in MUSIC_CENTER_FINDING_IDS if "VARIABLE_GEO_TIME_COLLINEARITY" in item
)
_GEO_SD_FINDINGS = tuple(
    item for item in MUSIC_CENTER_FINDING_IDS if item.startswith("STANDARD_DEVIATION.GEO")
)


def knot_strategy_proposal(*, n_time: int, current_n_knots: int | None) -> KnotStrategyProposal:
    """Candidates from official semantics and EDA compatibility, not visual preference."""

    eda_knots = max(1, n_time - 1)
    candidates = (
        KnotCandidate(
            n_knots=eda_knots,
            selection_basis=(
                "Official Meridian EDA compatibility used n_knots = n_time - 1. "
                "That enabled official EDA only; it is not a fitted-model ranking."
            ),
            relative_time_flexibility="near_full_n_time_minus_one",
            official_pre_fit_compatibility="SUPPORTED_INTEGER_KNOTS_LT_N_TIME",
            is_statistically_ranked=False,
        ),
    )
    return KnotStrategyProposal(
        current_n_time=n_time,
        current_n_knots=current_n_knots,
        candidate_n_knots=candidates,
        selection_basis=(
            "Official Meridian supports integer n_knots. Geo default is n_knots = n_time, "
            "which is unidentifiable here. EDA used n_time - 1. The human must approve "
            "the exact knot value; PreM3 does not claim statistical superiority."
        ),
        relative_time_flexibility="full_when_n_knots_equals_n_time",
        official_pre_fit_compatibility="N_KNOTS_LT_N_TIME_REQUIRED_IF_PROMOTION_RETAINED",
        tradeoffs=(
            "Fewer knots reduce time-effect flexibility and may leave residual structure.",
            "Selected knots can change how temporal effects are attributed.",
            "Promotion may remain collinear with other variables even after knot reduction.",
        ),
        prem3_recommendation=None,
        approved_n_knots=None,
    )


def _promotion_materiality(business_context: dict[str, Any]) -> PromotionMateriality:
    drivers = [str(item).lower() for item in business_context.get("material_drivers") or ()]
    if "promotions" in drivers or "promotion" in drivers:
        return PromotionMateriality.MATERIAL
    notes = str(business_context.get("commercial_driver_notes") or "").lower()
    if "promotion" in notes:
        return PromotionMateriality.CONTEXTUAL
    if business_context.get("silent"):
        return PromotionMateriality.UNKNOWN
    return PromotionMateriality.UNKNOWN


def _alternatives(
    *,
    geo_status: GeoPromotionEvidenceStatus,
    geo_available: bool,
    geo_reason: str | None,
) -> tuple[IdentifiabilityAlternative, ...]:
    return (
        IdentifiabilityAlternative(
            alternative_id=IdentifiabilityAlternativeId.A,
            summary="Retain music_center_promo. Reduce time-effect knot flexibility.",
            keep_promotion=True,
            knot_strategy="n_knots < n_time",
            available=True,
            potential_benefit="Preserves promotion as an explicit modeled business treatment.",
            primary_risk=(
                "Too few knots may under-represent unexplained temporal structure "
                "or shift that structure into other model effects."
            ),
        ),
        IdentifiabilityAlternative(
            alternative_id=IdentifiabilityAlternativeId.B,
            summary="Remove music_center_promo. Retain n_knots = n_time.",
            keep_promotion=False,
            knot_strategy="n_knots = n_time",
            available=True,
            potential_benefit="Retains maximum time-effect flexibility.",
            primary_risk=(
                "If promotion materially affects the KPI or media allocation, "
                "its effect may be absorbed into baseline or other variables. "
                "This is not harmless variable cleanup."
            ),
        ),
        IdentifiabilityAlternative(
            alternative_id=IdentifiabilityAlternativeId.C,
            summary="Use legitimate geo-varying promotion intensity if such data exists.",
            keep_promotion=True,
            knot_strategy="n_knots = n_time with geo-varying promotion",
            available=geo_available,
            unavailable_reason=None if geo_available else geo_reason,
            potential_benefit=(
                "Separates promotion from the time effect using genuine geo variation."
            ),
            primary_risk=(
                "A new field may be a weak proxy, coverage may not span the model window, "
                "or definitions may differ by market."
            ),
            requires_new_model_ready=True,
            data_foundation_work_required=not geo_available
            or geo_status is not GeoPromotionEvidenceStatus.GEO_PROMOTION_EVIDENCE_AVAILABLE,
        ),
    )


def _recommend(
    *,
    materiality: PromotionMateriality,
    geo_available: bool,
    alternatives: tuple[IdentifiabilityAlternative, ...],
) -> tuple[IdentifiabilityRecommendation | None, tuple[str, ...], tuple[str, ...]]:
    by_id = {item.alternative_id: item for item in alternatives}
    if geo_available and by_id[IdentifiabilityAlternativeId.C].available:
        rec = IdentifiabilityRecommendation(
            kind="PREM3_RECOMMENDATION",
            alternative_id=IdentifiabilityAlternativeId.C,
            statement=(
                "C may be recommended if validated geo-varying promotion evidence exists, "
                "subject to a new Data Foundation / ModelReady version."
            ),
            rationale="Real geo-varying promotion evidence can restore identifiability.",
            approved_model_change=False,
        )
        counter = (
            "The new field may be a weak proxy for the national promotion process.",
            "Coverage may not span the model window.",
            "Promotion definitions may differ by market.",
        )
        return rec, counter, ()
    if materiality is PromotionMateriality.MATERIAL and not geo_available:
        rec = IdentifiabilityRecommendation(
            kind="PREM3_RECOMMENDATION",
            alternative_id=IdentifiabilityAlternativeId.A,
            statement=(
                "A may be recommended for human review because Business IQ treats "
                "promotions as a material driver and no valid geo-varying promotion "
                "measure is available."
            ),
            rationale=(
                "Retain an explicit promotion effect and reduce time-effect flexibility "
                "enough for official Meridian identifiability. This is advisory only."
            ),
            approved_model_change=False,
        )
        counter = (
            "Reduced time flexibility may leave residual temporal structure.",
            "Selected knots may change attribution of temporal effects.",
            "Promotion may remain collinear with other variables.",
        )
        uncertainties: tuple[str, ...] = ()
        if materiality is PromotionMateriality.UNKNOWN:
            uncertainties = (
                "Business IQ is silent on promotion materiality, which reduces "
                "confidence in choosing between A and B.",
            )
        return rec, counter, uncertainties
    if materiality in {PromotionMateriality.CONTEXTUAL, PromotionMateriality.UNKNOWN}:
        rec = IdentifiabilityRecommendation(
            kind="PREM3_RECOMMENDATION",
            alternative_id=None,
            statement=(
                "No alternative is recommended as a default. Promotion materiality is "
                f"{materiality.value}; A and B remain human-owned."
            ),
            rationale=(
                "Do not treat B as harmless cleanup, and do not auto-select A."
            ),
            approved_model_change=False,
        )
        counter = (
            "Promotion may be a genuine business driver.",
            "Promotion timing may correlate with media.",
            "Baseline may absorb a consequential treatment if B is chosen.",
            "Too few knots may under-represent temporal structure if A is chosen.",
        )
        uncertainties = ()
        if materiality is PromotionMateriality.UNKNOWN:
            uncertainties = (
                "Business IQ is silent on promotion materiality, which reduces "
                "confidence in choosing between A and B.",
            )
        return rec, counter, uncertainties
    rec = IdentifiabilityRecommendation(
        kind="PREM3_RECOMMENDATION",
        alternative_id=IdentifiabilityAlternativeId.B,
        statement=(
            "B may be considered if promotion is weak or non-material and evidence "
            "supports allowing time effects to absorb it."
        ),
        rationale="Promotion is not evidenced as a material driver.",
        approved_model_change=False,
    )
    counter = (
        "Promotion may still be a genuine business driver despite weak labeling.",
        "Promotion timing may correlate with media.",
        "Baseline may absorb a consequential treatment.",
    )
    return rec, counter, ()


def build_identifiability_package(
    *,
    project_id: str,
    cycle_id: str,
    failed_model_version_id: str,
    failed_fit_run_id: str,
    official_message: str,
    failure_class: FitFailureClass = FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR,
    failure_stage: FitFailureStage = FitFailureStage.MODEL_INITIALIZATION,
    library: str = OFFICIAL_MERIDIAN_LIBRARY,
    library_version: str = "1.8.0",
    exception_type: str | None = "ValueError",
    business_context: dict[str, Any] | None = None,
    data_evidence: dict[str, Any] | None = None,
    eda_evidence: dict[str, Any] | None = None,
    model_evidence: dict[str, Any] | None = None,
    package_id: str | None = None,
) -> MMMIdentifiabilityDecisionPackage:
    variable = extract_invariant_treatment(official_message) or MUSIC_CENTER_PROMO_VARIABLE
    geo = data_evidence if data_evidence is not None else inspect_music_center_promotion_evidence()
    status = geo["status"]
    if not isinstance(status, GeoPromotionEvidenceStatus):
        status = GeoPromotionEvidenceStatus(str(status))
    business = business_context or {}
    materiality = _promotion_materiality(business)
    business = {
        **business,
        "promotion_materiality": materiality.value,
        "name_is_not_evidence": (
            "Do not infer importance of music_center_promo from its name."
        ),
    }
    alternatives = _alternatives(
        geo_status=status,
        geo_available=bool(geo.get("alternative_c_available")),
        geo_reason=geo.get("unavailable_reason"),
    )
    recommendation, counter, uncertainties = _recommend(
        materiality=materiality,
        geo_available=bool(geo.get("alternative_c_available")),
        alternatives=alternatives,
    )
    n_time = int(
        (eda_evidence or {}).get("n_time")
        or MUSIC_CENTER_MODEL_READY_COVERAGE.n_times
        or 131
    )
    knots = knot_strategy_proposal(
        n_time=n_time,
        current_n_knots=(eda_evidence or {}).get("failed_n_knots"),
    )
    payload = {
        "failed_model_version_id": failed_model_version_id,
        "failed_fit_run_id": failed_fit_run_id,
        "official_message": official_message,
        "alternatives": [item.model_dump(mode="json") for item in alternatives],
        "recommendation": None
        if recommendation is None
        else recommendation.model_dump(mode="json"),
        "policy_version": IDENTIFIABILITY_POLICY_VERSION,
        "knowledge_version": knowledge_version(),
    }
    fingerprint = canonical_fingerprint(payload)
    data_block = dict(geo)
    provenance = data_block.get("provenance")
    if hasattr(provenance, "model_dump"):
        data_block["provenance"] = provenance.model_dump(mode="json")
    data_block["status"] = status.value
    return MMMIdentifiabilityDecisionPackage(
        package_id=package_id or new_identifiability_package_id(),
        project_id=project_id,
        cycle_id=cycle_id,
        failed_model_version_id=failed_model_version_id,
        failed_fit_run_id=failed_fit_run_id,
        failure_ref=failed_fit_run_id,
        official_failure=IdentifiabilityOfficialFailure(
            failure_class=failure_class,
            failure_stage=failure_stage,
            official_message=official_message,
            library=library,
            library_version=library_version,
            exception_type=exception_type,
        ),
        decision_type=DecisionType.KNOT_STRATEGY,
        linked_decision_types=(
            DecisionType.TREATMENT_CLASSIFICATION.value,
            "GEO_SCOPE_REVIEW",
        ),
        affected_variables=(variable,),
        business_context=business,
        data_evidence=data_block,
        eda_evidence=eda_evidence or {},
        model_evidence=model_evidence or {},
        alternatives=alternatives,
        prem3_recommendation=recommendation,
        recommendation_rationale=None if recommendation is None else recommendation.rationale,
        counter_evidence=counter,
        uncertainties=uncertainties,
        decision_status=IdentifiabilityPackageStatus.PENDING_HUMAN_DECISION,
        selected_alternative=None,
        knot_strategy_proposal=knots,
        policy_version=IDENTIFIABILITY_POLICY_VERSION,
        knowledge_version=knowledge_version(),
        generated_at=utc_now(),
        fingerprint=fingerprint,
    )


def music_center_business_context_block() -> dict[str, Any]:
    context = music_center_business_context()
    return {
        "business_profile_snapshot_id": MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
        "primary_business_outcome": context.primary_business_outcome,
        "markets": list(context.markets),
        "material_channels": list(context.material_channels),
        "material_drivers": list(context.material_drivers),
        "labeled_facts": [
            {
                "label": item.label,
                "statement": item.statement,
                "source_ref": item.source_ref,
            }
            for item in context.labeled_facts
        ],
        "silent": False,
        "variable_specific_importance": (
            "Business IQ lists promotions as a material driver. It does not "
            "quantify music_center_promo from the column name alone."
        ),
    }


def music_center_eda_evidence_block() -> dict[str, Any]:
    receipt = music_center_receipt()
    return {
        "eda_model_spec_source": receipt.model_spec.source,
        "eda_model_spec_purpose": EDA_ONLY_SOURCE,
        "approved_for_final_modeling": receipt.model_spec.approved_for_final_modeling,
        "knot_fallback_statement": KNOT_FALLBACK_STATEMENT,
        "knots_normative_ref": KNOTS_NORMATIVE_REF,
        "n_knots_eda": receipt.model_spec.n_knots,
        "n_time": receipt.model_spec.n_time,
        "failed_n_knots": receipt.model_spec.n_time,
        "implication_ids": ("imp_knot_strategy", "imp_geo_scope_review"),
        "open_decision_types": ("KNOT_STRATEGY", "GEO_SCOPE_REVIEW"),
        "finding_ids": _COLLINEARITY_FINDINGS + _GEO_SD_FINDINGS,
        "receipt_fingerprint": eda_receipt_fingerprint(receipt),
        "receipt_run_id": receipt.run_id,
        "compatibility_official_error": None
        if receipt.compatibility_event is None
        else receipt.compatibility_event.official_error,
        "note": KNOT_FALLBACK_STATEMENT,
    }


def build_music_center_v1_package(
    *,
    project_id: str,
    failed_model_version_id: str,
    failed_fit_run_id: str,
    official_message: str,
    model_evidence: dict[str, Any] | None = None,
) -> MMMIdentifiabilityDecisionPackage:
    geo = inspect_music_center_promotion_evidence()
    provenance = geo["provenance"]
    geo = {
        **geo,
        "provenance": provenance.model_copy(
            update={"model_ready_fingerprint": MUSIC_CENTER_MODEL_READY_FINGERPRINT}
        ),
        "dataset_a_fingerprint": MUSIC_CENTER_DATASET_FINGERPRINT,
    }
    return build_identifiability_package(
        project_id=project_id,
        cycle_id=MUSIC_CENTER_CYCLE_ID,
        failed_model_version_id=failed_model_version_id,
        failed_fit_run_id=failed_fit_run_id,
        official_message=official_message,
        business_context=music_center_business_context_block(),
        data_evidence=geo,
        eda_evidence=music_center_eda_evidence_block(),
        model_evidence=model_evidence or {},
    )


def package_is_advisory(package: MMMIdentifiabilityDecisionPackage) -> bool:
    rec = package.prem3_recommendation
    if rec is None:
        return True
    return rec.kind == "PREM3_RECOMMENDATION" and rec.approved_model_change is False


def human_decision_payload(package: MMMIdentifiabilityDecisionPackage) -> dict[str, Any]:
    return {
        "decision_type": package.decision_type.value,
        "selected_alternative": None,
        "selected_configuration": {
            "A": {
                "keep": MUSIC_CENTER_PROMO_VARIABLE,
                "n_knots": "<human-approved integer less than n_time>",
                "candidate_n_knots": [
                    item.n_knots
                    for item in (package.knot_strategy_proposal.candidate_n_knots or ())
                ]
                if package.knot_strategy_proposal is not None
                else [],
            },
            "B": {
                "remove_non_media_treatments": [MUSIC_CENTER_PROMO_VARIABLE],
                "limitation": "PROMOTION_NOT_EXPLICITLY_MODELED",
                "retain_knot_strategy": "n_knots = n_time",
            },
            "C": {
                "requires": "governed geo-varying promotion evidence",
                "eligible": next(
                    item.available
                    for item in package.alternatives
                    if item.alternative_id is IdentifiabilityAlternativeId.C
                ),
                "data_foundation_work_request": True,
            },
        },
        "rationale": "<human rationale>",
        "evidence_refs": [
            package.failed_fit_run_id,
            package.failed_model_version_id,
            package.package_id,
        ],
        "approved_by": "<authorized human; service accounts prohibited>",
        "approved_at": None,
        "decision_fingerprint": None,
        "note": prem3_identifiability_summary(package.official_failure.official_message),
    }
