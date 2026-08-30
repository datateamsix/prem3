"""Definition-specific exposure metrics. No universal composite score."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import model_validator

from app.investment_planning.contracts import FrozenModel
from app.investment_planning.enums import SensitiveDataClass
from app.investment_planning.errors import ExposureMetricNotComparableError
from app.investment_planning.fingerprint import metadata_fingerprint

FORBIDDEN_COMPOSITE_METRIC_IDS = frozenset({"EXPOSURE_QUALITY_SCORE", "DELIVERY_CONFIDENCE"})

POLICY_VERSION = "exposure_metric_catalog/v1"


class ExposureMetricDefinition(FrozenModel):
    """Pinned definition of one exposure metric. Not a quality score."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    metric_id: str
    canonical_name: str
    provider: str | None = None
    numerator_definition: str
    denominator_definition: str
    population: str
    unit: str
    grain: str
    comparability_class: str
    created_at: datetime
    fingerprint: str

    @model_validator(mode="after")
    def _no_universal_score(self) -> ExposureMetricDefinition:
        if self.metric_id in FORBIDDEN_COMPOSITE_METRIC_IDS:
            raise ValueError("Universal exposure quality scores are not a P6-08 metric.")
        return self


def _definition(
    *,
    metric_id: str,
    canonical_name: str,
    numerator: str,
    denominator: str,
    population: str,
    unit: str,
    grain: str,
    comparability_class: str,
    provider: str | None = None,
) -> ExposureMetricDefinition:
    created = datetime.fromisoformat("2026-08-27T00:00:00+00:00")
    fingerprint = metadata_fingerprint(
        {
            "metric_id": metric_id,
            "provider": provider,
            "numerator_definition": numerator,
            "denominator_definition": denominator,
            "population": population,
            "unit": unit,
            "grain": grain,
            "comparability_class": comparability_class,
            "catalog": POLICY_VERSION,
        }
    )
    return ExposureMetricDefinition(
        metric_id=metric_id,
        canonical_name=canonical_name,
        provider=provider,
        numerator_definition=numerator,
        denominator_definition=denominator,
        population=population,
        unit=unit,
        grain=grain,
        comparability_class=comparability_class,
        created_at=created,
        fingerprint=fingerprint,
    )


EXPOSURE_METRIC_CATALOG: tuple[ExposureMetricDefinition, ...] = (
    _definition(
        metric_id="SERVED_IMPRESSIONS",
        canonical_name="Served impressions",
        numerator="served_impressions",
        denominator="1",
        population="ad_server_served",
        unit="count",
        grain="day",
        comparability_class="impression_count_served",
    ),
    _definition(
        metric_id="RENDERED_IMPRESSIONS",
        canonical_name="Rendered impressions",
        numerator="rendered_impressions",
        denominator="1",
        population="rendered_creative",
        unit="count",
        grain="day",
        comparability_class="impression_count_rendered",
    ),
    _definition(
        metric_id="MEASURABLE_IMPRESSIONS",
        canonical_name="Measurable impressions",
        numerator="measurable_impressions",
        denominator="1",
        population="viewability_measurable",
        unit="count",
        grain="day",
        comparability_class="impression_count_measurable",
    ),
    _definition(
        metric_id="VIEWABLE_IMPRESSIONS",
        canonical_name="Viewable impressions",
        numerator="viewable_impressions",
        denominator="1",
        population="mrc_viewable",
        unit="count",
        grain="day",
        comparability_class="impression_count_viewable",
    ),
    _definition(
        metric_id="HUMAN_VALID_IMPRESSIONS",
        canonical_name="Human/valid impressions",
        numerator="human_valid_impressions",
        denominator="1",
        population="ivt_filtered_human",
        unit="count",
        grain="day",
        comparability_class="impression_count_human",
    ),
    _definition(
        metric_id="VIEWABILITY_RATE",
        canonical_name="Viewability rate",
        numerator="viewable_impressions",
        denominator="measurable_impressions",
        population="mrc_viewable",
        unit="rate",
        grain="day",
        comparability_class="viewability_rate_measurable",
        provider="google_ads",
    ),
    _definition(
        metric_id="IVT_RATE",
        canonical_name="Invalid traffic rate",
        numerator="invalid_impressions",
        denominator="served_impressions",
        population="ad_server_served",
        unit="rate",
        grain="day",
        comparability_class="ivt_rate_served",
        provider="google_ads",
    ),
    _definition(
        metric_id="IN_TARGET_RATE",
        canonical_name="In-target delivery rate",
        numerator="in_target_impressions",
        denominator="delivered_impressions",
        population="audience_in_target",
        unit="rate",
        grain="day",
        comparability_class="in_target_rate_audience",
        provider="dv360",
    ),
    _definition(
        metric_id="UNIQUE_REACH",
        canonical_name="Unique reach",
        numerator="unique_persons_reached",
        denominator="1",
        population="provider_cookie_or_device_graph",
        unit="count",
        grain="campaign",
        comparability_class="unique_reach_provider_scoped",
        provider="google_ads",
    ),
    _definition(
        metric_id="INCREMENTAL_REACH",
        canonical_name="Incremental reach",
        numerator="incremental_unique_persons",
        denominator="1",
        population="provider_incremental_vs_baseline",
        unit="count",
        grain="campaign",
        comparability_class="incremental_reach_provider_scoped",
        provider="google_ads",
    ),
    _definition(
        metric_id="AVERAGE_FREQUENCY",
        canonical_name="Average frequency",
        numerator="impressions",
        denominator="unique_reach",
        population="reached_persons",
        unit="ratio",
        grain="campaign",
        comparability_class="average_frequency_mean",
        provider="google_ads",
    ),
    _definition(
        metric_id="OVER_FREQUENCY_SHARE",
        canonical_name="Over-frequency share",
        numerator="persons_above_frequency_cap",
        denominator="unique_reach",
        population="frequency_distribution_bins",
        unit="rate",
        grain="campaign",
        comparability_class="frequency_distribution_share",
        provider="google_ads",
    ),
    _definition(
        metric_id="UNDER_FREQUENCY_SHARE",
        canonical_name="Under-frequency share",
        numerator="persons_below_effective_frequency",
        denominator="unique_reach",
        population="frequency_distribution_bins",
        unit="rate",
        grain="campaign",
        comparability_class="frequency_distribution_share",
        provider="google_ads",
    ),
    _definition(
        metric_id="VIDEO_COMPLETION_RATE",
        canonical_name="Video completion rate",
        numerator="completed_views",
        denominator="video_starts",
        population="video_starts",
        unit="rate",
        grain="day",
        comparability_class="video_completion_rate",
        provider="google_ads",
    ),
    _definition(
        metric_id="ATTENTION_RATE",
        canonical_name="Attention rate",
        numerator="attention_qualified_impressions",
        denominator="measurable_impressions",
        population="attention_vendor_panel",
        unit="rate",
        grain="day",
        comparability_class="attention_vendor_rate",
    ),
    _definition(
        metric_id="INVENTORY_QUALITY_RATE",
        canonical_name="Inventory quality rate",
        numerator="made_for_advertising_impressions",
        denominator="served_impressions",
        population="inventory_classification",
        unit="rate",
        grain="day",
        comparability_class="inventory_quality_rate",
    ),
    _definition(
        metric_id="COST_PER_QUALIFIED_EXPOSURE",
        canonical_name="Cost per qualified exposure",
        numerator="media_cost",
        denominator="qualified_exposures",
        population="qualified_exposure_definition",
        unit="currency_per_count",
        grain="day",
        comparability_class="cost_per_qualified_exposure",
    ),
)

_BY_ID = {item.metric_id: item for item in EXPOSURE_METRIC_CATALOG}


def get_metric_definition(metric_id: str) -> ExposureMetricDefinition:
    definition = _BY_ID.get(metric_id)
    if definition is None:
        raise ExposureMetricNotComparableError(
            f"Unknown exposure metric_id {metric_id!r}.",
            code="EXPOSURE_METRIC_NOT_COMPARABLE",
        )
    return definition


def assert_comparable(
    left: ExposureMetricDefinition,
    right: ExposureMetricDefinition,
    *,
    period: str,
    grain: str,
    provider: str | None = None,
) -> None:
    """Require compatible numerator, denominator, population, period, grain, provider."""
    del period
    forbidden = FORBIDDEN_COMPOSITE_METRIC_IDS
    if left.metric_id in forbidden or right.metric_id in forbidden:
        raise ExposureMetricNotComparableError(
            "Universal exposure quality scores are not comparable.",
            code="EXPOSURE_METRIC_NOT_COMPARABLE",
        )
    if left.comparability_class != right.comparability_class:
        raise ExposureMetricNotComparableError(
            "Exposure metrics are not in the same comparability class.",
            code="EXPOSURE_METRIC_NOT_COMPARABLE",
        )
    if left.numerator_definition != right.numerator_definition:
        raise ExposureMetricNotComparableError(
            "Exposure metric numerators are not compatible.",
            code="EXPOSURE_METRIC_NOT_COMPARABLE",
        )
    if left.denominator_definition != right.denominator_definition:
        raise ExposureMetricNotComparableError(
            "Exposure metric denominators are not compatible.",
            code="EXPOSURE_METRIC_NOT_COMPARABLE",
        )
    if left.population != right.population:
        raise ExposureMetricNotComparableError(
            "Exposure metric populations are not compatible.",
            code="EXPOSURE_METRIC_NOT_COMPARABLE",
        )
    if left.grain != grain or right.grain != grain:
        raise ExposureMetricNotComparableError(
            "Exposure metric grain is not compatible.",
            code="EXPOSURE_METRIC_NOT_COMPARABLE",
        )
    if provider is not None:
        left_mismatch = bool(left.provider and left.provider != provider)
        right_mismatch = bool(right.provider and right.provider != provider)
        if left_mismatch or right_mismatch:
            raise ExposureMetricNotComparableError(
                "Provider metric definitions are not comparable without an explicit mapping.",
                code="EXPOSURE_METRIC_NOT_COMPARABLE",
            )


NAMED_QUALIFIED_IMPRESSIONS_PROXY = "human_viewable_in_target_impressions/v1"


def qualified_impressions_proxy_allowed(
    human: ExposureMetricDefinition,
    viewable: ExposureMetricDefinition,
    in_target: ExposureMetricDefinition,
) -> bool:
    """Named proxy only when all component denominators/populations are compatible."""
    try:
        assert_comparable(
            human, viewable, period="same", grain=human.grain, provider=human.provider
        )
        assert_comparable(
            viewable, in_target, period="same", grain=viewable.grain, provider=viewable.provider
        )
    except ExposureMetricNotComparableError:
        return False
    return True
