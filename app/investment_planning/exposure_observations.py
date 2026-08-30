"""Transient exposure metric observations. Values are not Firestore documents."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Protocol, runtime_checkable

from pydantic import model_validator

from app.investment_planning.contracts import FrozenModel
from app.investment_planning.enums import (
    ExposureFreshnessState,
    ExposureQualityStatus,
    SensitiveDataClass,
)
from app.investment_planning.errors import (
    ExposureEntityMappingRequiredError,
    ExposureSourceNotReadyError,
)
from app.investment_planning.exposure_metrics import get_metric_definition
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.identity import (
    require_canonical_channel_id,
    require_canonical_market_id,
)

_LOGGER = logging.getLogger("prem3.investment_planning.exposure")
_FORBIDDEN_IDENTITY_KEYS = frozenset({"person_id", "member_id", "email", "user_email"})


class ExposureMetricObservation(FrozenModel):
    """Analytical observation. Amount/rate values stay customer-owned and transient."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = (
        SensitiveDataClass.CUSTOMER_AMOUNT_TRANSIENT
    )
    project_id: str
    period: str
    market_id: str
    channel_id: str
    campaign_id: str | None = None
    provider_id: str | None = None
    metric_id: str
    value: Decimal
    unit: str
    source_ref: str
    as_of_time: datetime
    freshness: ExposureFreshnessState
    quality_status: ExposureQualityStatus
    fingerprint: str

    @model_validator(mode="after")
    def _no_person_identity(self) -> ExposureMetricObservation:
        payload = self.model_dump()
        if _FORBIDDEN_IDENTITY_KEYS.intersection(payload):
            raise ValueError("Exposure observations cannot carry person identity.")
        get_metric_definition(self.metric_id)
        return self


def observation_fingerprint(
    *,
    project_id: str,
    period: str,
    market_id: str,
    channel_id: str,
    metric_id: str,
    source_ref: str,
    as_of_time: datetime,
) -> str:
    return metadata_fingerprint(
        {
            "project_id": project_id,
            "period": period,
            "market_id": market_id,
            "channel_id": channel_id,
            "metric_id": metric_id,
            "source_ref": source_ref,
            "as_of_time": as_of_time.isoformat(),
        }
    )


def normalize_observation(
    observation: ExposureMetricObservation,
    *,
    known_market_ids: frozenset[str] | set[str],
    known_campaign_ids: frozenset[str] | set[str] | None = None,
) -> ExposureMetricObservation:
    market_id = require_canonical_market_id(
        observation.market_id, known_market_ids=known_market_ids
    )
    channel_id = require_canonical_channel_id(observation.channel_id)
    if observation.campaign_id:
        known = known_campaign_ids or frozenset()
        if observation.campaign_id not in known:
            raise ExposureEntityMappingRequiredError(
                "campaign_id is not a canonical Identity Graph campaign.",
                code="EXPOSURE_ENTITY_MAPPING_REQUIRED",
            )
    return observation.model_copy(update={"market_id": market_id, "channel_id": channel_id})


@runtime_checkable
class ExposureObservationSource(Protocol):
    def fetch_observations(
        self, *, tenant_id: str, project_id: str, period: str
    ) -> tuple[ExposureMetricObservation, ...]: ...


class TestOnlyExposureObservationAdapter:
    """Synthetic fixture adapter. Never labeled customer-governed."""

    __test__ = False

    def __init__(self, observations: tuple[ExposureMetricObservation, ...] = ()) -> None:
        self._observations = observations

    def fetch_observations(
        self, *, tenant_id: str, project_id: str, period: str
    ) -> tuple[ExposureMetricObservation, ...]:
        del tenant_id
        rows = tuple(
            item
            for item in self._observations
            if item.project_id == project_id and item.period == period
        )
        _LOGGER.info(
            "exposure_observations receipt project_id=%s period=%s row_count=%s",
            project_id,
            period,
            len(rows),
        )
        return rows


class ProductionExposureObservationAdapter:
    """Production seam. DF owns source existence; P6-08 does not discover warehouses."""

    def fetch_observations(
        self, *, tenant_id: str, project_id: str, period: str
    ) -> tuple[ExposureMetricObservation, ...]:
        del tenant_id, project_id, period
        raise ExposureSourceNotReadyError(
            "Governed exposure SourceBinding is not ready for production query.",
            code="EXPOSURE_SOURCE_NOT_READY",
        )
