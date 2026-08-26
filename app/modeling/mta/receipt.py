"""Build fingerprinted MTARunReceipt."""

from __future__ import annotations

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.runtime_contracts import (
    MTAComputationAuthority,
    MTAModelExecutionEvidence,
    MTARun,
    MTARunReceipt,
    MTARunStatus,
)


def build_run_receipt(
    run: MTARun,
    *,
    input_contract_fingerprint: str,
    session_count: int,
    touchpoint_count: int,
    journey_count: int,
    grouped_path_count: int,
    output_refs: tuple[str, ...] | list[str],
    readback_status: str,
    limitations: tuple[str, ...] | list[str] = (),
    computation_authority: MTAComputationAuthority = MTAComputationAuthority.TEST_FAKE_RUNTIME,
) -> MTARunReceipt:
    payload = {
        "run_id": run.run_id,
        "execution_plan_id": run.execution_plan_id,
        "status": run.status.value,
        "input_contract_fingerprint": input_contract_fingerprint,
        "session_count": session_count,
        "touchpoint_count": touchpoint_count,
        "journey_count": journey_count,
        "grouped_path_count": grouped_path_count,
        "model_statuses": [m.model_dump(mode="json") for m in run.model_evidence],
        "output_refs": list(output_refs),
        "readback_status": readback_status,
        "limitations": list(limitations),
        "source_commit_sha": run.source_commit_sha,
        "worker_image_digest": run.worker_image_digest,
        "computation_authority": computation_authority.value,
    }
    return MTARunReceipt(
        receipt_id=f"mrcpt_{canonical_fingerprint(payload)[:20]}",
        run_id=run.run_id,
        execution_plan_id=run.execution_plan_id,
        status=run.status,
        input_contract_fingerprint=input_contract_fingerprint,
        session_count=session_count,
        touchpoint_count=touchpoint_count,
        journey_count=journey_count,
        grouped_path_count=grouped_path_count,
        model_statuses=run.model_evidence,
        output_refs=tuple(output_refs),
        readback_status=readback_status,
        limitations=tuple(limitations),
        started_at=run.started_at,
        completed_at=run.completed_at,
        source_commit_sha=run.source_commit_sha,
        worker_image_digest=run.worker_image_digest,
        computation_authority=computation_authority,
        fingerprint=canonical_fingerprint(payload),
    )


def mark_succeeded_after_readback(
    run: MTARun, *, evidence: tuple[MTAModelExecutionEvidence, ...]
) -> MTARun:
    return run.model_copy(
        update={
            "status": MTARunStatus.SUCCEEDED,
            "model_evidence": evidence,
        }
    )
