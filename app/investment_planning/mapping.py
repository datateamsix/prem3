"""Header mapping. Stores header identities only, never cell values."""

from __future__ import annotations

from dataclasses import dataclass

from app.investment_planning.contracts import BudgetColumnMapping
from app.investment_planning.enums import MappingMethod
from app.investment_planning.errors import BudgetFormatError
from app.investment_planning.ids import new_mapping_id
from app.investment_planning.parser import ParsedBudgetTable

_MARKET_ID = frozenset({"market_id", "market id", "canonical_market_id"})
_MARKET_DISPLAY = frozenset({"market", "region", "geo", "market name", "market_name"})
_CHANNEL = frozenset({"channel", "media type", "media", "channel name", "channel_id"})
_Q1 = frozenset({"q1", "q1 budget", "first quarter", "quarter 1"})
_Q2 = frozenset({"q2", "q2 budget", "second quarter", "quarter 2"})
_Q3 = frozenset({"q3", "q3 budget", "third quarter", "quarter 3"})
_Q4 = frozenset({"q4", "q4 budget", "fourth quarter", "quarter 4"})
_STATUS = frozenset({"budget status", "status", "locked/flexible"})
_INITIATIVE = frozenset({"initiative", "campaign"})
_INITIATIVE_ID = frozenset({"initiative id", "initiative_id", "campaign id"})
_NOTES = frozenset({"notes", "note", "comment"})
_ROW_TYPE = frozenset({"row type", "row_type", "grain"})


def _norm(header: str) -> str:
    return " ".join(header.strip().lower().replace("_", " ").split())


def _matches(header: str, aliases: frozenset[str]) -> bool:
    return _norm(header) in aliases


@dataclass(frozen=True, slots=True)
class MappingProposal:
    mapping: BudgetColumnMapping
    ambiguous: tuple[str, ...]
    market_display_column: str | None
    row_type_column: str | None


def propose_column_mapping(
    table: ParsedBudgetTable,
    *,
    plan_id: str,
    source_version_id: str,
    confirmed: bool = False,
) -> MappingProposal:
    headers = [header for header in table.headers if header]
    market_id_col = _unique(headers, _MARKET_ID, "market_id")
    market_display = _unique(headers, _MARKET_DISPLAY, "market display")
    channel_col = _unique(headers, _CHANNEL, "channel")
    quarters = (
        _unique(headers, _Q1, "Q1"),
        _unique(headers, _Q2, "Q2"),
        _unique(headers, _Q3, "Q3"),
        _unique(headers, _Q4, "Q4"),
    )
    if None in quarters:
        raise BudgetFormatError("Q1–Q4 columns must be mapped before validation.")
    if channel_col is None:
        raise BudgetFormatError("A channel column must be mapped before validation.")
    if market_id_col is None and market_display is None:
        raise BudgetFormatError("A market_id column is required; display names are not identity.")
    mapping = BudgetColumnMapping(
        mapping_id=new_mapping_id(),
        plan_id=plan_id,
        source_version_id=source_version_id,
        market_column=market_id_col or market_display,
        channel_column=channel_col,
        quarter_columns=tuple(column for column in quarters if column is not None),
        initiative_column=_unique(headers, _INITIATIVE, "initiative"),
        status_column=_unique(headers, _STATUS, "budget status"),
        mapping_method=MappingMethod.EXPLICIT_USER_MAP,
        confirmed=confirmed,
    )
    ambiguous: list[str] = []
    if market_id_col is None:
        ambiguous.append("market_id")
    return MappingProposal(
        mapping=mapping,
        ambiguous=tuple(ambiguous),
        market_display_column=market_display if market_display != market_id_col else None,
        row_type_column=_unique(headers, _ROW_TYPE, "row type"),
    )


def _unique(headers: list[str], aliases: frozenset[str], label: str) -> str | None:
    hits = [header for header in headers if _matches(header, aliases)]
    if len(hits) > 1:
        raise BudgetFormatError(f"Ambiguous {label} column mapping requires confirmation.")
    return hits[0] if hits else None
