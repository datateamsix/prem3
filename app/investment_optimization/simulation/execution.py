"""Simulation execution adapters. Production must not silently install local."""

from __future__ import annotations

from typing import Protocol

from app.investment_optimization.errors import (
    LiveSimulationJobProofPendingError,
    SimulationRuntimeUnavailableError,
)
from app.service.evaluation_jobs import CloudRunEvaluationJobLauncher


class SimulationExecutionAdapter(Protocol):
    def dispatch(self, simulation_run_id: str) -> str: ...


class LocalSimulationExecutionAdapter:
    """Test-only / explicit local adapter. Must not be wired in create_app."""

    def __init__(self, runner: object | None = None) -> None:
        self._runner = runner
        self.calls: list[str] = []

    def dispatch(self, simulation_run_id: str) -> str:
        self.calls.append(simulation_run_id)
        if self._runner is not None:
            self._runner(simulation_run_id)
        return f"local-{simulation_run_id}"


class UnavailableSimulationExecutionAdapter:
    def dispatch(self, simulation_run_id: str) -> str:
        del simulation_run_id
        raise SimulationRuntimeUnavailableError("Simulation runtime is not configured.")


class CloudRunSimulationExecutionAdapter:
    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        job_name: str,
        client: object | None = None,
    ) -> None:
        self._launcher = CloudRunEvaluationJobLauncher(
            project_id=project_id,
            location=location,
            job_name=job_name,
            client=client,
            dispatch_env_var="PREM3_SIMULATION_RUN_ID",
        )

    def dispatch(self, simulation_run_id: str) -> str:
        try:
            return self._launcher.launch(simulation_run_id)
        except Exception as exc:
            raise LiveSimulationJobProofPendingError(
                "Live Cloud Run simulation job proof is pending."
            ) from exc
