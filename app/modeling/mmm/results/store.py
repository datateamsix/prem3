"""Idempotent result extraction, persistence, and pointer management."""

from __future__ import annotations

import json
import logging
from threading import Lock
from typing import Any

from app.modeling.common.errors import ModelingError
from app.modeling.mmm.artifacts import persist_immutable_bytes
from app.modeling.mmm.contracts import FitRunStatus, ReviewSource
from app.modeling.mmm.results.adapter_meridian_180 import Meridian180ResultsAdapter
from app.modeling.mmm.results.builder import (
    build_snapshot_from_raw,
    default_fit_evidence,
    resolve_result_status,
)
from app.modeling.mmm.results.contracts import (
    EvidenceEligibility,
    MMMDecisionIntelligenceBrief,
    MMMResultStatus,
    MMMResultsSnapshot,
    MMMResultsUnavailable,
    RawMeridianResultsEvidence,
    ResultProvenance,
    ResultSnapshotMetadata,
    ResultSnapshotPointer,
    UnavailableReason,
)
from app.modeling.mmm.results.fingerprint import result_source_fingerprint
from app.modeling.mmm.results.intelligence import compile_decision_intelligence_brief
from app.modeling.mmm.results.ledger import InMemoryResultLedger, ResultLedger, publish_result_ledger

logger = logging.getLogger(__name__)

RESULTS_SNAPSHOT_NAME = "mmm_results_snapshot.json"
CHANNEL_RESULTS_NAME = "mmm_channel_results.json"
DECISION_BRIEF_NAME = "mmm_decision_intelligence_brief.json"

FIT_COMPLETE_STATUSES = frozenset({FitRunStatus.SUCCEEDED})


class ResultExtractionError(ModelingError):
    code = "RESULT_EXTRACTION_FAILED"


class ResultStore:
    """In-memory + optional Firestore/GCS/BQ-backed result store."""

    def __init__(
        self,
        *,
        ledger: ResultLedger | None = None,
        object_store: Any | None = None,
        artifact_bucket: str | None = None,
    ) -> None:
        self.ledger = ledger or InMemoryResultLedger()
        self.object_store = object_store
        self.artifact_bucket = artifact_bucket
        self._lock = Lock()
        self.snapshots: dict[str, MMMResultsSnapshot] = {}
        self.briefs: dict[str, MMMDecisionIntelligenceBrief] = {}
        self.metadata: dict[str, ResultSnapshotMetadata] = {}
        self.pointers: dict[tuple[str, str, str], ResultSnapshotPointer] = {}
        self.by_source: dict[str, str] = {}
        self.claims: set[str] = set()

    def get_snapshot(self, result_snapshot_id: str) -> MMMResultsSnapshot | None:
        return self.snapshots.get(result_snapshot_id)

    def get_brief_for_snapshot(self, result_snapshot_id: str) -> MMMDecisionIntelligenceBrief | None:
        for brief in self.briefs.values():
            if brief.result_snapshot_id == result_snapshot_id:
                return brief
        return None

    def get_pointer(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> ResultSnapshotPointer | None:
        return self.pointers.get((tenant_id, project_id, cycle_id))

    def claim_or_get(
        self, *, source_fingerprint: str
    ) -> tuple[str, MMMResultsSnapshot | None]:
        with self._lock:
            existing_id = self.by_source.get(source_fingerprint)
            if existing_id is not None:
                return existing_id, self.snapshots.get(existing_id)
            if source_fingerprint in self.claims:
                return source_fingerprint, None
            self.claims.add(source_fingerprint)
            return source_fingerprint, None

    def persist_snapshot(
        self,
        snapshot: MMMResultsSnapshot,
        *,
        brief: MMMDecisionIntelligenceBrief | None = None,
        update_accepted_pointer: bool = False,
    ) -> MMMResultsSnapshot:
        source_fp = result_source_fingerprint(
            model_artifact_sha256=snapshot.model_artifact_sha256,
            model_version_id=snapshot.model_version_id,
            fit_run_id=snapshot.fit_run_id,
            adapter_version=snapshot.adapter_version,
            meridian_version=snapshot.meridian_version,
            metric_extraction_policy_version=snapshot.metric_extraction_policy_version,
        )
        with self._lock:
            existing_id = self.by_source.get(source_fp)
            if existing_id is not None:
                existing = self.snapshots[existing_id]
                return existing

            gcs_snapshot_ref = None
            gcs_channel_ref = None
            gcs_brief_ref = None
            if self.object_store is not None and self.artifact_bucket:
                prefix = (
                    f"{snapshot.tenant_id}/{snapshot.project_id}/modeling/"
                    f"{snapshot.model_version_id}/results/{snapshot.result_snapshot_id}"
                )
                snap_bytes = snapshot.model_dump_json().encode("utf-8")
                persist_immutable_bytes(
                    self.object_store,
                    bucket=self.artifact_bucket,
                    object_name=f"{prefix}/{RESULTS_SNAPSHOT_NAME}",
                    data=snap_bytes,
                    content_type="application/json",
                )
                gcs_snapshot_ref = f"gs://{self.artifact_bucket}/{prefix}/{RESULTS_SNAPSHOT_NAME}"
                channel_payload = json.dumps(
                    [c.model_dump(mode="json") for c in snapshot.channels],
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
                persist_immutable_bytes(
                    self.object_store,
                    bucket=self.artifact_bucket,
                    object_name=f"{prefix}/{CHANNEL_RESULTS_NAME}",
                    data=channel_payload,
                    content_type="application/json",
                )
                gcs_channel_ref = f"gs://{self.artifact_bucket}/{prefix}/{CHANNEL_RESULTS_NAME}"
                if brief is not None:
                    brief_bytes = brief.model_dump_json().encode("utf-8")
                    persist_immutable_bytes(
                        self.object_store,
                        bucket=self.artifact_bucket,
                        object_name=f"{prefix}/{DECISION_BRIEF_NAME}",
                        data=brief_bytes,
                        content_type="application/json",
                    )
                    gcs_brief_ref = f"gs://{self.artifact_bucket}/{prefix}/{DECISION_BRIEF_NAME}"

            publish_result_ledger(self.ledger, snapshot=snapshot, brief=brief)
            snapshot = snapshot.model_copy(
                update={
                    "gcs_snapshot_ref": gcs_snapshot_ref,
                    "gcs_channel_results_ref": gcs_channel_ref,
                    "gcs_brief_ref": gcs_brief_ref,
                    "ledger_readback_verified": True,
                }
            )
            if brief is not None and gcs_brief_ref is not None:
                brief = brief.model_copy(update={"gcs_brief_ref": gcs_brief_ref})

            meta = ResultSnapshotMetadata(
                result_snapshot_id=snapshot.result_snapshot_id,
                tenant_id=snapshot.tenant_id,
                project_id=snapshot.project_id,
                cycle_id=snapshot.cycle_id,
                model_version_id=snapshot.model_version_id,
                fit_run_id=snapshot.fit_run_id,
                result_status=snapshot.result_status,
                eligibility=snapshot.eligibility,
                result_fingerprint=snapshot.result_fingerprint,
                model_artifact_sha256=snapshot.model_artifact_sha256,
                adapter_version=snapshot.adapter_version,
                meridian_version=snapshot.meridian_version,
                metric_extraction_policy_version=snapshot.metric_extraction_policy_version,
                gcs_snapshot_ref=gcs_snapshot_ref,
                gcs_channel_results_ref=gcs_channel_ref,
                gcs_brief_ref=gcs_brief_ref,
                ledger_readback_verified=True,
                synthetic=snapshot.synthetic,
                channel_count=len(snapshot.channels),
                generated_at=snapshot.generated_at,
            )
            # Compact metadata invariant: no nested channel arrays on metadata.
            dumped = meta.model_dump(mode="json")
            if any(isinstance(v, list) for v in dumped.values()):
                raise ResultExtractionError("Firestore metadata must not store large nested arrays.")

            self.snapshots[snapshot.result_snapshot_id] = snapshot
            self.metadata[snapshot.result_snapshot_id] = meta
            self.by_source[source_fp] = snapshot.result_snapshot_id
            if brief is not None:
                self.briefs[brief.brief_id] = brief

            key = (snapshot.tenant_id, snapshot.project_id, snapshot.cycle_id)
            pointer = self.pointers.get(key) or ResultSnapshotPointer(
                project_id=snapshot.project_id,
                cycle_id=snapshot.cycle_id,
                tenant_id=snapshot.tenant_id,
            )
            pointer = pointer.model_copy(
                update={"latest_result_snapshot_id": snapshot.result_snapshot_id}
            )
            if update_accepted_pointer and snapshot.result_status is MMMResultStatus.ACCEPTED:
                pointer = pointer.model_copy(
                    update={"accepted_result_snapshot_id": snapshot.result_snapshot_id}
                )
            self.pointers[key] = pointer

            logger.info(
                "mmm_result_snapshot_persisted",
                extra={
                    "result_snapshot_id": snapshot.result_snapshot_id,
                    "project_id": snapshot.project_id,
                    "cycle_id": snapshot.cycle_id,
                    "model_version_id": snapshot.model_version_id,
                    "fit_run_id": snapshot.fit_run_id,
                    "result_status": snapshot.result_status.value,
                    "adapter_version": snapshot.adapter_version,
                    "meridian_version": snapshot.meridian_version,
                    "metrics_available": [
                        c.channel_id
                        for c in snapshot.channels
                        if c.availability.value in {"VALUE", "ZERO"}
                    ],
                    "metrics_unavailable": [
                        c.channel_id
                        for c in snapshot.channels
                        if c.availability.value in {"NOT_AVAILABLE", "INVALID"}
                    ],
                },
            )
            return snapshot

    def mark_accepted(self, *, tenant_id: str, project_id: str, cycle_id: str, result_snapshot_id: str) -> None:
        with self._lock:
            snapshot = self.snapshots.get(result_snapshot_id)
            if snapshot is None:
                raise ResultExtractionError("Unknown result snapshot for acceptance pointer.")
            if snapshot.tenant_id != tenant_id or snapshot.project_id != project_id:
                raise ResultExtractionError("Cross-tenant result pointer update denied.")
            key = (tenant_id, project_id, cycle_id)
            pointer = self.pointers.get(key) or ResultSnapshotPointer(
                project_id=project_id, cycle_id=cycle_id, tenant_id=tenant_id
            )
            # Never let unaccepted replace accepted; only ACCEPTED snapshots move pointer.
            if snapshot.result_status is not MMMResultStatus.ACCEPTED:
                return
            self.pointers[key] = pointer.model_copy(
                update={"accepted_result_snapshot_id": result_snapshot_id}
            )


def extract_and_persist(
    store: ResultStore,
    *,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    model_version_id: str,
    fit_run_id: str,
    model_artifact_sha256: str,
    raw: RawMeridianResultsEvidence,
    provenance: ResultProvenance,
    fit_complete: bool,
    model_accepted: bool,
    review_pending: bool,
    model_plan_fingerprint: str | None = None,
    fit_plan_fingerprint: str | None = None,
    review_pack_fingerprint: str | None = None,
    model_window_start: str | None = None,
    model_window_end: str | None = None,
    outcome_name: str | None = None,
    outcome_unit: str | None = None,
    review_source: ReviewSource = ReviewSource.OFFICIAL_MERIDIAN,
    review_items: tuple[str, ...] = (),
    acknowledgments: tuple[str, ...] = (),
    business_iq_notes: tuple[str, ...] = (),
    source_runtime: str = "OFFICIAL_MERIDIAN",
    synthetic_label: str | None = None,
) -> MMMResultsSnapshot:
    if not fit_complete:
        raise ResultExtractionError("Cannot extract results before fit completion.")
    adapter = Meridian180ResultsAdapter()
    adapter.extract_from_raw_evidence(raw)
    source_fp = result_source_fingerprint(
        model_artifact_sha256=model_artifact_sha256,
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        adapter_version=raw.adapter_version,
        meridian_version=raw.meridian_version,
    )
    _, existing = store.claim_or_get(source_fingerprint=source_fp)
    if existing is not None:
        return existing

    status = resolve_result_status(
        fit_complete=True,
        model_accepted=model_accepted,
        review_pending=review_pending,
    )
    snapshot = build_snapshot_from_raw(
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        model_artifact_sha256=model_artifact_sha256,
        raw=raw,
        fit_evidence=default_fit_evidence(
            review_source=review_source,
            model_accepted=model_accepted,
            review_items=review_items,
            acknowledgments=acknowledgments,
        ),
        provenance=provenance,
        result_status=status,
        model_plan_fingerprint=model_plan_fingerprint,
        fit_plan_fingerprint=fit_plan_fingerprint,
        review_pack_fingerprint=review_pack_fingerprint,
        model_window_start=model_window_start,
        model_window_end=model_window_end,
        outcome_name=outcome_name,
        outcome_unit=outcome_unit,
        source_runtime=source_runtime,
        synthetic_label=synthetic_label,
    )
    brief = compile_decision_intelligence_brief(
        snapshot=snapshot, business_iq_notes=business_iq_notes
    )
    return store.persist_snapshot(
        snapshot,
        brief=brief,
        update_accepted_pointer=model_accepted,
    )


def unavailable_for_cycle(
    *,
    project_id: str,
    cycle_id: str,
    reason: UnavailableReason = UnavailableReason.FIT_NOT_COMPLETE,
    model_version_id: str | None = None,
    fit_run_id: str | None = None,
    detail: str | None = None,
) -> MMMResultsUnavailable:
    return MMMResultsUnavailable(
        status=MMMResultStatus.NOT_AVAILABLE,
        reason=reason,
        project_id=project_id,
        cycle_id=cycle_id,
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        detail=detail,
    )


def select_snapshot_for_read(
    store: ResultStore,
    *,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    prefer_accepted: bool = False,
) -> MMMResultsSnapshot | None:
    pointer = store.get_pointer(tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id)
    if pointer is None:
        return None
    if prefer_accepted and pointer.accepted_result_snapshot_id:
        snap = store.get_snapshot(pointer.accepted_result_snapshot_id)
        if snap is not None and snap.tenant_id == tenant_id and snap.project_id == project_id:
            return snap
    if pointer.latest_result_snapshot_id:
        snap = store.get_snapshot(pointer.latest_result_snapshot_id)
        if snap is not None and snap.tenant_id == tenant_id and snap.project_id == project_id:
            return snap
    return None
