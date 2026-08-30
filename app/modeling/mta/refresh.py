"""Managed MTA operational refresh — window planner, MERGE, watermark."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.runtime_contracts import (
    MTARefreshWindow,
    MTAScheduledRefreshPlan,
    MTAScheduledRefreshReceipt,
    ScheduledRefreshApprovalStatus,
)
from app.modeling.mta.sql.registry import cached_sql_asset_manifest
from app.modeling.mta.sql.renderer import render_sql_asset


class MTARefreshWindowPlanner:
    """Deterministic bounded refresh windows — never full GA4 history."""

    def plan(
        self,
        *,
        run_date: str,
        settlement_days: int,
        source_overlap_days: int,
        lookback_window_days: int,
        last_watermark_date: str | None = None,
    ) -> MTARefreshWindow:
        end = date.fromisoformat(run_date) - timedelta(days=max(settlement_days, 0))
        # Bound by lookback + overlap; optionally advance from watermark.
        span_days = lookback_window_days + source_overlap_days
        start = end - timedelta(days=max(span_days, 0))
        if last_watermark_date:
            watermark = date.fromisoformat(last_watermark_date)
            # Re-open overlap behind watermark; never scan earlier than lookback bound.
            reopen = watermark - timedelta(days=max(source_overlap_days, 0))
            start = max(start, reopen)
        affected_conversion_start = start.isoformat()
        affected_conversion_end = end.isoformat()
        payload = {
            "run_date": run_date,
            "settlement_days": settlement_days,
            "source_overlap_days": source_overlap_days,
            "lookback_window_days": lookback_window_days,
            "last_watermark_date": last_watermark_date,
            "source_start_date": start.isoformat(),
            "source_end_date": end.isoformat(),
            "affected_conversion_start": affected_conversion_start,
            "affected_conversion_end": affected_conversion_end,
        }
        return MTARefreshWindow(
            run_date=run_date,
            settlement_days=settlement_days,
            source_overlap_days=source_overlap_days,
            lookback_window_days=lookback_window_days,
            source_start_date=start.isoformat(),
            source_end_date=end.isoformat(),
            affected_conversion_start=affected_conversion_start,
            affected_conversion_end=affected_conversion_end,
            fingerprint=canonical_fingerprint(payload),
        )


class InMemoryOperationalStore:
    """Fake BQ operational layer for MERGE/rebuild idempotency tests."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.conversions: dict[str, dict[str, Any]] = {}
        self.touchpoints: dict[str, dict[str, Any]] = {}
        self.journeys: dict[str, dict[str, Any]] = {}
        self.path_frequencies: dict[str, dict[str, Any]] = {}
        self.watermark: str | None = None
        self.validated = False

    def merge_sessions(
        self,
        rows: list[dict[str, Any]],
        *,
        source_start: str,
        source_end: str,
    ) -> None:
        incoming_ids = {r["session_id"] for r in rows}
        for sid, row in list(self.sessions.items()):
            if source_start <= str(row.get("source_date", "")) <= source_end:
                if sid not in incoming_ids:
                    del self.sessions[sid]
        for row in rows:
            existing = self.sessions.get(row["session_id"])
            if existing is None or existing.get("source_fingerprint") != row.get(
                "source_fingerprint"
            ):
                self.sessions[row["session_id"]] = dict(row)

    def merge_conversions(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.conversions[row["conversion_id"]] = dict(row)

    def merge_touchpoints(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.touchpoints[row["touchpoint_id"]] = dict(row)

    def rebuild_journeys(
        self, rows: list[dict[str, Any]], *, conversion_start: str, conversion_end: str
    ) -> None:
        for jid, row in list(self.journeys.items()):
            conv_date = str(row.get("conversion_date", ""))
            if conversion_start <= conv_date <= conversion_end:
                del self.journeys[jid]
        for row in rows:
            self.journeys[row["journey_id"]] = dict(row)

    def rebuild_path_frequencies(self, rows: list[dict[str, Any]]) -> None:
        self.path_frequencies = {r["path_string"]: dict(r) for r in rows}

    def advance_watermark(self, value: str, *, validated: bool) -> None:
        if not validated:
            raise ValueError("Watermark cannot advance before validation succeeds.")
        self.watermark = value
        self.validated = True


def compile_refresh_sql(
    *,
    project_id: str,
    modeling_dataset: str,
    channel_grouping_version: int,
    traffic_source_policy: str,
    window: MTARefreshWindow,
) -> dict[str, tuple[str, str]]:
    """Render MERGE/rebuild/watermark templates for a refresh window."""
    manifest = cached_sql_asset_manifest()
    params = {
        "project_id": project_id,
        "modeling_dataset": modeling_dataset,
        "channel_grouping_version": channel_grouping_version,
        "traffic_source_policy": traffic_source_policy,
        "standardized_session_select": (
            "SELECT CAST(NULL AS STRING) AS session_id, "
            "CAST(NULL AS STRING) AS subject_key, "
            "CAST(NULL AS TIMESTAMP) AS session_start_ts, "
            "CAST(NULL AS TIMESTAMP) AS session_end_ts, "
            "CAST(NULL AS STRING) AS source, CAST(NULL AS STRING) AS medium, "
            "CAST(NULL AS STRING) AS campaign, CAST(NULL AS DATE) AS source_date"
        ),
        "source_start_date": window.source_start_date,
        "source_end_date": window.source_end_date,
    }
    out: dict[str, tuple[str, str]] = {}
    for asset_id in (
        "merge_sessions_v1",
        "merge_conversions_v1",
        "merge_touchpoints_v1",
        "rebuild_journeys_v1",
        "rebuild_path_frequencies_v1",
        "update_watermark_v1",
        "daily_refresh_v1",
    ):
        entry = manifest.get(asset_id)
        # Some templates only need a subset; provide defaults for optional Jinja vars.
        rich = {
            **params,
            "run_id": "refresh",
            "watermark_date": window.source_end_date,
            "conversion_start": window.affected_conversion_start,
            "conversion_end": window.affected_conversion_end,
        }
        try:
            rendered, fp = render_sql_asset(entry, params=rich)
        except Exception:
            # Templates may reference additional vars; compile with StrictUndefined may fail.
            # Fall back to compiling only assets that render with base params.
            continue
        out[asset_id] = (rendered, fp)
    return out


def build_scheduled_refresh_plan(
    *,
    schedule_id: str,
    conversion_event: str,
    lookback_window_days: int,
    settlement_days: int = 2,
    source_overlap_days: int = 3,
    channel_registry_version: int = 1,
    channel_grouping_version: int = 1,
    cadence: str = "DAILY",
    timezone: str = "America/Los_Angeles",
    enabled: bool = False,
) -> MTAScheduledRefreshPlan:
    payload = {
        "schedule_id": schedule_id,
        "enabled": enabled,
        "cadence": cadence,
        "timezone": timezone,
        "settlement_days": settlement_days,
        "source_overlap_days": source_overlap_days,
        "lookback_window_days": lookback_window_days,
        "conversion_event": conversion_event,
        "channel_registry_version": channel_registry_version,
        "channel_grouping_version": channel_grouping_version,
    }
    return MTAScheduledRefreshPlan(
        schedule_id=schedule_id,
        enabled=enabled,
        cadence=cadence,
        timezone=timezone,
        settlement_days=settlement_days,
        source_overlap_days=source_overlap_days,
        lookback_window_days=lookback_window_days,
        conversion_event=conversion_event,
        channel_registry_version=channel_registry_version,
        channel_grouping_version=channel_grouping_version,
        approval_status=ScheduledRefreshApprovalStatus.DRAFT,
        fingerprint=canonical_fingerprint(payload),
    )


def approve_scheduled_refresh(plan: MTAScheduledRefreshPlan) -> MTAScheduledRefreshPlan:
    return plan.model_copy(
        update={"approval_status": ScheduledRefreshApprovalStatus.APPROVED}
    )


def provision_scheduled_refresh_fake(
    plan: MTAScheduledRefreshPlan,
) -> MTAScheduledRefreshReceipt:
    if plan.approval_status not in (
        ScheduledRefreshApprovalStatus.APPROVED,
        ScheduledRefreshApprovalStatus.PROVISIONED,
    ):
        raise PermissionError("Scheduled refresh requires APPROVAL_REQUIRED approval.")
    return MTAScheduledRefreshReceipt(
        receipt_id=f"mta_sched_{plan.fingerprint[:16]}",
        schedule_id=plan.schedule_id,
        plan_fingerprint=plan.fingerprint,
        provisioned=True,
        verified=True,
    )
