"""Canonical channel registry models — one channel_id contract across PreM3."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.core.contracts import utc_now


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChannelDefinition(FrozenModel):
    channel_id: str
    display_name: str
    channel_family_id: str
    aliases: tuple[str, ...] = ()
    mta_default: bool = True
    mmm_allowed: bool = True
    deprecated: bool = False


class ChannelRegistry(FrozenModel):
    channel_registry_version: int
    contract: str = "PREM3_CANONICAL_CHANNEL_REGISTRY"
    channels: tuple[ChannelDefinition, ...] = ()
    fingerprint: str
    created_at: datetime = Field(default_factory=utc_now)

    def channel_ids(self) -> frozenset[str]:
        return frozenset(c.channel_id for c in self.channels)

    def get(self, channel_id: str) -> ChannelDefinition | None:
        for channel in self.channels:
            if channel.channel_id == channel_id:
                return channel
        return None


class ChannelGroupingMatchKind(StrEnum):
    EXACT = "EXACT"
    REGEX = "REGEX"
    ANY = "ANY"


class ChannelGroupingRule(FrozenModel):
    rule_id: str
    priority: int
    output_channel_id: str
    source_exact: str | None = None
    source_regex: str | None = None
    medium_exact: str | None = None
    medium_regex: str | None = None
    campaign_exact: str | None = None
    campaign_regex: str | None = None
    enabled: bool = True
    description: str | None = None


class ChannelGroupingRuleSet(FrozenModel):
    version: int
    contract: str = "PREM3_CHANNEL_GROUPING_RULESET"
    fallback_channel_id: str = "other"
    rules: tuple[ChannelGroupingRule, ...] = ()
    fingerprint: str


class ChannelGroupingProposal(FrozenModel):
    proposal_id: str
    ruleset: ChannelGroupingRuleSet
    channel_registry_version: int
    channel_registry_fingerprint: str
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    notes: tuple[str, ...] = ()


class ChannelGroupingApproval(FrozenModel):
    approval_id: str
    proposal_id: str
    ruleset_fingerprint: str
    approved_by: str
    approved_at: datetime = Field(default_factory=utc_now)


class ChannelGroupingProvisioningReceipt(FrozenModel):
    receipt_id: str
    routine_name: str
    routine_version: int
    sql_fingerprint: str
    channel_registry_version: int
    ruleset_fingerprint: str
    verified: bool = False
    generated_at: datetime = Field(default_factory=utc_now)
