"""Persist/hydrate a dispatch bundle so prem3-mta-worker can restore authority."""

from __future__ import annotations

from typing import Any

from app.control_plane.serialization import document_to_model, model_to_document
from app.modeling.mta.contracts import MTAInputContract
from app.modeling.mta.repository import InMemoryMTARepository
from app.modeling.mta.runtime_contracts import (
    MTAExecutionDispatch,
    MTAExecutionPlan,
    MTARun,
    MTARunReceipt,
)


def persist_runtime_bundle(
    client: Any,
    *,
    dispatch_id: str,
    plan: MTAExecutionPlan,
    run: MTARun,
    dispatch: MTAExecutionDispatch,
    contract: MTAInputContract,
    journeys: list[dict[str, Any]],
) -> None:
    client.collection("mta_runtime").document(dispatch_id).set(
        {
            "plan": model_to_document(plan),
            "run": model_to_document(run),
            "dispatch": model_to_document(dispatch),
            "contract": model_to_document(contract),
            "journeys": journeys,
        }
    )


def persist_runtime_receipt(
    client: Any,
    *,
    dispatch_id: str,
    receipt: MTARunReceipt,
    run: MTARun,
) -> None:
    client.collection("mta_runtime").document(dispatch_id).set(
        {
            "receipt": model_to_document(receipt),
            "run": model_to_document(run),
            "completed": True,
        },
        merge=True,
    )


def hydrate_runtime_bundle(
    client: Any,
    *,
    dispatch_id: str,
    repo: InMemoryMTARepository | None = None,
) -> InMemoryMTARepository:
    snap = client.collection("mta_runtime").document(dispatch_id).get()
    if not snap.exists:
        raise KeyError(f"Missing mta_runtime bundle {dispatch_id}")
    payload = snap.to_dict() or {}
    repo = repo or InMemoryMTARepository()
    plan = document_to_model(MTAExecutionPlan, payload["plan"])
    run = document_to_model(MTARun, payload["run"])
    dispatch = document_to_model(MTAExecutionDispatch, payload["dispatch"])
    contract = document_to_model(MTAInputContract, payload["contract"])
    repo.put_execution_plan(plan)
    repo.put_dispatch(dispatch)
    repo.put_run(run)
    repo.put_contract(contract)
    if payload.get("receipt"):
        receipt = document_to_model(MTARunReceipt, payload["receipt"])
        repo.put_run_receipt(receipt)
    return repo


def bundle_journeys(client: Any, *, dispatch_id: str) -> list[dict[str, Any]]:
    snap = client.collection("mta_runtime").document(dispatch_id).get()
    if not snap.exists:
        raise KeyError(dispatch_id)
    payload = snap.to_dict() or {}
    return list(payload.get("journeys") or [])
