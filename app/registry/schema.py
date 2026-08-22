"""Typed provider-registry records."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TrustLevel(StrEnum):
    EXECUTABLE = "executable"
    DIRECTORY = "directory"


class ProviderCategory(StrEnum):
    PAID_SEARCH = "paid_search"
    PAID_SOCIAL = "paid_social"
    DSP = "dsp"
    RETAIL_MEDIA = "retail_media"
    ANALYTICS = "analytics"
    ATTRIBUTION = "attribution"
    COMMERCE = "commerce"
    CRM = "crm"
    VIDEO_CTV = "video_ctv"
    AUDIO = "audio"
    ORGANIC = "organic"
    MEASUREMENT = "measurement"


class FitStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    GAP = "gap"
    UNKNOWN = "unknown"


class RegistryField(BaseModel):
    source_name: str
    semantic_concept: str
    data_type: str | None = None
    summable: bool | None = None
    notes: str | None = None


class MeridianFit(BaseModel):
    time: FitStatus = FitStatus.UNKNOWN
    geo: FitStatus = FitStatus.UNKNOWN
    kpi: FitStatus = FitStatus.UNKNOWN
    media: FitStatus = FitStatus.UNKNOWN
    media_spend: FitStatus = FitStatus.UNKNOWN
    reach_frequency: FitStatus = FitStatus.UNKNOWN
    controls: FitStatus = FitStatus.UNKNOWN


class ProviderRegistryEntry(BaseModel):
    provider_id: str
    display_name: str
    category: ProviderCategory
    report_family: str
    trust: TrustLevel = TrustLevel.DIRECTORY
    export_formats: list[str] = Field(default_factory=list)
    grain: list[str] = Field(default_factory=list)
    date_fields: list[str] = Field(default_factory=list)
    typical_date_formats: list[str] = Field(default_factory=list)
    filename_hints: list[str] = Field(default_factory=list)
    summable_metric_hints: list[str] = Field(default_factory=list)
    non_summable_rate_hints: list[str] = Field(default_factory=list)
    meridian_fit: MeridianFit = Field(default_factory=MeridianFit)
    meridian_gaps: list[str] = Field(default_factory=list)
    fields: list[RegistryField] = Field(default_factory=list)
    quirks: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    retrieved_at: str | None = None
    provider: str | None = None
    typical_grain: list[str] | None = None
    typical_date_fields: list[str] | None = None
    discovery_signatures: list[str] = Field(default_factory=list)
    provisioning_capability: str | None = None
    native_transfer_type: str | None = None
    expected_unique_keys: list[str] = Field(default_factory=list)
    supported_file_patterns: list[str] = Field(default_factory=list)

    def resolved_grain(self) -> list[str]:
        return self.grain or self.typical_grain or []

    def resolved_date_fields(self) -> list[str]:
        return self.date_fields or self.typical_date_fields or []


class ProviderRegistryCatalog(BaseModel):
    version: str
    retrieved_at: str
    providers: list[ProviderRegistryEntry]
