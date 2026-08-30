"""Official-runtime pre-fit validation. Does not run full posterior sampling."""

from __future__ import annotations

import platform

from app.control_plane.ids import new_prefit_receipt_id
from app.core.contracts import utc_now
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.compiler import compile_meridian_model_spec
from app.modeling.mmm.contracts import (
    FitFailureClass,
    FitFailureStage,
    MeridianPreFitCheck,
    MeridianPreFitValidationReceipt,
    MeridianRuntimeMode,
    ModelPlan,
    PreFitCheckStatus,
)
from app.modeling.mmm.failures import classify_fit_failure
from app.modeling.mmm.identifiability import is_geo_invariant_identifiability_error
from app.modeling.mmm.meridian.runner import MeridianRuntime

GEO_INVARIANT_NON_MEDIA_WITH_FULL_TIME_KNOTS = "GEO_INVARIANT_NON_MEDIA_WITH_FULL_TIME_KNOTS"


def early_geo_invariant_full_knots_warning(
    *,
    knots: int | list[int] | None,
    n_time: int | None,
    geo_invariant_non_media: bool,
) -> MeridianPreFitCheck | None:
    """PreM3 early warning. Official Meridian remains compatibility authority."""

    full_knots = knots is None or knots == n_time
    if not (full_knots and geo_invariant_non_media):
        return None
    return MeridianPreFitCheck(
        check_name=GEO_INVARIANT_NON_MEDIA_WITH_FULL_TIME_KNOTS,
        status=PreFitCheckStatus.FAIL,
        official=False,
        detail=(
            "PreM3 early warning: geo-invariant non-media treatment with "
            "n_knots=n_time. Official runtime still decides compatibility."
        ),
    )


def execute_prefit_validation(
    runtime: MeridianRuntime,
    plan: ModelPlan,
    *,
    model_version_id: str,
    geo_invariant_non_media: bool = False,
    n_time: int | None = None,
    n_draws: int = 1,
) -> MeridianPreFitValidationReceipt:
    compile_meridian_model_spec(plan=plan)
    checks: list[MeridianPreFitCheck] = []
    warning = early_geo_invariant_full_knots_warning(
        knots=plan.spec.knots,
        n_time=n_time,
        geo_invariant_non_media=geo_invariant_non_media,
    )
    if warning is not None:
        checks.append(warning)
    runtime_mode = getattr(runtime, "runtime_mode", MeridianRuntimeMode.FAKE_TEST)
    python_version = platform.python_version()
    tensorflow_version = None
    failure_class = None
    failure_stage = None
    official_message = None
    status = PreFitCheckStatus.PASS
    try:
        result = runtime.sample_prior(
            plan, n_draws=max(1, n_draws), seed=int(plan.mcmc.get("seed", 1))
        )
        calls = tuple(getattr(result, "calls_made", ()) or ())
        if "sample_posterior" in calls:
            status = PreFitCheckStatus.FAIL
            official_message = "Pre-fit validation must not run full posterior sampling."
            failure_class = FitFailureClass.MERIDIAN_RUNTIME_ERROR
            failure_stage = FitFailureStage.UNKNOWN
            checks.append(
                MeridianPreFitCheck(
                    check_name="no_full_posterior",
                    status=PreFitCheckStatus.FAIL,
                    official=True,
                    detail=official_message,
                )
            )
        else:
            checks.append(
                MeridianPreFitCheck(
                    check_name="official_model_initialization",
                    status=PreFitCheckStatus.PASS,
                    official=True,
                    detail="Official construct_model / sample_prior completed.",
                )
            )
            checks.append(
                MeridianPreFitCheck(
                    check_name="no_full_posterior",
                    status=PreFitCheckStatus.PASS,
                    official=True,
                    detail="sample_posterior was not invoked.",
                )
            )
        tensorflow_version = getattr(result, "tensorflow_version", None)
    except Exception as exc:
        classified = classify_fit_failure(exc)
        status = PreFitCheckStatus.FAIL
        failure_class = classified.failure_class
        failure_stage = classified.failure_stage
        official_message = classified.official_message
        checks.append(
            MeridianPreFitCheck(
                check_name="official_model_initialization",
                status=PreFitCheckStatus.FAIL,
                official=True,
                detail=classified.official_message,
            )
        )
        if is_geo_invariant_identifiability_error(exc):
            checks.append(
                MeridianPreFitCheck(
                    check_name=GEO_INVARIANT_NON_MEDIA_WITH_FULL_TIME_KNOTS,
                    status=PreFitCheckStatus.FAIL,
                    official=True,
                    detail=(
                        "Official Meridian rejected n_knots=n_time with "
                        "geo-invariant treatment."
                    ),
                )
            )
    fingerprint = canonical_fingerprint(
        {
            "model_version_id": model_version_id,
            "model_plan_fingerprint": plan.fingerprint,
            "model_ready_fingerprint": plan.model_ready_manifest_fingerprint,
            "checks": [item.model_dump(mode="json") for item in checks],
            "status": status.value,
            "official_message": official_message,
        }
    )
    return MeridianPreFitValidationReceipt(
        receipt_id=new_prefit_receipt_id(),
        model_version_id=model_version_id,
        model_plan_fingerprint=plan.fingerprint,
        model_ready_fingerprint=plan.model_ready_manifest_fingerprint,
        runtime_mode=runtime_mode,
        meridian_version=PINNED_RUNTIME_VERSION,
        python_version=python_version,
        tensorflow_version=tensorflow_version,
        checks=tuple(checks),
        status=status,
        failure_class=failure_class,
        failure_stage=failure_stage,
        official_message=official_message,
        generated_at=utc_now(),
        fingerprint=fingerprint,
    )


def prefit_blocks_final_model(receipt: MeridianPreFitValidationReceipt | None) -> bool:
    return receipt is None or receipt.status is not PreFitCheckStatus.PASS
