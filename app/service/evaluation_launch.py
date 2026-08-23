"""Internal Cloud Tasks launch handler. Starts the Job; does not run ADK."""

from __future__ import annotations

from app.control_plane.dispatch_claims import mark_launching, utc_now
from app.control_plane.models import DispatchStatus
from app.control_plane.repository import ControlPlaneRepository
from app.service.errors import resource_not_found
from app.service.evaluation_jobs import EvaluationJobLauncher, JobLaunchError
from app.service.security_log import security_log


class EvaluationLaunchService:
    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        launcher: EvaluationJobLauncher,
    ) -> None:
        self._repo = repo
        self._launcher = launcher

    def launch(self, dispatch_id: str) -> dict[str, str]:
        dispatch = self._repo.get_evaluation_dispatch(dispatch_id)
        if dispatch is None:
            raise resource_not_found()
        if dispatch.status in {
            DispatchStatus.RUNNING,
            DispatchStatus.SUCCEEDED,
            DispatchStatus.FAILED_TERMINAL,
        }:
            security_log(
                "evaluation.launch_skipped",
                dispatch_id=dispatch_id,
                status=dispatch.status.value,
            )
            return {"dispatch_id": dispatch_id, "status": dispatch.status.value}
        try:
            execution_name = self._launcher.launch(dispatch.dispatch_id)
        except JobLaunchError:
            security_log("evaluation.launch_failed", dispatch_id=dispatch_id)
            raise
        updated = mark_launching(
            dispatch, now=utc_now(), execution_name=execution_name or None
        )
        stored = self._repo.put_evaluation_dispatch(updated)
        security_log(
            "evaluation.job_launched",
            dispatch_id=dispatch_id,
            run_id=stored.run_id,
        )
        return {"dispatch_id": dispatch_id, "status": stored.status.value}
