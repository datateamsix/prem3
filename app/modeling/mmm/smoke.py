"""Official CPU smoke against installed google-meridian. No Recording/Fake library."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.modeling.common.errors import FitRuntimeError, GpuNotVisibleError, MeridianImportError
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.contracts import (
    ComputeProfile,
    FitPurpose,
    MeridianFitPlan,
    MeridianModelSpecProposal,
    MeridianRuntimeMode,
    ModelPlan,
)
from app.modeling.mmm.design import QUALIFICATION_MCMC
from app.modeling.mmm.meridian.runner import InstalledMeridianLibrary, OfficialMeridianRuntime

SMOKE_LABEL = "EXECUTION_COMPATIBILITY_ONLY"
SMOKE_WINDOW = ("2024-01-01", "2024-03-18")


def tiny_smoke_frame() -> Any:
    import pandas as pd

    start = date.fromisoformat(SMOKE_WINDOW[0])
    rows: list[dict[str, Any]] = []
    for geo, population in (("AA", 1_000.0), ("BB", 2_000.0)):
        for week in range(12):
            day = start + timedelta(weeks=week)
            rows.append(
                {
                    "time": datetime(day.year, day.month, day.day),
                    "geo": geo,
                    "population": population,
                    "revenue": 1_000.0 + week * 12.0 + (40.0 if geo == "BB" else 0.0),
                    "channel_impressions": 80.0 + week * 3.0 + (25.0 if geo == "BB" else 0.0),
                    "channel_spend": 40.0 + week * 2.0 + (12.0 if geo == "BB" else 0.0),
                    "control_a": 1.0
                    + (week % 3) * 0.1
                    + (0.8 if geo == "BB" else 0.0),
                }
            )
    return pd.DataFrame(rows)


def tiny_smoke_plan() -> ModelPlan:
    spec = MeridianModelSpecProposal(
        media_effects_dist="log_normal",
        media_prior_type="roi",
        max_lag=4,
        enable_aks=False,
        knots=3,
    )
    mcmc = {
        "n_chains": QUALIFICATION_MCMC["n_chains"],
        "n_adapt": QUALIFICATION_MCMC["n_adapt"],
        "n_burnin": QUALIFICATION_MCMC["n_burnin"],
        "n_keep": QUALIFICATION_MCMC["n_keep"],
        "seed": 1,
        "label": QUALIFICATION_MCMC["label"],
    }
    fingerprint = canonical_fingerprint(
        {
            "input": "official-cpu-smoke-tiny",
            "window": list(SMOKE_WINDOW),
            "spec": spec.model_dump(mode="json"),
            "mcmc": mcmc,
            "meridian_version": PINNED_RUNTIME_VERSION,
        }
    )
    return ModelPlan(
        model_plan_id="mplan_cpu_smoke",
        model_version_id="mver_cpu_smoke",
        model_ready_run_id="run_cpu_smoke",
        model_ready_manifest_fingerprint="official-cpu-smoke-tiny",
        model_window_start=SMOKE_WINDOW[0],
        model_window_end=SMOKE_WINDOW[1],
        scope="GEO",
        spec=spec,
        mcmc=mcmc,
        compute_profile=ComputeProfile.CPU_TEST,
        media_channels=("channel",),
        fingerprint=fingerprint,
    )


def tiny_smoke_fit_plan(plan: ModelPlan) -> MeridianFitPlan:
    payload = {
        "n_chains": int(plan.mcmc["n_chains"]),
        "n_adapt": int(plan.mcmc["n_adapt"]),
        "n_burnin": int(plan.mcmc["n_burnin"]),
        "n_keep": int(plan.mcmc["n_keep"]),
        "seed": int(plan.mcmc["seed"]),
        "compute_profile": ComputeProfile.CPU_TEST.value,
        "fit_purpose": FitPurpose.RUNTIME_QUALIFICATION.value,
        "input_fingerprint": plan.model_ready_manifest_fingerprint,
        "model_plan_fingerprint": plan.fingerprint,
    }
    return MeridianFitPlan(
        model_version_id=plan.model_version_id,
        model_plan_fingerprint=plan.fingerprint,
        meridian_version=PINNED_RUNTIME_VERSION,
        n_chains=int(plan.mcmc["n_chains"]),
        n_adapt=int(plan.mcmc["n_adapt"]),
        n_burnin=int(plan.mcmc["n_burnin"]),
        n_keep=int(plan.mcmc["n_keep"]),
        seed=int(plan.mcmc["seed"]),
        compute_profile=ComputeProfile.CPU_TEST,
        fit_purpose=FitPurpose.RUNTIME_QUALIFICATION,
        input_fingerprint=plan.model_ready_manifest_fingerprint,
        fingerprint=canonical_fingerprint(payload),
    )


def tiny_smoke_mapping() -> dict[str, Any]:
    return {
        "fingerprint": "official-cpu-smoke-tiny",
        "frame": tiny_smoke_frame(),
        "kpi": "revenue",
        "kpi_type": "revenue",
        "time": "time",
        "geo": "geo",
        "population": "population",
        "media": ("channel_impressions",),
        "media_spend": ("channel_spend",),
        "media_channels": ("channel",),
        "controls": ("control_a",),
    }


def resolve_fit_input_mapping(plan: ModelPlan) -> dict[str, Any]:
    """Server-owned mapping for the worker. Qualification uses the tiny fixture."""
    if plan.model_ready_manifest_fingerprint == "official-cpu-smoke-tiny":
        return tiny_smoke_mapping()
    raise FitRuntimeError("INPUT_CONTRACT_MISMATCH: ModelReady frame is missing.")


def _pass_fail(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_official_cpu_smoke(*, artifact_path: str | None = None) -> dict[str, Any]:
    """Execute real Meridian APIs. RecordingMeridianLibrary is forbidden here."""
    started = datetime.now(UTC)
    stages = {
        "sample_prior": "FAIL",
        "sample_posterior": "FAIL",
        "serde_save": "FAIL",
        "serde_load": "FAIL",
        "reviewer": "FAIL",
        "summarizer": "FAIL",
    }
    try:
        library = InstalledMeridianLibrary.load()
    except FitRuntimeError as exc:
        raise MeridianImportError(str(exc)) from exc
    if type(library).__name__ == "RecordingMeridianLibrary":
        raise FitRuntimeError("RecordingMeridianLibrary cannot satisfy official CPU smoke.")
    plan = tiny_smoke_plan()
    fit_plan = tiny_smoke_fit_plan(plan)
    runtime = OfficialMeridianRuntime(
        mode=MeridianRuntimeMode.OFFICIAL_CPU_SMOKE,
        library=library,
        input_mapping=tiny_smoke_mapping(),
    )
    result = runtime.sample_posterior(plan, fit_plan)
    calls = set(result.calls_made)
    stages["sample_prior"] = _pass_fail("sample_prior" in calls)
    stages["sample_posterior"] = _pass_fail("sample_posterior" in calls)
    stages["serde_save"] = _pass_fail("save_meridian" in calls)
    stages["serde_load"] = _pass_fail("load_meridian" in calls)
    stages["reviewer"] = _pass_fail("ModelReviewer" in calls)
    stages["summarizer"] = _pass_fail("Summarizer" in calls)
    if any(value == "FAIL" for value in stages.values()):
        raise FitRuntimeError(f"Official CPU smoke missed required calls: {stages}")
    completed = datetime.now(UTC)
    payload = {
        "label": SMOKE_LABEL,
        "runtime_mode": MeridianRuntimeMode.OFFICIAL_CPU_SMOKE.value,
        "fit_purpose": FitPurpose.RUNTIME_QUALIFICATION.value,
        "python_version": result.python_version or platform.python_version(),
        "meridian_version": result.meridian_version,
        "tensorflow_version": result.tensorflow_version,
        "platform": platform.platform(),
        "fixture": "tiny-geo-12-weeks-2-geos-1-channel",
        "mcmc": {
            "n_chains": fit_plan.n_chains,
            "n_adapt": fit_plan.n_adapt,
            "n_burnin": fit_plan.n_burnin,
            "n_keep": fit_plan.n_keep,
            "seed": fit_plan.seed,
        },
        "sample_prior": stages["sample_prior"],
        "sample_posterior": stages["sample_posterior"],
        "serde_save": stages["serde_save"],
        "serde_load": stages["serde_load"],
        "reviewer": stages["reviewer"],
        "summarizer": stages["summarizer"],
        "reviewer_checks": [
            {
                "check_name": item.check_name,
                "status": item.status.value,
                "summary": item.summary,
            }
            for item in result.health_checks
        ],
        "model_artifact_sha256": result.binary_sha256,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "completed_at": completed.isoformat().replace("+00:00", "Z"),
        "duration_seconds": (completed - started).total_seconds(),
        "eligible_for_customer_conclusions": False,
        "library_class": type(library).__name__,
    }
    if artifact_path:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["artifact_path"] = str(path)
        payload["artifact_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return payload


def run_import_smoke() -> dict[str, Any]:
    try:
        import meridian
        import tensorflow as tf
        from meridian.analysis import summarizer
        from meridian.analysis.review import reviewer
        from meridian.data import data_frame_input_data_builder as data_builder
        from meridian.model.model import Meridian
        from meridian.model.prior_distribution import PriorDistribution
        from meridian.model.spec import ModelSpec
        from meridian.schema.serde import meridian_serde
    except Exception as exc:
        raise MeridianImportError(f"MERIDIAN_IMPORT_FAILED: {exc}") from exc
    gpu = [str(item) for item in tf.config.list_physical_devices("GPU")]
    return {
        "meridian_version": getattr(meridian, "__version__", None),
        "tensorflow_version": getattr(tf, "__version__", None),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "gpu_devices": gpu,
        "imports": {
            "DataFrameInputDataBuilder": data_builder.DataFrameInputDataBuilder.__name__,
            "ModelSpec": ModelSpec.__name__,
            "PriorDistribution": PriorDistribution.__name__,
            "Meridian": Meridian.__name__,
            "ModelReviewer": reviewer.ModelReviewer.__name__,
            "Summarizer": summarizer.Summarizer.__name__,
            "serde": meridian_serde.__name__,
        },
        "expected_meridian_version": PINNED_RUNTIME_VERSION,
        "version_match": str(getattr(meridian, "__version__", "")) == PINNED_RUNTIME_VERSION,
    }


def run_gpu_detect(*, require_gpu: bool = True) -> dict[str, Any]:
    payload = run_import_smoke()
    if require_gpu and not payload["gpu_devices"]:
        raise GpuNotVisibleError("GPU_NOT_VISIBLE: TensorFlow listed no GPU devices.")
    payload["gpu_required"] = require_gpu
    payload["gpu_visible"] = bool(payload["gpu_devices"])
    return payload
