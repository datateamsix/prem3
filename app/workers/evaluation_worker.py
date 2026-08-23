"""Cloud Run Job entrypoint. Reads only PREM3_EVALUATION_DISPATCH_ID."""

from __future__ import annotations

import asyncio
import os
import sys

from app.agent import root_agent
from app.config import load_settings
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.service.evaluation_executor import EvaluationExecutor
from app.workers.evaluation_runtime import claim_owner_from_env, execute_claimed_dispatch


def main() -> int:
    dispatch_id = (os.environ.get("PREM3_EVALUATION_DISPATCH_ID") or "").strip()
    if not dispatch_id:
        return 1
    settings = load_settings()
    repo = FirestoreControlPlaneRepository.from_settings(
        project_id=settings.project_id,
        database=settings.firestore_database,
    )
    executor = EvaluationExecutor(repo=repo, agent=root_agent)
    execution_name, owner = claim_owner_from_env()
    return execute_claimed_dispatch(
        repo=repo,
        executor=executor,
        dispatch_id=dispatch_id,
        owner=owner,
        execution_name=execution_name,
        run_async=asyncio.run,
    )


if __name__ == "__main__":
    sys.exit(main())
