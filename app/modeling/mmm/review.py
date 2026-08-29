"""Official review pack assembly. Gemini may explain; it may not change status."""

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.contracts import (
    MeridianModelHealthReceipt,
    MMMModelReviewPack,
    ResultsSummary,
)


def assemble_review_pack(
    *,
    model_version_id: str,
    fit_run_id: str,
    model_spec_summary: dict,
    prior_summary: dict,
    mcmc_summary: dict,
    health: MeridianModelHealthReceipt,
    results: ResultsSummary,
    limitations: tuple[str, ...],
    review_required: tuple[str, ...],
    acknowledged: tuple[str, ...] = (),
) -> MMMModelReviewPack:
    payload = {
        "model_version_id": model_version_id,
        "fit_run_id": fit_run_id,
        "health": health.model_dump(mode="json"),
        "results": results.model_dump(mode="json"),
        "review_required": review_required,
        "acknowledged": acknowledged,
    }
    return MMMModelReviewPack(
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        model_spec_summary=model_spec_summary,
        prior_summary=prior_summary,
        mcmc_summary=mcmc_summary,
        official_health=health,
        results=results,
        known_limitations=limitations,
        review_required_items=review_required,
        acknowledged_review_items=acknowledged,
        recommended_next_action=(
            "ACCEPT"
            if not review_required or set(review_required) <= set(acknowledged)
            else "ACKNOWLEDGE_REVIEW"
        ),
        fingerprint=canonical_fingerprint(payload),
    )
