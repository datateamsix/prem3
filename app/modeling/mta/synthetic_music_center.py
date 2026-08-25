"""SYNTHETIC_DEMO Music Center GA4-compatible events for live BQ proofs.

Loads into the authorized customer/project analytics-like dataset and is consumed
by the production GA4 source compiler / MERGE path — not a parallel runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from google.cloud import bigquery

from app.modeling.mta.bq_executor import client_for_project, ensure_dataset

EVIDENCE_LABEL = "SYNTHETIC_DEMO"
GA4_SYNTHETIC_DATASET = "analytics_music_center_synthetic"
DEFAULT_WINDOW_START = date(2024, 6, 1)
DEFAULT_WINDOW_END = date(2024, 6, 7)


@dataclass(frozen=True)
class SyntheticEventSpec:
    event_date: date
    event_name: str
    user_pseudo_id: str
    ga_session_id: int
    source: str | None
    medium: str | None
    campaign: str | None
    transaction_id: str | None = None
    purchase_revenue: float | None = None
    user_id: str | None = None
    hour: int = 12


def music_center_base_events() -> list[SyntheticEventSpec]:
    """Bounded Music Center journeys incl. ai_search + correction/removal subjects."""
    d0 = DEFAULT_WINDOW_START
    d1 = d0 + timedelta(days=1)
    d2 = d0 + timedelta(days=2)
    d3 = d0 + timedelta(days=3)
    return [
        # Journey A: social → ai_search → paid search → purchase
        SyntheticEventSpec(
            d0, "session_start", "mc_user_a", 1001, "facebook", "cpc", "brand_spring"
        ),
        SyntheticEventSpec(
            d0, "page_view", "mc_user_a", 1001, "facebook", "cpc", "brand_spring", hour=13
        ),
        SyntheticEventSpec(
            d1, "session_start", "mc_user_a", 1002, "chatgpt.com", "referral", "ai_answer"
        ),
        SyntheticEventSpec(
            d1, "page_view", "mc_user_a", 1002, "chatgpt.com", "referral", "ai_answer", hour=14
        ),
        SyntheticEventSpec(
            d2, "session_start", "mc_user_a", 1003, "google", "cpc", "brand_exact"
        ),
        SyntheticEventSpec(
            d2,
            "purchase",
            "mc_user_a",
            1003,
            "google",
            "cpc",
            "brand_exact",
            transaction_id="txn_a1",
            purchase_revenue=199.0,
            hour=15,
        ),
        # Journey B: direct → purchase (stable)
        SyntheticEventSpec(d1, "session_start", "mc_user_b", 2001, None, None, None),
        SyntheticEventSpec(
            d1,
            "purchase",
            "mc_user_b",
            2001,
            None,
            None,
            None,
            transaction_id="txn_b1",
            purchase_revenue=89.0,
            hour=16,
        ),
        # Journey C: correction subject (google/organic → later bing/cpc)
        SyntheticEventSpec(
            d0, "session_start", "mc_user_c", 3001, "google", "organic", "(organic)"
        ),
        SyntheticEventSpec(
            d3, "session_start", "mc_user_c", 3002, "google", "cpc", "retarget"
        ),
        SyntheticEventSpec(
            d3,
            "purchase",
            "mc_user_c",
            3002,
            "google",
            "cpc",
            "retarget",
            transaction_id="txn_c1",
            purchase_revenue=120.0,
            hour=11,
        ),
        # Journey D: removable row subject
        SyntheticEventSpec(
            d2, "session_start", "mc_user_d", 4001, "email", "email", "newsletter"
        ),
        SyntheticEventSpec(
            d2,
            "purchase",
            "mc_user_d",
            4001,
            "email",
            "email",
            "newsletter",
            transaction_id="txn_d1",
            purchase_revenue=45.0,
            hour=10,
        ),
    ]


def events_with_correction(
    base: list[SyntheticEventSpec] | None = None,
) -> list[SyntheticEventSpec]:
    """Late arrival: session 3001 source changes google/organic → bing/cpc."""
    rows = list(base or music_center_base_events())
    out: list[SyntheticEventSpec] = []
    for row in rows:
        if row.user_pseudo_id == "mc_user_c" and row.ga_session_id == 3001:
            out.append(
                SyntheticEventSpec(
                    event_date=row.event_date,
                    event_name=row.event_name,
                    user_pseudo_id=row.user_pseudo_id,
                    ga_session_id=row.ga_session_id,
                    source="bing",
                    medium="cpc",
                    campaign="corrected_brand",
                    hour=row.hour,
                )
            )
        else:
            out.append(row)
    return out


def events_with_removal(base: list[SyntheticEventSpec] | None = None) -> list[SyntheticEventSpec]:
    """Remove mc_user_d events from the source window."""
    rows = list(base or music_center_base_events())
    return [r for r in rows if r.user_pseudo_id != "mc_user_d"]


def _ga4_schema() -> list[bigquery.SchemaField]:
    value = bigquery.SchemaField(
        "value",
        "RECORD",
        fields=[
            bigquery.SchemaField("string_value", "STRING"),
            bigquery.SchemaField("int_value", "INTEGER"),
            bigquery.SchemaField("float_value", "FLOAT"),
            bigquery.SchemaField("double_value", "FLOAT"),
        ],
    )
    event_param = bigquery.SchemaField(
        "event_params",
        "RECORD",
        mode="REPEATED",
        fields=[
            bigquery.SchemaField("key", "STRING"),
            value,
        ],
    )
    manual = bigquery.SchemaField(
        "manual_campaign",
        "RECORD",
        fields=[
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("medium", "STRING"),
            bigquery.SchemaField("campaign_name", "STRING"),
        ],
    )
    cross = bigquery.SchemaField(
        "cross_channel_campaign",
        "RECORD",
        fields=[
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("medium", "STRING"),
            bigquery.SchemaField("campaign_name", "STRING"),
        ],
    )
    last_click = bigquery.SchemaField(
        "session_traffic_source_last_click",
        "RECORD",
        fields=[manual, cross],
    )
    collected = bigquery.SchemaField(
        "collected_traffic_source",
        "RECORD",
        fields=[
            bigquery.SchemaField("manual_source", "STRING"),
            bigquery.SchemaField("manual_medium", "STRING"),
            bigquery.SchemaField("manual_campaign_name", "STRING"),
        ],
    )
    ecommerce = bigquery.SchemaField(
        "ecommerce",
        "RECORD",
        fields=[
            bigquery.SchemaField("transaction_id", "STRING"),
            bigquery.SchemaField("purchase_revenue", "FLOAT"),
        ],
    )
    return [
        bigquery.SchemaField("event_date", "STRING"),
        bigquery.SchemaField("event_timestamp", "INTEGER"),
        bigquery.SchemaField("event_name", "STRING"),
        bigquery.SchemaField("user_pseudo_id", "STRING"),
        bigquery.SchemaField("user_id", "STRING"),
        event_param,
        last_click,
        collected,
        ecommerce,
        bigquery.SchemaField("evidence_label", "STRING"),
    ]


def _row_dict(spec: SyntheticEventSpec) -> dict[str, Any]:
    ts = datetime(
        spec.event_date.year,
        spec.event_date.month,
        spec.event_date.day,
        spec.hour,
        0,
        0,
        tzinfo=UTC,
    )
    micros = int(ts.timestamp() * 1_000_000)
    source = spec.source
    medium = spec.medium
    campaign = spec.campaign
    return {
        "event_date": spec.event_date.strftime("%Y%m%d"),
        "event_timestamp": micros,
        "event_name": spec.event_name,
        "user_pseudo_id": spec.user_pseudo_id,
        "user_id": spec.user_id,
        "event_params": [
            {"key": "ga_session_id", "value": {"int_value": spec.ga_session_id}},
        ],
        "session_traffic_source_last_click": {
            "manual_campaign": {
                "source": source,
                "medium": medium,
                "campaign_name": campaign,
            },
            "cross_channel_campaign": {
                "source": source,
                "medium": medium,
                "campaign_name": campaign,
            },
        },
        "collected_traffic_source": {
            "manual_source": source,
            "manual_medium": medium,
            "manual_campaign_name": campaign,
        },
        "ecommerce": {
            "transaction_id": spec.transaction_id,
            "purchase_revenue": spec.purchase_revenue,
        },
        "evidence_label": EVIDENCE_LABEL,
    }


def load_synthetic_ga4_events(
    *,
    project_id: str,
    events: list[SyntheticEventSpec] | None = None,
    dataset_id: str = GA4_SYNTHETIC_DATASET,
    replace: bool = True,
) -> dict[str, Any]:
    """Write GA4-compatible events_* tables. All rows labeled SYNTHETIC_DEMO."""
    client = client_for_project(project_id)
    ensure_dataset(client, project_id=project_id, dataset_id=dataset_id)
    # Tag dataset description
    ds = client.get_dataset(f"{project_id}.{dataset_id}")
    ds.description = f"PreM3 {EVIDENCE_LABEL} Music Center GA4-compatible source"
    client.update_dataset(ds, ["description"])

    by_day: dict[str, list[dict[str, Any]]] = {}
    for spec in events or music_center_base_events():
        by_day.setdefault(spec.event_date.strftime("%Y%m%d"), []).append(_row_dict(spec))

    created: list[str] = []
    schema = _ga4_schema()
    if replace:
        # Drop prior synthetic day tables in window
        for day in sorted(by_day):
            table_id = f"events_{day}"
            client.delete_table(f"{project_id}.{dataset_id}.{table_id}", not_found_ok=True)

    for day, rows in sorted(by_day.items()):
        table_id = f"events_{day}"
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        # Batch load avoids streaming-insert races on freshly created tables.
        load_job = client.load_table_from_json(rows, table_ref, job_config=job_config)
        load_job.result()
        table = client.get_table(table_ref)
        table.description = f"{EVIDENCE_LABEL} Music Center GA4 events {day}"
        table.labels = {"prem3_evidence": "synthetic_demo", "prem3_demo": "music_center"}
        client.update_table(table, ["description", "labels"])
        created.append(table_ref)

    return {
        "evidence_label": EVIDENCE_LABEL,
        "project_id": project_id,
        "dataset_id": dataset_id,
        "tables": created,
        "event_count": sum(len(v) for v in by_day.values()),
        "window_start": DEFAULT_WINDOW_START.isoformat(),
        "window_end": DEFAULT_WINDOW_END.isoformat(),
    }
