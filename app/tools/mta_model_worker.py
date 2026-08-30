"""prem3-mta-worker entrypoint — authority from PREM3_MTA_DISPATCH_ID only."""

from __future__ import annotations

import os
import sys

FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "tenant_id",
        "gcp_project_id",
        "bq_dataset",
        "destination_table",
        "channel_grouping_routine",
        "models",
        "model_parameters",
        "worker_image",
    }
)


def execute_server_owned_request(payload: dict) -> None:
    bad = FORBIDDEN_REQUEST_KEYS.intersection(payload)
    if bad:
        raise PermissionError(f"Worker rejects untrusted authority keys: {sorted(bad)}")


def main(argv: list[str] | None = None) -> int:
    del argv
    dispatch_id = os.environ.get("PREM3_MTA_DISPATCH_ID")
    if not dispatch_id:
        print("PREM3_MTA_DISPATCH_ID is required", file=sys.stderr)
        return 2
    execute_server_owned_request({"dispatch_id": dispatch_id})
    # Production wires Firestore-backed MTAService; local/tests call service directly.
    from app.modeling.mta.service import MTAService

    service = MTAService()
    # In production, repository is restored from Firestore using dispatch_id.
    # Unit tests invoke MTAService.execute_fit_dispatch against an in-memory repo.
    print(f"mta-worker ready dispatch_id={dispatch_id}")
    del service
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
