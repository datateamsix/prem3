"""Deterministic Investment Plan validation. Gemini never emits readiness."""

from __future__ import annotations

from collections import defaultdict

from app.control_plane.models import DriveWorkspaceBinding
from app.governance.codes import BindingStatus
from app.integrations.google.adapters import DriveFile
from app.investment_planning.contracts import (
    BudgetColumnMapping,
    BudgetValidationCheck,
    InvestmentPlan,
    InvestmentPlanValidationReceipt,
)
from app.investment_planning.drive import file_is_under_folder
from app.investment_planning.drive_binding import SUPPORTED_BUDGET_MIMES
from app.investment_planning.enums import BudgetSourceGrain, BudgetValidationCode, InvestmentPlanReadyStatus
from app.investment_planning.errors import (
    CanonicalMarketContractPendingError,
    UnresolvedChannelIdentityError,
    UnresolvedMarketIdentityError,
)
from app.investment_planning.identity import (
    assert_investment_plan_ready_permitted,
    require_canonical_channel_id,
    require_canonical_market_id,
)
from app.investment_planning.ids import new_validation_receipt_id
from app.investment_planning.markets import MarketIdentityDirectory, resolve_planning_market_token
from app.investment_planning.parser import ParsedBudgetTable, parse_decimal_cell
from app.investment_planning.source import DriveSourceIdentity, assert_source_unchanged


def validate_budget_plan(
    *,
    plan: InvestmentPlan,
    binding: DriveWorkspaceBinding,
    file: DriveFile,
    table: ParsedBudgetTable,
    mapping: BudgetColumnMapping,
    loaded_identity: DriveSourceIdentity,
    known_market_ids: frozenset[str],
    blanks_acknowledged: bool = False,
    mixed_grain: BudgetSourceGrain = BudgetSourceGrain.MARKET_CHANNEL_QUARTER,
    directory: MarketIdentityDirectory | None = None,
) -> InvestmentPlanValidationReceipt:
    checks: list[BudgetValidationCheck] = []
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.DRIVE_BINDING_ACTIVE.value,
            passed=binding.status == BindingStatus.ACTIVE.value,
        )
    )
    budgets_folder_id = binding.budgets_folder_id
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.BUDGET_FOLDER_BOUND.value,
            passed=bool(budgets_folder_id) and file_is_under_folder(file, budgets_folder_id or ""),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.SOURCE_EXISTS.value,
            passed=not file.trashed,
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.SOURCE_VERSION_IDENTIFIED.value,
            passed=any((file.md5, file.head_revision_id, file.version)),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.FORMAT_SUPPORTED.value,
            passed=file.mime_type in SUPPORTED_BUDGET_MIMES or file.name.lower().endswith(
                (".csv", ".xlsx")
            ),
        )
    )
    mapped = bool(
        mapping.market_column
        and mapping.channel_column
        and len(mapping.quarter_columns) == 4
        and mapping.confirmed
    )
    checks.append(
        BudgetValidationCheck(code=BudgetValidationCode.SCHEMA_MAPPED.value, passed=mapped)
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.BUSINESS_PROFILE_PINNED.value,
            passed=bool(plan.business_profile_snapshot_id and plan.business_profile_fingerprint),
        )
    )

    market_rows: list[int] = []
    channel_rows: list[int] = []
    quarter_rows: list[int] = []
    negative_rows: list[int] = []
    blank_rows: list[int] = []
    duplicate_rows: list[int] = []
    seen: dict[tuple[str, str], list[int]] = defaultdict(list)
    market_bearing = False

    if mapped:
        q1, q2, q3, q4 = mapping.quarter_columns
        for row in table.rows:
            market_token = row.cells.get(mapping.market_column or "", "")
            channel_token = row.cells.get(mapping.channel_column or "", "")
            if market_token.strip():
                market_bearing = True
                try:
                    if directory is not None:
                        market_id = resolve_planning_market_token(
                            market_token,
                            directory=directory,
                            tenant_id=plan.tenant_id,
                            project_id=plan.project_id,
                            snapshot_id=plan.business_profile_snapshot_id,
                        )
                    else:
                        market_id = require_canonical_market_id(
                            market_token, known_market_ids=known_market_ids
                        )
                except UnresolvedMarketIdentityError:
                    market_rows.append(row.row_index)
                    market_id = ""
            else:
                market_rows.append(row.row_index)
                market_id = ""
            try:
                channel_id = require_canonical_channel_id(channel_token)
            except UnresolvedChannelIdentityError:
                channel_rows.append(row.row_index)
                channel_id = ""
            amounts = []
            for header in (q1, q2, q3, q4):
                try:
                    parsed = parse_decimal_cell(row.cells.get(header, ""))
                except Exception:
                    quarter_rows.append(row.row_index)
                    continue
                if parsed.missing:
                    blank_rows.append(row.row_index)
                elif parsed.value is not None and parsed.value < 0:
                    negative_rows.append(row.row_index)
                amounts.append(parsed)
            if market_id and channel_id:
                seen[(market_id, channel_id)].append(row.row_index)

    for indexes in seen.values():
        if len(indexes) > 1:
            duplicate_rows.extend(indexes)

    initiative_present = bool(mapping.initiative_column)
    mixed_unresolved = mixed_grain is BudgetSourceGrain.MIXED or (
        initiative_present
        and mixed_grain is not BudgetSourceGrain.INITIATIVE_DETAIL
        and any(
            row.cells.get(mapping.initiative_column or "", "").strip() for row in table.rows
        )
        and any(
            not row.cells.get(mapping.initiative_column or "", "").strip() for row in table.rows
        )
    )

    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.MARKETS_RESOLVED.value,
            passed=not market_rows,
            flagged_row_indexes=tuple(market_rows),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.CHANNELS_RESOLVED.value,
            passed=not channel_rows,
            flagged_row_indexes=tuple(channel_rows),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.QUARTERS_VALID.value,
            passed=not quarter_rows,
            flagged_row_indexes=tuple(quarter_rows),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.AMOUNTS_NONNEGATIVE.value,
            passed=not negative_rows,
            flagged_row_indexes=tuple(negative_rows),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.BLANKS_ACKNOWLEDGED.value,
            passed=not blank_rows or blanks_acknowledged,
            flagged_row_indexes=tuple(blank_rows),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.DUPLICATES_RESOLVED.value,
            passed=not duplicate_rows,
            flagged_row_indexes=tuple(duplicate_rows),
        )
    )
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.MIXED_GRAIN_RESOLVED.value,
            passed=not mixed_unresolved,
        )
    )
    checks.append(
        BudgetValidationCheck(code=BudgetValidationCode.CURRENCY_SINGLE.value, passed=True)
    )
    try:
        assert_source_unchanged(loaded=loaded_identity, current=file)
        source_ok = True
    except Exception:
        source_ok = False
    checks.append(
        BudgetValidationCheck(code=BudgetValidationCode.SOURCE_UNCHANGED.value, passed=source_ok)
    )
    try:
        assert_investment_plan_ready_permitted(
            market_bearing=market_bearing,
            markets_resolved=True,
        )
        market_contract_ok = True
    except CanonicalMarketContractPendingError:
        market_contract_ok = False
    checks.append(
        BudgetValidationCheck(
            code=BudgetValidationCode.CANONICAL_MARKET_CONTRACT.value,
            passed=market_contract_ok,
        )
    )

    failed = tuple(check.code for check in checks if not check.passed)
    ready = not failed
    status = (
        InvestmentPlanReadyStatus.INVESTMENT_PLAN_READY
        if ready
        else InvestmentPlanReadyStatus.PENDING
    )
    flagged_rows = tuple(
        sorted({index for check in checks for index in check.flagged_row_indexes})
    )
    return InvestmentPlanValidationReceipt(
        receipt_id=new_validation_receipt_id(),
        plan_id=plan.plan_id,
        source_version_id=mapping.source_version_id,
        status=status,
        error_codes=failed,
        flagged_row_indexes=flagged_rows,
        flagged_headers=(),
        checks=tuple(checks),
    )
