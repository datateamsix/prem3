"""BigQuery result ledger tables inside prem3_modeling."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.contracts import utc_now
from app.modeling.common.errors import LedgerPublicationError
from app.modeling.mmm.results.contracts import (
    MMMDecisionIntelligenceBrief,
    MMMResultsSnapshot,
)

BQ_RESULT_LEDGER_TABLES = (
    "mmm_result_snapshots",
    "mmm_channel_results",
    "mmm_response_curve_points",
    "mmm_model_fit_evidence",
    "mmm_model_limitations",
    "mmm_decision_intelligence_findings",
)

RESULT_LEDGER_COLUMNS: dict[str, tuple[str, ...]] = {
    "mmm_result_snapshots": (
        "project_id",
        "cycle_id",
        "model_version_id",
        "fit_run_id",
        "result_snapshot_id",
        "result_status",
        "eligibility",
        "result_fingerprint",
        "model_artifact_sha256",
        "adapter_version",
        "meridian_version",
        "metric_extraction_policy_version",
        "synthetic",
        "generated_at",
    ),
    "mmm_channel_results": (
        "project_id",
        "cycle_id",
        "model_version_id",
        "fit_run_id",
        "result_snapshot_id",
        "channel_id",
        "channel_name",
        "spend",
        "incremental_outcome",
        "contribution",
        "roi",
        "marginal_roi",
        "availability",
        "generated_at",
    ),
    "mmm_response_curve_points": (
        "project_id",
        "cycle_id",
        "model_version_id",
        "fit_run_id",
        "result_snapshot_id",
        "channel_id",
        "spend_level",
        "expected_outcome",
        "outcome_lower",
        "outcome_upper",
        "generated_at",
    ),
    "mmm_model_fit_evidence": (
        "project_id",
        "cycle_id",
        "model_version_id",
        "fit_run_id",
        "result_snapshot_id",
        "official_review_source",
        "model_accepted",
        "blocking_fail_count",
        "review_item_count",
        "generated_at",
    ),
    "mmm_model_limitations": (
        "project_id",
        "cycle_id",
        "model_version_id",
        "fit_run_id",
        "result_snapshot_id",
        "limitation_id",
        "category",
        "severity",
        "title",
        "generated_at",
    ),
    "mmm_decision_intelligence_findings": (
        "project_id",
        "cycle_id",
        "model_version_id",
        "fit_run_id",
        "result_snapshot_id",
        "brief_id",
        "finding_id",
        "authority",
        "finding_type",
        "title",
        "generated_at",
    ),
}

# Documented view contracts (materialized by ops / later migration).
RESULT_LEDGER_VIEWS = (
    "mmm_results_latest_fit",
    "mmm_results_current_accepted",
)


class ResultLedger(Protocol):
    def write(self, *, table: str, row: dict[str, Any]) -> dict[str, Any]: ...

    def read_back(
        self, *, table: str, result_snapshot_id: str
    ) -> dict[str, Any] | list[dict[str, Any]] | None: ...

    def count(self, *, table: str, result_snapshot_id: str) -> int: ...


class InMemoryResultLedger:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {name: [] for name in BQ_RESULT_LEDGER_TABLES}

    def write(self, *, table: str, row: dict[str, Any]) -> dict[str, Any]:
        if table not in self.rows:
            raise LedgerPublicationError(f"Unknown result ledger table: {table}")
        stored = dict(row)
        self.rows[table].append(stored)
        return stored

    def read_back(
        self, *, table: str, result_snapshot_id: str
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        matches = [
            row for row in self.rows.get(table, []) if row.get("result_snapshot_id") == result_snapshot_id
        ]
        if not matches:
            return None
        if table == "mmm_result_snapshots":
            return matches[0]
        return matches

    def count(self, *, table: str, result_snapshot_id: str) -> int:
        return len(
            [
                row
                for row in self.rows.get(table, [])
                if row.get("result_snapshot_id") == result_snapshot_id
            ]
        )


def _metric_number(metric: Any) -> float | None:
    value = getattr(metric, "value", None)
    availability = getattr(metric, "availability", None)
    availability_value = getattr(availability, "value", availability)
    if availability_value in {"NOT_AVAILABLE", "INVALID"}:
        return None
    return value


def publish_result_ledger(
    ledger: ResultLedger,
    *,
    snapshot: MMMResultsSnapshot,
    brief: MMMDecisionIntelligenceBrief | None = None,
) -> dict[str, Any]:
    generated_at = snapshot.generated_at or utc_now()
    identity = {
        "project_id": snapshot.project_id,
        "cycle_id": snapshot.cycle_id,
        "model_version_id": snapshot.model_version_id,
        "fit_run_id": snapshot.fit_run_id,
        "result_snapshot_id": snapshot.result_snapshot_id,
        "generated_at": generated_at,
    }
    ledger.write(
        table="mmm_result_snapshots",
        row={
            **identity,
            "result_status": snapshot.result_status.value,
            "eligibility": snapshot.eligibility.value,
            "result_fingerprint": snapshot.result_fingerprint,
            "model_artifact_sha256": snapshot.model_artifact_sha256,
            "adapter_version": snapshot.adapter_version,
            "meridian_version": snapshot.meridian_version,
            "metric_extraction_policy_version": snapshot.metric_extraction_policy_version,
            "synthetic": snapshot.synthetic,
        },
    )
    for channel in snapshot.channels:
        ledger.write(
            table="mmm_channel_results",
            row={
                **identity,
                "channel_id": channel.channel_id,
                "channel_name": channel.channel_name,
                "spend": _metric_number(channel.spend),
                "incremental_outcome": _metric_number(channel.incremental_outcome),
                "contribution": _metric_number(channel.contribution),
                "roi": _metric_number(channel.roi),
                "marginal_roi": _metric_number(channel.marginal_roi),
                "availability": channel.availability.value,
            },
        )
    for curve in snapshot.response_curves:
        for point in curve.points:
            ledger.write(
                table="mmm_response_curve_points",
                row={
                    **identity,
                    "channel_id": curve.channel_id,
                    "spend_level": point.spend_level,
                    "expected_outcome": point.expected_outcome,
                    "outcome_lower": point.outcome_lower,
                    "outcome_upper": point.outcome_upper,
                },
            )
    ledger.write(
        table="mmm_model_fit_evidence",
        row={
            **identity,
            "official_review_source": snapshot.fit_evidence.official_review_source.value,
            "model_accepted": snapshot.fit_evidence.model_accepted,
            "blocking_fail_count": len(snapshot.fit_evidence.blocking_failures),
            "review_item_count": len(snapshot.fit_evidence.review_items),
        },
    )
    for limitation in snapshot.limitations:
        ledger.write(
            table="mmm_model_limitations",
            row={
                **identity,
                "limitation_id": limitation.limitation_id,
                "category": limitation.category.value,
                "severity": limitation.severity.value,
                "title": limitation.title,
            },
        )
    if brief is not None:
        for finding in (
            *brief.verified_findings,
            *brief.interpretations,
            *brief.uncertainties,
        ):
            ledger.write(
                table="mmm_decision_intelligence_findings",
                row={
                    **identity,
                    "brief_id": brief.brief_id,
                    "finding_id": finding.finding_id,
                    "authority": finding.authority.value,
                    "finding_type": finding.finding_type.value,
                    "title": finding.title,
                },
            )

    snap_row = ledger.read_back(
        table="mmm_result_snapshots", result_snapshot_id=snapshot.result_snapshot_id
    )
    if not isinstance(snap_row, dict):
        raise LedgerPublicationError("Result snapshot read-back failed.")
    if snap_row.get("result_fingerprint") != snapshot.result_fingerprint:
        raise LedgerPublicationError("Result snapshot fingerprint mismatch on read-back.")
    channel_count = ledger.count(
        table="mmm_channel_results", result_snapshot_id=snapshot.result_snapshot_id
    )
    if channel_count != len(snapshot.channels):
        raise LedgerPublicationError("Channel result read-back count mismatch.")
    return {
        "result_snapshot_id": snapshot.result_snapshot_id,
        "result_fingerprint": snapshot.result_fingerprint,
        "channel_count": channel_count,
        "verified": True,
    }
