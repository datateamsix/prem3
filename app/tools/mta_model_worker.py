"""prem3-mta-worker entrypoint — authority from PREM3_MTA_DISPATCH_ID only."""

from __future__ import annotations

import os
import sys

from app.modeling.mta.adapters.dp6_mam_v1_0_11 import DP6MAMAdapter
from app.modeling.mta.dispatch import FakeMTADispatcher
from app.modeling.mta.jobs import FakeMTAJobLauncher
from app.modeling.mta.readback import (
    BigQueryResultStore,
    HybridResultStore,
)
from app.modeling.mta.runtime_bundle import (
    bundle_journeys,
    hydrate_runtime_bundle,
    persist_runtime_receipt,
)
from app.modeling.mta.service import MTAService

try:
    from google.cloud import firestore
except ImportError:  # pragma: no cover - local unit tests
    firestore = None

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
    if not bad:
        return
    raise PermissionError(f"Worker rejects untrusted authority keys: {sorted(bad)}")


def _build_service(dispatch_id: str) -> tuple[MTAService, str]:
    adapter = DP6MAMAdapter(fake=False)
    firestore_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get(
        "M3_GCP_PROJECT"
    )
    if firestore_project and os.environ.get("PREM3_MTA_CLOUD_RUNTIME") == "1":
        if firestore is None:
            raise RuntimeError("google-cloud-firestore is required for cloud MTA runtime")
        client = firestore.Client(project=firestore_project)
        repo = hydrate_runtime_bundle(client, dispatch_id=dispatch_id)
        journeys = bundle_journeys(client, dispatch_id=dispatch_id)
        store = HybridResultStore(BigQueryResultStore(project_id=firestore_project))
        service = MTAService(
            repo=repo,
            dispatcher=FakeMTADispatcher(),
            result_store=store,
            dp6=adapter,
            job_launcher=FakeMTAJobLauncher(),
            firestore_client=client,
        )
        run = next(iter(repo.runs.values()))
        store.write(f"_journeys_{run.run_id}", journeys)
        return service, dispatch_id
    service = MTAService(dp6=adapter)
    return service, dispatch_id


def main(argv: list[str] | None = None) -> int:
    del argv
    dispatch_id = os.environ.get("PREM3_MTA_DISPATCH_ID")
    if not dispatch_id:
        print("PREM3_MTA_DISPATCH_ID is required", file=sys.stderr)
        return 2
    execute_server_owned_request({"dispatch_id": dispatch_id})
    service, resolved = _build_service(dispatch_id)
    receipt = service.execute_fit_dispatch(dispatch_id=resolved)
    if service.firestore_client is not None:
        run = service.repo.get_run(receipt.run_id)
        if run is not None:
            persist_runtime_receipt(
                service.firestore_client,
                dispatch_id=resolved,
                receipt=receipt,
                run=run,
            )
    print(
        f"mta-worker complete dispatch_id={dispatch_id} "
        f"receipt={receipt.receipt_id} status={receipt.status.value}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
