"""Private Evaluation launch surface. Service identity only. Not a customer API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict

from app.service.dependencies import get_control_plane
from app.service.errors import evaluation_dispatch_unavailable, service_identity_required
from app.service.evaluation_jobs import JobLaunchError
from app.service.evaluation_launch import EvaluationLaunchService
from app.service.security_log import security_log
from app.service.service_identity import ServiceIdentityVerifier

router = APIRouter(prefix="/internal/v1", include_in_schema=False)


class LaunchAck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dispatch_id: str
    status: str


def get_service_identity_verifier(request: Request) -> ServiceIdentityVerifier | None:
    return getattr(request.app.state, "service_identity_verifier", None)


def get_launch_service(request: Request) -> EvaluationLaunchService:
    service = getattr(request.app.state, "evaluation_launch", None)
    if service is None:
        raise RuntimeError("Evaluation launch service is not configured.")
    return service


@router.post(
    "/evaluation-dispatches/{dispatch_id}/launch",
    response_model=LaunchAck,
    include_in_schema=False,
)
async def launch_evaluation_dispatch(
    dispatch_id: str,
    request: Request,
    launch: Annotated[EvaluationLaunchService, Depends(get_launch_service)],
    verifier: Annotated[
        ServiceIdentityVerifier | None, Depends(get_service_identity_verifier)
    ],
    _control_plane: Annotated[object, Depends(get_control_plane)],
    x_cloudtasks_taskname: Annotated[str | None, Header(alias="X-CloudTasks-TaskName")] = None,
) -> LaunchAck:
    del x_cloudtasks_taskname
    if verifier is None:
        raise service_identity_required()
    verifier.verify(request.headers.get("authorization") or request.headers.get("Authorization"))
    try:
        result = launch.launch(dispatch_id)
    except JobLaunchError:
        security_log("evaluation.launch_http_failed", dispatch_id=dispatch_id)
        raise evaluation_dispatch_unavailable() from None
    return LaunchAck(dispatch_id=result["dispatch_id"], status=result["status"])


def unused_payload_guard(body: dict[str, Any] | None) -> None:
    """Cloud Task body is ignored. Path dispatch_id is the only identifier."""
    del body
