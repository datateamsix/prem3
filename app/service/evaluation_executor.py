"""In-process ADK Evaluation bridge.

Mission 10 qualifies local programmatic invocation.
M2-13 invokes this same bridge from the Cloud Run Evaluation worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.control_plane.repository import ControlPlaneRepository
from app.core.execution_context import bind_execution
from app.core.tenancy import bind_tenant, bind_workspace, require_tenant
from app.service.execution_from_evaluation import execution_context_from_evaluation


@dataclass(frozen=True, slots=True)
class EvaluationExecutionResult:
    run_id: str
    event_count: int
    tool_names: list[str] = field(default_factory=list)
    final_text: str | None = None


class EvaluationExecutor:
    """Trusted dispatch target: execute_evaluation(run_id) after server authorization.

    Not a public HTTP endpoint. M2-13 calls this from durable Cloud Run Job dispatch.
    Requires an already-bound TenantContext for foreign-tenant fail-closed lookup.
    """

    def __init__(
        self,
        *,
        repo: ControlPlaneRepository,
        agent: BaseAgent,
        app_name: str = "prem3",
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._app_name = app_name

    async def execute_evaluation(
        self,
        run_id: str,
        *,
        user_message: str = "Initialize the bound Dataset Evaluation.",
    ) -> EvaluationExecutionResult:
        tenant = require_tenant()
        evaluation = self._repo.get_evaluation_ref(
            tenant_id=tenant.tenant_id, run_id=run_id
        )
        if evaluation is None:
            raise LookupError("Evaluation not found for tenant.")

        service_tenant, workspace, execution = execution_context_from_evaluation(
            repo=self._repo,
            evaluation=evaluation,
            tenant=tenant,
        )

        session_service = InMemorySessionService()
        user_id = f"svc_{uuid4().hex[:16]}"
        session_id = f"sess_{uuid4().hex[:16]}"
        await session_service.create_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
        )
        runner = Runner(
            agent=self._agent,
            app_name=self._app_name,
            session_service=session_service,
        )

        tool_names: list[str] = []
        event_count = 0
        final_text: str | None = None
        try:
            with (
                bind_tenant(service_tenant),
                bind_workspace(workspace),
                bind_execution(execution),
            ):
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=user_message)],
                    ),
                ):
                    event_count += 1
                    for name in _tool_names_from_event(event):
                        if name not in tool_names:
                            tool_names.append(name)
                    text = _text_from_event(event)
                    if text:
                        final_text = text
        finally:
            await runner.close()

        return EvaluationExecutionResult(
            run_id=run_id,
            event_count=event_count,
            tool_names=tool_names,
            final_text=final_text,
        )


def _tool_names_from_event(event: object) -> list[str]:
    names: list[str] = []
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    for part in parts:
        function_call = getattr(part, "function_call", None)
        if function_call is not None and getattr(function_call, "name", None):
            names.append(str(function_call.name))
        function_response = getattr(part, "function_response", None)
        if function_response is not None and getattr(function_response, "name", None):
            names.append(str(function_response.name))
    return names


def _text_from_event(event: object) -> str | None:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    texts = [str(part.text) for part in parts if getattr(part, "text", None)]
    if not texts:
        return None
    return "".join(texts)
