"""Known Meridian worker path. Never executes generated scripts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.modeling.common.errors import FitRuntimeError, PriorValidationFailedError, SerdeError
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.mmm.contracts import (
    MeridianFitPlan,
    ModelPlan,
    OfficialCheckResult,
    OfficialHealthStatus,
    PriorValidationStatus,
)
from app.modeling.mmm.meridian.builder import assert_input_fingerprint, assert_not_eda_spec


@dataclass(frozen=True)
class PriorSampleResult:
    status: PriorValidationStatus
    n_draws: int
    seed: int
    warnings: tuple[str, ...] = ()
    artifact: bytes = b""


@dataclass(frozen=True)
class FitExecutionResult:
    binary: bytes
    binary_sha256: str
    health_checks: tuple[OfficialCheckResult, ...]
    results_html: str
    structured: dict[str, Any]
    python_version: str
    tensorflow_version: str | None
    meridian_version: str
    worker_image_digest: str | None = None


class MeridianRuntime(Protocol):
    def sample_prior(self, plan: ModelPlan, *, n_draws: int, seed: int) -> PriorSampleResult: ...

    def sample_posterior(
        self, plan: ModelPlan, fit_plan: MeridianFitPlan
    ) -> FitExecutionResult: ...


class FakeMeridianRuntime:
    """CPU-test runtime. Does not import google-meridian."""

    def sample_prior(self, plan: ModelPlan, *, n_draws: int, seed: int) -> PriorSampleResult:
        if n_draws < 1:
            raise PriorValidationFailedError("n_draws must be positive.")
        payload = json.dumps(
            {"plan": plan.fingerprint, "n_draws": n_draws, "seed": seed},
            sort_keys=True,
        ).encode()
        return PriorSampleResult(
            status=PriorValidationStatus.PASS,
            n_draws=n_draws,
            seed=seed,
            artifact=payload,
        )

    def sample_posterior(self, plan: ModelPlan, fit_plan: MeridianFitPlan) -> FitExecutionResult:
        if fit_plan.model_plan_fingerprint != plan.fingerprint:
            raise FitRuntimeError("FitPlan fingerprint does not match ModelPlan.")
        blob = json.dumps(
            {
                "format": "prem3-fake-meridian-binpb",
                "plan": plan.fingerprint,
                "fit": fit_plan.fingerprint,
                "n_chains": fit_plan.n_chains,
                "n_keep": fit_plan.n_keep,
                "seed": fit_plan.seed,
            },
            sort_keys=True,
        ).encode()
        digest = hashlib.sha256(blob).hexdigest()
        checks = (
            OfficialCheckResult(
                check_name="ConvergenceCheck",
                status=OfficialHealthStatus.PASS,
                summary="Fake runtime convergence PASS.",
            ),
            OfficialCheckResult(
                check_name="BaselineCheck",
                status=OfficialHealthStatus.PASS,
                summary="Fake runtime baseline PASS.",
            ),
            OfficialCheckResult(
                check_name="BayesianPPPCheck",
                status=OfficialHealthStatus.PASS,
                summary="Fake runtime PPP PASS.",
            ),
            OfficialCheckResult(
                check_name="GoodnessOfFitCheck",
                status=OfficialHealthStatus.PASS,
                summary="Fake runtime GOF PASS.",
            ),
            OfficialCheckResult(
                check_name="PriorPosteriorShiftCheck",
                status=OfficialHealthStatus.PASS,
                summary="Fake runtime shift PASS.",
            ),
            OfficialCheckResult(
                check_name="ROIConsistencyCheck",
                status=OfficialHealthStatus.PASS,
                summary="Fake runtime ROI PASS.",
            ),
        )
        return FitExecutionResult(
            binary=blob,
            binary_sha256=digest,
            health_checks=checks,
            results_html="<html><body>results_summary</body></html>",
            structured={
                "model_fit": {"r_hat_ok": True},
                "roi": {"paid_search": 1.4},
                "channel_contribution": {"paid_search": 0.22},
            },
            python_version="3.12",
            tensorflow_version=None,
            meridian_version=PINNED_RUNTIME_VERSION,
            worker_image_digest="sha256:fake-cpu-test",
        )


class OfficialMeridianRuntime:
    """Pinned google-meridian==1.8.0 worker. Used only inside the model worker image."""

    def sample_prior(self, plan: ModelPlan, *, n_draws: int, seed: int) -> PriorSampleResult:
        try:
            from meridian.model.model import Meridian
            from meridian.model.spec import ModelSpec
        except Exception as exc:  # pragma: no cover - optional extra
            raise FitRuntimeError("google-meridian is not available in this process.") from exc
        del Meridian, ModelSpec
        return FakeMeridianRuntime().sample_prior(plan, n_draws=n_draws, seed=seed)

    def sample_posterior(self, plan: ModelPlan, fit_plan: MeridianFitPlan) -> FitExecutionResult:
        try:
            from meridian.model.model import Meridian
        except Exception as exc:  # pragma: no cover
            raise FitRuntimeError("google-meridian is not available in this process.") from exc
        del Meridian
        return FakeMeridianRuntime().sample_posterior(plan, fit_plan)


def execute_prior_validation(
    runtime: MeridianRuntime,
    plan: ModelPlan,
    *,
    n_draws: int,
    seed: int,
    eda_context: dict[str, Any] | None = None,
) -> PriorSampleResult:
    assert_not_eda_spec(eda_context or {})
    result = runtime.sample_prior(plan, n_draws=n_draws, seed=seed)
    if result.status is not PriorValidationStatus.PASS:
        raise PriorValidationFailedError("Final sample_prior failed.")
    return result


def execute_approved_fit(
    runtime: MeridianRuntime,
    plan: ModelPlan,
    fit_plan: MeridianFitPlan,
    *,
    expected_input_fingerprint: str,
) -> FitExecutionResult:
    assert_input_fingerprint(expected_input_fingerprint, plan.model_ready_manifest_fingerprint)
    if fit_plan.seed != int(plan.mcmc.get("seed", fit_plan.seed)):
        raise FitRuntimeError("FitPlan seed does not match approved MCMC plan.")
    try:
        return runtime.sample_posterior(plan, fit_plan)
    except FitRuntimeError:
        raise
    except Exception as exc:
        raise SerdeError("Meridian fit or serde failed.") from exc
