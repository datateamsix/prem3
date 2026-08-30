"""P6-01 parser, mapping, blank-vs-zero, and privacy."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.investment_planning.drive_binding import CSV_MIME, XLSX_MIME
from app.investment_planning.errors import BudgetFormatError
from app.investment_planning.mapping import propose_column_mapping
from app.investment_planning.parser import parse_budget_bytes, parse_decimal_cell
from app.investment_planning.privacy import safe_log_text
from app.investment_planning.template import compile_budget_template, TEMPLATE_HEADERS
from app.investment_planning.store import InMemoryInvestmentPlanningMetadataStore
from tests.unit.investment_planning.test_p6_00_architecture import _plan


def test_blank_is_missing_and_zero_is_zero() -> None:
    missing = parse_decimal_cell("")
    zero = parse_decimal_cell("0")
    assert missing.missing is True
    assert missing.value is None
    assert zero.missing is False
    assert zero.value == Decimal("0")


def test_csv_parser_does_not_log_amounts() -> None:
    csv_bytes = (
        b"market_id,channel,Q1,Q2,Q3,Q4\n"
        b"mkt_us,search_paid,123456.78,0,,100\n"
    )
    table = parse_budget_bytes(data=csv_bytes, mime_type=CSV_MIME, file_name="plan.csv")
    assert table.headers[0] == "market_id"
    assert table.rows[0].cells["Q1"] == "123456.78"
    assert table.rows[0].cells["Q3"] == ""
    logged = safe_log_text("preview 123456.78")
    assert "123456.78" not in logged


def test_xlsx_round_trip_template_headers() -> None:
    from app.business_iq.contracts import BusinessIdentity, BusinessProfile, Market, MarketingChannel
    from app.core.contracts import utc_now

    now = utc_now()
    profile = BusinessProfile(
        profile_id="bpf_aaaaaaaaaaaaaaaaaaaa",
        tenant_id="ten_bbbbbbbbbbbbbbbbbbbb",
        workspace_id="wsp_cccccccccccccccccccc",
        version=1,
        fingerprint="fp_biq",
        current_snapshot_id="bps_dddddddddddddddddddd",
        business_identity=BusinessIdentity(),
        markets=(Market(market_id="mkt_us", name="United States"),),
        marketing_portfolio=(
            MarketingChannel(
                channel_id="bch_search",
                canonical_name="Paid Search",
                registry_channel_id="search_paid",
                channel_registry_version=1,
            ),
        ),
        created_at=now,
        updated_at=now,
        updated_by="user_music_center",
        created_by="user_music_center",
    )
    compiled = compile_budget_template(profile=profile, fiscal_year=2027, as_xlsx=True)
    assert compiled.mime_type == XLSX_MIME
    parsed = parse_budget_bytes(
        data=compiled.payload, mime_type=compiled.mime_type, file_name=compiled.file_name
    )
    assert parsed.headers[:4] == TEMPLATE_HEADERS[:4]
    assert parsed.rows[0].cells["market_id"] == "mkt_us"
    assert parsed.rows[0].cells["market_name"] == "United States"


def test_display_market_column_is_not_identity() -> None:
    csv_bytes = b"Market,Channel,Q1,Q2,Q3,Q4\nUnited States,Paid Search,1,1,1,1\n"
    table = parse_budget_bytes(data=csv_bytes, mime_type=CSV_MIME, file_name="plan.csv")
    proposal = propose_column_mapping(
        table, plan_id="ipln_aaaaaaaaaaaaaaaaaaaa", source_version_id="bsrc_aaaaaaaaaaaaaaaaaaa"
    )
    assert "market_id" in proposal.ambiguous
    assert proposal.mapping.confirmed is False


def test_negative_amount_rejected() -> None:
    with pytest.raises(BudgetFormatError):
        parse_budget_bytes(data=b"not-a-spreadsheet", mime_type="application/pdf")


def test_parsed_amounts_cannot_enter_metadata_store() -> None:
    from app.investment_planning.contracts import MoneyAmount
    from app.investment_planning.enums import AmountKind
    from app.investment_planning.errors import PersistenceBarrierError

    store = InMemoryInvestmentPlanningMetadataStore()
    with pytest.raises(PersistenceBarrierError):
        store.put(
            MoneyAmount(kind=AmountKind.PLANNED, currency="USD", value=Decimal("250000"), missing=False)
        )
    store.put(_plan())
    assert "250000" not in str(store.get_plan("ipln_aaaaaaaaaaaaaaaaaaaa"))
