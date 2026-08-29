"""Operational CPU feasibility for official FINAL_MODEL. Does not mutate MCMC."""

from __future__ import annotations

from enum import StrEnum

from app.modeling.mmm.coverage import MUSIC_CENTER_MODEL_READY_COVERAGE

# Tiny official CPU smoke: 12 weeks × 2 geos, 1 chain, 8/2/2, ~140s wall.
QUALIFICATION_SMOKE_SECONDS = 140.0
QUALIFICATION_SMOKE_OBSERVATIONS = 12 * 2
QUALIFICATION_SMOKE_DRAWS = 1 * (8 + 2 + 2)


class CpuFeasibility(StrEnum):
    EXPECTED_FEASIBLE = "EXPECTED_FEASIBLE"
    EXPECTED_SLOW = "EXPECTED_SLOW"
    NOT_FEASIBLE = "NOT_FEASIBLE"


def estimate_official_cpu_final_feasibility(
    *,
    n_times: int,
    n_geos: int,
    n_chains: int,
    n_adapt: int,
    n_burnin: int,
    n_keep: int,
    timeout_seconds: int,
    smoke_seconds: float = QUALIFICATION_SMOKE_SECONDS,
) -> tuple[CpuFeasibility, str, float]:
    observations = max(1, n_times * n_geos)
    draws = max(1, n_chains * (n_adapt + n_burnin + n_keep))
    scaled = smoke_seconds * (observations / QUALIFICATION_SMOKE_OBSERVATIONS) * (
        draws / QUALIFICATION_SMOKE_DRAWS
    )
    rationale = (
        f"Scaled from official CPU smoke ({smoke_seconds:.0f}s, "
        f"{QUALIFICATION_SMOKE_OBSERVATIONS} obs, {QUALIFICATION_SMOKE_DRAWS} draws) "
        f"to {observations} obs and {draws} draws → ~{scaled:.0f}s vs "
        f"Cloud Run timeout {timeout_seconds}s. MCMC is not reduced."
    )
    if scaled > timeout_seconds:
        return CpuFeasibility.NOT_FEASIBLE, rationale, scaled
    if scaled > timeout_seconds * 0.5:
        return CpuFeasibility.EXPECTED_SLOW, rationale, scaled
    return CpuFeasibility.EXPECTED_FEASIBLE, rationale, scaled


def music_center_cpu_final_feasibility(
    *,
    n_chains: int,
    n_adapt: int,
    n_burnin: int,
    n_keep: int,
    timeout_seconds: int = 3600,
) -> tuple[CpuFeasibility, str, float]:
    coverage = MUSIC_CENTER_MODEL_READY_COVERAGE
    return estimate_official_cpu_final_feasibility(
        n_times=coverage.n_times or 0,
        n_geos=coverage.n_geos or 0,
        n_chains=n_chains,
        n_adapt=n_adapt,
        n_burnin=n_burnin,
        n_keep=n_keep,
        timeout_seconds=timeout_seconds,
    )
