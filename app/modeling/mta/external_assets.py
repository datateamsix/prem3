"""Pinned external assets for MTA (reference + future runtime)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.modeling.mta import DP6_MAM_PINNED_VERSION


class MTAExternalAsset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str
    provider: str
    repository: str | None = None
    version: str | None = None
    commit_sha: str | None = None
    license: str | None = None
    asset_type: str
    authority: str
    url: str | None = None
    enabled: bool = True
    notes: str | None = None


MTA_EXTERNAL_ASSETS: tuple[MTAExternalAsset, ...] = (
    MTAExternalAsset(
        asset_id="ga4-bigquery-export-schema",
        provider="google",
        asset_type="NORMATIVE_DOC",
        authority="NORMATIVE",
        url="https://support.google.com/analytics/answer/7029846",
        notes="Official GA4 BigQuery Export schema.",
    ),
    MTAExternalAsset(
        asset_id="ga4-bigquery-query-examples",
        provider="google",
        asset_type="NORMATIVE_DOC",
        authority="NORMATIVE",
        url="https://developers.google.com/analytics/bigquery/advanced-queries",
        notes="Official GA4 BigQuery query examples.",
    ),
    MTAExternalAsset(
        asset_id="dp6-marketing-attribution-models",
        provider="dp6",
        repository="DP6/Marketing-Attribution-Models",
        version=DP6_MAM_PINNED_VERSION,
        license="Apache-2.0",
        asset_type="RUNTIME_LIBRARY",
        authority="RUNTIME",
        url="https://github.com/DP6/Marketing-Attribution-Models",
        enabled=False,
        notes="Pinned for M5-01 adapter; not executed in M5-00.",
    ),
    MTAExternalAsset(
        asset_id="stacktonic-ga4-attribution-sql",
        provider="stacktonic",
        asset_type="REFERENCE_TUTORIAL",
        authority="REFERENCE_ONLY",
        url="https://stacktonic.com/article/build-a-data-driven-attribution-model-using-google-analytics-4-big-query-and-python",
        notes="SQL/data-prep reference only; not production authority.",
    ),
    MTAExternalAsset(
        asset_id="stacktonic-channel-grouping-udf",
        provider="stacktonic",
        asset_type="REFERENCE_TUTORIAL",
        authority="REFERENCE_ONLY",
        url="https://stacktonic.com/article/google-analytics-4-and-big-query-create-custom-channel-groupings-in-a-reusable-sql-function",
        notes="Channel grouping UDF pattern reference only.",
    ),
    MTAExternalAsset(
        asset_id="google-meridian-skills-pattern",
        provider="google",
        repository="google/meridian",
        asset_type="SKILL_PATTERN",
        authority="REFERENCE_ONLY",
        url="https://github.com/google/meridian/tree/main/skills",
        notes="Skill architecture pattern reference for MTA skills.",
    ),
)


def listed_mta_assets() -> tuple[MTAExternalAsset, ...]:
    return MTA_EXTERNAL_ASSETS
