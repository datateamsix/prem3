"""Business-IQ-aware budget template compiler. Bytes are discarded after Drive upload."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from openpyxl import Workbook

from app.business_iq.contracts import BusinessProfile, Market, MarketingChannel
from app.business_iq.enums import ChannelLifecycle
from app.core.errors import InvalidResourceIdentifierError
from app.core.identifiers import validate_resource_identifier
from app.domain.channels.registry import cached_channel_registry
from app.domain.channels.validation import ChannelValidationError, assert_channel_id_in_registry
from app.investment_planning.drive_binding import (
    CSV_MIME,
    TEMPLATE_SCHEMA_VERSION,
    XLSX_MIME,
)

TEMPLATE_HEADERS = (
    "market_id",
    "market_name",
    "channel",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "Budget Status",
    "Notes",
)


@dataclass(frozen=True, slots=True)
class CompiledBudgetTemplate:
    file_name: str
    mime_type: str
    payload: bytes
    schema_version: str
    unresolved_market_names: tuple[str, ...]


def compile_budget_template(
    *,
    profile: BusinessProfile,
    fiscal_year: int,
    as_xlsx: bool = True,
) -> CompiledBudgetTemplate:
    rows, unresolved = _template_rows(profile)
    if as_xlsx:
        payload = _xlsx_bytes(rows)
        mime = XLSX_MIME
        suffix = "xlsx"
    else:
        payload = _csv_bytes(rows)
        mime = CSV_MIME
        suffix = "csv"
    return CompiledBudgetTemplate(
        file_name=f"{TEMPLATE_SCHEMA_VERSION}_FY{fiscal_year}.{suffix}",
        mime_type=mime,
        payload=payload,
        schema_version=TEMPLATE_SCHEMA_VERSION,
        unresolved_market_names=unresolved,
    )


def _template_rows(profile: BusinessProfile) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]:
    registry = cached_channel_registry()
    unresolved: list[str] = []
    canonical_markets: list[Market] = []
    for market in profile.markets:
        try:
            validate_resource_identifier(market.market_id, field="market_id")
        except InvalidResourceIdentifierError:
            unresolved.append(market.name or market.market_id)
            continue
        canonical_markets.append(market)
    channels: list[MarketingChannel] = []
    for channel in profile.marketing_portfolio:
        registry_id = channel.registry_channel_id
        if registry_id is None:
            continue
        try:
            assert_channel_id_in_registry(registry_id, registry)
        except ChannelValidationError:
            continue
        if channel.lifecycle_status is ChannelLifecycle.RETIRED:
            continue
        channels.append(channel)
    rows: list[tuple[str, ...]] = [TEMPLATE_HEADERS]
    for market in canonical_markets:
        for channel in channels:
            declared_markets = channel.markets
            if declared_markets and market.market_id not in declared_markets:
                continue
            rows.append(
                (
                    market.market_id,
                    market.name,
                    channel.registry_channel_id or channel.channel_id,
                    "",
                    "",
                    "",
                    "",
                    "PLANNED",
                    "",
                )
            )
    return tuple(rows), tuple(unresolved)


def _csv_bytes(rows: tuple[tuple[str, ...], ...]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _xlsx_bytes(rows: tuple[tuple[str, ...], ...]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Investment Plan"
    for row in rows:
        sheet.append(list(row))
    payload = io.BytesIO()
    workbook.save(payload)
    return payload.getvalue()
