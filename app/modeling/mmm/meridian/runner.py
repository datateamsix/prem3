"""Known Meridian worker path. Never executes generated scripts."""

from __future__ import annotations

import hashlib
import json
import platform
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.modeling.common.errors import FitRuntimeError, PriorValidationFailedError, SerdeError
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.mmm.contracts import (
    ComputeProfile,
    MeridianFitPlan,
    MeridianRuntimeMode,
    ModelPlan,
    OfficialCheckResult,
    OfficialHealthStatus,
    PriorValidationStatus,
    ReviewSource,
)
from app.modeling.mmm.meridian.builder import (
    assert_input_fingerprint,
    assert_not_eda_spec,
    compile_input_mapping,
)


@dataclass(frozen=True)
class PriorSampleResult:
    status: PriorValidationStatus
    n_draws: int
    seed: int
    warnings: tuple[str, ...] = ()
    artifact: bytes = b""
    runtime_mode: MeridianRuntimeMode = MeridianRuntimeMode.FAKE_TEST
    calls_made: tuple[str, ...] = ()


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
    runtime_mode: MeridianRuntimeMode = MeridianRuntimeMode.FAKE_TEST
    review_source: ReviewSource = ReviewSource.FAKE_TEST
    calls_made: tuple[str, ...] = ()
    serde_readback_ok: bool = False
    health_html: str = ""
    results_html_sha256: str | None = None


class MeridianRuntime(Protocol):
    runtime_mode: MeridianRuntimeMode

    def sample_prior(self, plan: ModelPlan, *, n_draws: int, seed: int) -> PriorSampleResult: ...

    def sample_posterior(
        self, plan: ModelPlan, fit_plan: MeridianFitPlan
    ) -> FitExecutionResult: ...


class MeridianLibrary(Protocol):
    """Real google-meridian surface. Test stubs must not be FakeMeridianRuntime."""

    def sample_prior(self, model: Any, *, n_draws: int, seed: int) -> None: ...

    def sample_posterior(
        self,
        model: Any,
        *,
        n_chains: int,
        n_adapt: int,
        n_burnin: int,
        n_keep: int,
        seed: int,
    ) -> None: ...

    def save_meridian(self, model: Any, path: str) -> None: ...

    def load_meridian(self, path: str) -> Any: ...

    def run_reviewer(self, model: Any) -> tuple[OfficialCheckResult, ...]: ...

    def run_summarizer(self, model: Any, *, start: str, end: str) -> str: ...

    def construct_model(self, plan: ModelPlan, mapping: dict[str, Any]) -> Any: ...

    def structured_outputs(self, model: Any) -> dict[str, Any]: ...


class FakeMeridianRuntime:
    """Explicit CI twin. Never eligible for production MODEL_ACCEPTED."""

    runtime_mode = MeridianRuntimeMode.FAKE_TEST

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
            runtime_mode=MeridianRuntimeMode.FAKE_TEST,
            calls_made=("fake_sample_prior",),
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
        html = "<html><body>results_summary</body></html>"
        return FitExecutionResult(
            binary=blob,
            binary_sha256=digest,
            health_checks=checks,
            results_html=html,
            structured={
                "model_fit": {"r_hat_ok": True},
                "roi": {"paid_search": 1.4},
                "channel_contribution": {"paid_search": 0.22},
            },
            python_version="3.12",
            tensorflow_version=None,
            meridian_version=PINNED_RUNTIME_VERSION,
            worker_image_digest="sha256:fake-cpu-test",
            runtime_mode=MeridianRuntimeMode.FAKE_TEST,
            review_source=ReviewSource.FAKE_TEST,
            calls_made=("fake_sample_posterior", "fake_serde", "fake_reviewer"),
            serde_readback_ok=True,
            health_html="<html><body>model_health</body></html>",
            results_html_sha256=hashlib.sha256(html.encode()).hexdigest(),
        )


class InstalledMeridianLibrary:
    """Pinned google-meridian==1.8.0. Fail closed if the package is missing."""

    def __init__(self, modules: dict[str, Any]) -> None:
        self._modules = modules
        self.calls: list[str] = []

    @classmethod
    def load(cls) -> InstalledMeridianLibrary:
        try:
            from meridian.analysis import summarizer
            from meridian.analysis.review import reviewer
            from meridian.data import data_frame_input_data_builder as data_builder
            from meridian.model.model import Meridian
            from meridian.model.prior_distribution import PriorDistribution
            from meridian.model.spec import ModelSpec
            from meridian.schema.serde import meridian_serde
        except Exception as exc:
            raise FitRuntimeError(
                "google-meridian is not available; OfficialMeridianRuntime fails closed."
            ) from exc
        return cls(
            {
                "Meridian": Meridian,
                "ModelSpec": ModelSpec,
                "PriorDistribution": PriorDistribution,
                "data_builder": data_builder,
                "meridian_serde": meridian_serde,
                "reviewer": reviewer,
                "summarizer": summarizer,
            }
        )

    def construct_model(self, plan: ModelPlan, mapping: dict[str, Any]) -> Any:
        frame = mapping.get("frame")
        if frame is None:
            raise FitRuntimeError("INPUT_CONTRACT_MISMATCH: ModelReady frame is missing.")
        builder_mod = self._modules["data_builder"]
        kpi_type = str(mapping.get("kpi_type") or "revenue")
        builder = builder_mod.DataFrameInputDataBuilder(
            kpi_type=kpi_type,
            default_kpi_column=mapping["kpi"],
            default_revenue_per_kpi_column=mapping.get("revenue_per_kpi"),
            default_time_column=mapping["time"],
            default_geo_column=mapping.get("geo") or "geo",
            default_population_column=mapping.get("population") or "population",
            default_media_time_column=mapping["time"],
        )
        builder = builder.with_kpi(frame, kpi_col=mapping["kpi"])
        media = tuple(mapping.get("media") or ())
        media_spend = tuple(mapping.get("media_spend") or ())
        media_channels = tuple(mapping.get("media_channels") or ())
        if media:
            builder = builder.with_media(
                frame,
                media_cols=list(media),
                media_spend_cols=list(media_spend),
                media_channels=list(media_channels or media),
            )
        rf = tuple(mapping.get("rf") or ())
        if rf and hasattr(builder, "with_reach_frequency"):
            builder = builder.with_reach_frequency(frame, **mapping["rf_kwargs"])
        if mapping.get("organic_media"):
            builder = builder.with_organic_media(
                frame,
                organic_media_cols=list(mapping["organic_media"]),
                organic_media_channels=list(
                    mapping.get("organic_media_channels") or mapping["organic_media"]
                ),
            )
        if mapping.get("controls"):
            builder = builder.with_controls(frame, control_cols=list(mapping["controls"]))
        if mapping.get("non_media_treatments") and hasattr(builder, "with_non_media_treatments"):
            builder = builder.with_non_media_treatments(
                frame, non_media_treatment_cols=list(mapping["non_media_treatments"])
            )
        if mapping.get("population"):
            builder = builder.with_population(frame, population_col=mapping["population"])
        if kpi_type == "non_revenue" and mapping.get("revenue_per_kpi"):
            builder = builder.with_revenue_per_kpi(
                frame, revenue_per_kpi_col=mapping["revenue_per_kpi"]
            )
        input_data = builder.build()
        spec_kwargs = plan.spec.model_dump(mode="python", exclude_none=True)
        spec_kwargs.pop("paid_media_prior_type", None)
        spec = self._modules["ModelSpec"](
            prior=self._modules["PriorDistribution"](),
            **spec_kwargs,
        )
        self.calls.append("DataFrameInputDataBuilder")
        self.calls.append("ModelSpec")
        self.calls.append("Meridian")
        return self._modules["Meridian"](input_data=input_data, model_spec=spec)

    def sample_prior(self, model: Any, *, n_draws: int, seed: int) -> None:
        del seed
        self.calls.append("sample_prior")
        model.sample_prior(n_draws)

    def sample_posterior(
        self,
        model: Any,
        *,
        n_chains: int,
        n_adapt: int,
        n_burnin: int,
        n_keep: int,
        seed: int,
    ) -> None:
        del seed
        self.calls.append("sample_posterior")
        model.sample_posterior(
            n_chains=n_chains,
            n_adapt=n_adapt,
            n_burnin=n_burnin,
            n_keep=n_keep,
        )

    def save_meridian(self, model: Any, path: str) -> None:
        self.calls.append("save_meridian")
        self._modules["meridian_serde"].save_meridian(model, path)

    def load_meridian(self, path: str) -> Any:
        self.calls.append("load_meridian")
        return self._modules["meridian_serde"].load_meridian(path)

    def run_reviewer(self, model: Any) -> tuple[OfficialCheckResult, ...]:
        self.calls.append("ModelReviewer")
        review = self._modules["reviewer"].ModelReviewer(
            model_context=model.model_context,
            inference_data=model.inference_data,
        )
        summary = review.run()
        return _map_official_review(summary)

    def run_summarizer(self, model: Any, *, start: str, end: str) -> str:
        self.calls.append("Summarizer")
        with tempfile.TemporaryDirectory() as tmp:
            out = self._modules["summarizer"].Summarizer(model, use_kpi=True)
            out.output_model_results_summary(
                filename="results_summary.html",
                filepath=tmp,
                start_date=start,
                end_date=end,
            )
            html_path = Path(tmp) / "results_summary.html"
            if html_path.is_file():
                return html_path.read_text(encoding="utf-8")
        return ""

    def structured_outputs(self, model: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        try:
            from meridian.analysis import analyzer as analyzer_mod
        except Exception:
            return payload
        ctor = getattr(analyzer_mod, "Analyzer", None)
        if ctor is None:
            return payload
        try:
            anal = ctor(model)
        except Exception:
            return payload
        for name in (
            "roi",
            "incremental_outcome",
            "contribution",
            "marginal_roi",
        ):
            fn = getattr(anal, name, None)
            if not callable(fn):
                continue
            try:
                value = fn()
            except Exception:
                continue
            converted = _jsonable_metric(value)
            if converted is None:
                continue
            payload[name] = converted
        return payload


def _jsonable_metric(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "numpy"):
        try:
            value = value.numpy()
        except Exception:
            return None
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable_metric(item) for key, item in value.items()}
    return None


def _official_status_name(item: Any) -> str:
    case = getattr(item, "case", None)
    status = getattr(case, "status", None) if case is not None else None
    if status is None:
        status = getattr(item, "status", None)
    if status is None:
        return ""
    name = getattr(status, "name", None)
    if name:
        return str(name).upper()
    value = getattr(status, "value", None)
    if isinstance(value, str):
        return value.upper()
    raw = str(status).split(".")[-1]
    return raw.upper()


def _official_check_name(item: Any) -> str:
    name = str(getattr(item, "name", None) or getattr(item, "check_name", "") or "")
    if name:
        return name
    cls = type(item).__name__
    if cls.endswith("CheckResult"):
        return cls[: -len("Result")]
    if cls.endswith("Result"):
        return cls[: -len("Result")]
    return cls


def _map_official_review(summary: Any) -> tuple[OfficialCheckResult, ...]:
    checks = (
        getattr(summary, "results", None)
        or getattr(summary, "checks", None)
        or getattr(summary, "check_results", None)
    )
    if not checks:
        raise FitRuntimeError("Official ModelReviewer returned no check results.")
    mapped: list[OfficialCheckResult] = []
    for item in checks:
        name = _official_check_name(item)
        raw = _official_status_name(item)
        if raw not in OfficialHealthStatus.__members__:
            raise FitRuntimeError(f"Official reviewer status {raw!r} is not PASS/REVIEW/FAIL.")
        if not name:
            raise FitRuntimeError("Official reviewer check is missing a name.")
        rec = getattr(item, "recommendation", None)
        if rec is None:
            case = getattr(item, "case", None)
            rec = getattr(case, "recommendation", None) if case is not None else None
        mapped.append(
            OfficialCheckResult(
                check_name=name,
                status=OfficialHealthStatus(raw),
                summary=str(
                    rec
                    or getattr(item, "summary", None)
                    or getattr(item, "message", "")
                    or ""
                ),
            )
        )
    return tuple(mapped)


@dataclass
class RecordingMeridianLibrary:
    """Official-runtime test double. Not FakeMeridianRuntime and not production evidence."""

    checks: tuple[OfficialCheckResult, ...]
    calls: list[str] = field(default_factory=list)
    binary: bytes = b"official-stub-binpb"

    def construct_model(self, plan: ModelPlan, mapping: dict[str, Any]) -> Any:
        del mapping
        self.calls.append("DataFrameInputDataBuilder")
        self.calls.append("ModelSpec")
        self.calls.append("Meridian")
        return {"plan": plan.fingerprint}

    def sample_prior(self, model: Any, *, n_draws: int, seed: int) -> None:
        del model, n_draws, seed
        self.calls.append("sample_prior")

    def sample_posterior(
        self,
        model: Any,
        *,
        n_chains: int,
        n_adapt: int,
        n_burnin: int,
        n_keep: int,
        seed: int,
    ) -> None:
        del model, n_chains, n_adapt, n_burnin, n_keep, seed
        self.calls.append("sample_posterior")

    def save_meridian(self, model: Any, path: str) -> None:
        del model
        self.calls.append("save_meridian")
        Path(path).write_bytes(self.binary)

    def load_meridian(self, path: str) -> Any:
        self.calls.append("load_meridian")
        payload = Path(path).read_bytes()
        if payload != self.binary:
            raise SerdeError("serde read-back did not match saved bytes.")
        return {"loaded": True}

    def run_reviewer(self, model: Any) -> tuple[OfficialCheckResult, ...]:
        del model
        self.calls.append("ModelReviewer")
        return self.checks

    def run_summarizer(self, model: Any, *, start: str, end: str) -> str:
        del model, start, end
        self.calls.append("Summarizer")
        return "<html><body>official-stub-results</body></html>"

    def structured_outputs(self, model: Any) -> dict[str, Any]:
        del model
        return {}


class OfficialMeridianRuntime:
    """Pinned google-meridian worker. Never falls back to FakeMeridianRuntime."""

    def __init__(
        self,
        *,
        mode: MeridianRuntimeMode,
        library: MeridianLibrary | None = None,
        input_mapping: dict[str, Any] | None = None,
        worker_image_digest: str | None = None,
    ) -> None:
        if mode is MeridianRuntimeMode.FAKE_TEST:
            raise FitRuntimeError("OfficialMeridianRuntime cannot run FAKE_TEST.")
        self.runtime_mode = mode
        self._library = library
        self._input_mapping = input_mapping or {}
        self.worker_image_digest = worker_image_digest

    def _library_or_fail(self) -> MeridianLibrary:
        if self._library is not None:
            return self._library
        self._library = InstalledMeridianLibrary.load()
        return self._library

    def sample_prior(self, plan: ModelPlan, *, n_draws: int, seed: int) -> PriorSampleResult:
        if n_draws < 1:
            raise PriorValidationFailedError("n_draws must be positive.")
        library = self._library_or_fail()
        mapping = compile_input_mapping(plan=plan, mapping=self._input_mapping)
        model = library.construct_model(plan, mapping)
        library.sample_prior(model, n_draws=n_draws, seed=seed)
        calls = tuple(getattr(library, "calls", ("sample_prior",)))
        return PriorSampleResult(
            status=PriorValidationStatus.PASS,
            n_draws=n_draws,
            seed=seed,
            runtime_mode=self.runtime_mode,
            calls_made=calls,
        )

    def sample_posterior(self, plan: ModelPlan, fit_plan: MeridianFitPlan) -> FitExecutionResult:
        if fit_plan.model_plan_fingerprint != plan.fingerprint:
            raise FitRuntimeError("FitPlan fingerprint does not match ModelPlan.")
        if (
            fit_plan.n_chains != int(plan.mcmc.get("n_chains", fit_plan.n_chains))
            or fit_plan.n_adapt != int(plan.mcmc.get("n_adapt", fit_plan.n_adapt))
            or fit_plan.n_burnin != int(plan.mcmc.get("n_burnin", fit_plan.n_burnin))
            or fit_plan.n_keep != int(plan.mcmc.get("n_keep", fit_plan.n_keep))
        ):
            raise FitRuntimeError("Worker must not mutate approved MCMC settings.")
        library = self._library_or_fail()
        mapping = compile_input_mapping(plan=plan, mapping=self._input_mapping)
        model = library.construct_model(plan, mapping)
        library.sample_prior(model, n_draws=max(1, min(32, fit_plan.n_keep)), seed=fit_plan.seed)
        library.sample_posterior(
            model,
            n_chains=fit_plan.n_chains,
            n_adapt=fit_plan.n_adapt,
            n_burnin=fit_plan.n_burnin,
            n_keep=fit_plan.n_keep,
            seed=fit_plan.seed,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "meridian_model.binpb")
            library.save_meridian(model, path)
            payload = Path(path).read_bytes()
            if not payload:
                raise SerdeError("Official serde produced an empty model binary.")
            loaded = library.load_meridian(path)
            if loaded is None:
                raise SerdeError("Official serde read-back failed.")
        checks = library.run_reviewer(model)
        html = library.run_summarizer(
            model, start=plan.model_window_start, end=plan.model_window_end
        )
        digest = hashlib.sha256(payload).hexdigest()
        tensorflow_version = None
        try:
            import tensorflow as tf

            tensorflow_version = getattr(tf, "__version__", None)
        except Exception:
            tensorflow_version = None
        calls = tuple(getattr(library, "calls", ()))
        return FitExecutionResult(
            binary=payload,
            binary_sha256=digest,
            health_checks=checks,
            results_html=html,
            structured=library.structured_outputs(model),
            python_version=platform.python_version(),
            tensorflow_version=tensorflow_version,
            meridian_version=PINNED_RUNTIME_VERSION,
            worker_image_digest=self.worker_image_digest,
            runtime_mode=self.runtime_mode,
            review_source=ReviewSource.OFFICIAL_MERIDIAN,
            calls_made=calls,
            serde_readback_ok=True,
            health_html="",
            results_html_sha256=hashlib.sha256(html.encode()).hexdigest() if html else None,
        )


def runtime_mode_for_profile(profile: str, *, official: bool) -> MeridianRuntimeMode:
    if not official:
        return MeridianRuntimeMode.FAKE_TEST
    if profile == ComputeProfile.CPU_TEST.value:
        return MeridianRuntimeMode.OFFICIAL_CPU_SMOKE
    if profile in {
        ComputeProfile.CPU_STANDARD.value,
        ComputeProfile.CPU_LARGE.value,
    }:
        return MeridianRuntimeMode.OFFICIAL_CPU
    if profile in {
        ComputeProfile.GPU_STANDARD.value,
        ComputeProfile.GPU_LARGE.value,
    }:
        return MeridianRuntimeMode.OFFICIAL_GPU
    raise FitRuntimeError(f"Unsupported compute profile {profile}.")


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
