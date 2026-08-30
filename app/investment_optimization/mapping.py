"""Deterministic portfolio-to-model mapping. Canonical IDs only; no fuzzy names."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.investment_optimization.contracts import (
    MappingConflict,
    MappingOverride,
    ModelConsumptionContract,
    ModelConsumptionVariable,
    OptimizationIssue,
    PortfolioModelMapping,
    PortfolioModelMappingEntry,
    UnmappedModelVariable,
    UnmappedPortfolioCell,
)
from app.investment_optimization.eligibility import is_budget_optimizable
from app.investment_optimization.enums import (
    GOVERNED_OVERRIDE_AUTHORITIES,
    ORGANIC_CHANNEL_IDS,
    ForbiddenMappingAuthority,
    MappingAuthority,
    MappingCardinalityPolicy,
    MappingEntryStatus,
    MappingKind,
    MarketModelCompatibility,
    ModelGeoSemantics,
    OptimizationIssueCode,
    PortfolioModelMappingStatus,
    UnmappedVariableTreatment,
)
from app.investment_optimization.errors import FuzzyMappingRejectedError
from app.investment_optimization.ids import new_mapping_entry_id, new_portfolio_model_mapping_id
from app.investment_planning.contracts import PortfolioView
from app.investment_planning.enums import AmountKind, PortfolioBaselineKind
from app.investment_planning.fingerprint import metadata_fingerprint


def _issue(
    code: OptimizationIssueCode,
    *,
    blocking: bool,
    review: bool = False,
    market_id: str | None = None,
    channel_id: str | None = None,
    variable_id: str | None = None,
) -> OptimizationIssue:
    return OptimizationIssue(
        code=code,
        blocking=blocking,
        review_required=review,
        message_key=code.value,
        subject_market_id=market_id,
        subject_channel_id=channel_id,
        subject_variable_id=variable_id,
    )


def _entry_fingerprint(payload: dict[str, object]) -> str:
    return metadata_fingerprint(payload)


def reject_forbidden_authority(authority: str) -> None:
    if authority in {item.value for item in ForbiddenMappingAuthority}:
        raise FuzzyMappingRejectedError(
            "Fuzzy, similarity, and LLM mapping cannot become mapping authority."
        )


def classify_market(
    *,
    market_id: str,
    contract: ModelConsumptionContract,
    require_market_level: bool,
    explicit_market_ids: set[str],
) -> MarketModelCompatibility:
    if market_id in explicit_market_ids:
        return MarketModelCompatibility.DIRECTLY_MODELED
    if contract.geo_semantics is ModelGeoSemantics.NATIONAL:
        if require_market_level:
            return MarketModelCompatibility.REVIEW_REQUIRED
        return MarketModelCompatibility.AGGREGATED_IN_MODEL
    if contract.geo_semantics is ModelGeoSemantics.GEO:
        if market_id in explicit_market_ids:
            return MarketModelCompatibility.DIRECTLY_MODELED
        return MarketModelCompatibility.REVIEW_REQUIRED
    if contract.geo_semantics is ModelGeoSemantics.MARKET_FILTERED:
        if market_id in explicit_market_ids:
            return MarketModelCompatibility.DIRECTLY_MODELED
        return MarketModelCompatibility.NOT_MODELED
    if market_id in explicit_market_ids:
        return MarketModelCompatibility.DIRECTLY_MODELED
    return MarketModelCompatibility.NOT_MODELED


def _override_for(
    overrides: tuple[MappingOverride, ...],
    *,
    market_id: str,
    channel_id: str,
) -> MappingOverride | None:
    exact = [
        item
        for item in overrides
        if item.channel_id == channel_id and item.market_id == market_id
    ]
    if exact:
        return exact[-1]
    channel_only = [
        item
        for item in overrides
        if item.channel_id == channel_id and item.market_id is None
    ]
    if channel_only:
        return channel_only[-1]
    return None


def _variables_for_channel(
    contract: ModelConsumptionContract, channel_id: str
) -> tuple[ModelConsumptionVariable, ...]:
    return tuple(
        variable
        for variable in contract.variables
        if variable.canonical_channel_id == channel_id
    )


def build_portfolio_model_mapping(
    *,
    tenant_id: str,
    project_id: str,
    snapshot_id: str,
    baseline_kind: PortfolioBaselineKind,
    view: PortfolioView,
    contract: ModelConsumptionContract,
    created_at: datetime,
    created_by: str,
    overrides: tuple[MappingOverride, ...] = (),
    require_market_level_optimization: bool = False,
) -> PortfolioModelMapping:
    for override in overrides:
        reject_forbidden_authority(override.authority.value)
        if override.authority not in GOVERNED_OVERRIDE_AUTHORITIES:
            raise FuzzyMappingRejectedError(
                "Mapping overrides must use USER_CONFIRMED or APPROVED_CUSTOM_MAPPING."
            )
        if override.split_weights_bps and sum(override.split_weights_bps) != 10_000:
            raise FuzzyMappingRejectedError(
                "APPROVED_ALLOCATION_SPLIT weights must sum to 10000 bps."
            )

    cells = sorted(
        {
            (row.market_id, row.channel_id)
            for row in view.allocations
            if any(
                amount.kind is AmountKind.APPROVED and not amount.missing
                for amount in row.amounts
            )
        }
    )
    explicit_markets = {
        variable.canonical_market_id
        for variable in contract.variables
        if variable.canonical_market_id
    }
    entries: list[PortfolioModelMappingEntry] = []
    unmapped_cells: list[UnmappedPortfolioCell] = []
    conflicts: list[MappingConflict] = []
    channel_to_variables: dict[str, set[str]] = defaultdict(set)
    variable_to_channels: dict[str, set[str]] = defaultdict(set)

    for market_id, channel_id in cells:
        market_compat = classify_market(
            market_id=market_id,
            contract=contract,
            require_market_level=require_market_level_optimization,
            explicit_market_ids=explicit_markets,
        )
        override = _override_for(overrides, market_id=market_id, channel_id=channel_id)
        bound = _variables_for_channel(contract, channel_id)
        issues: list[OptimizationIssue] = []
        if market_compat is MarketModelCompatibility.NOT_MODELED:
            issues.append(
                _issue(
                    OptimizationIssueCode.MARKET_NOT_MODELED,
                    blocking=True,
                    market_id=market_id,
                    channel_id=channel_id,
                )
            )
        if market_compat is MarketModelCompatibility.REVIEW_REQUIRED:
            issues.append(
                _issue(
                    OptimizationIssueCode.MARKET_SCOPE_TOO_GRANULAR,
                    blocking=False,
                    review=True,
                    market_id=market_id,
                    channel_id=channel_id,
                )
            )
        if market_compat is MarketModelCompatibility.AGGREGATED_IN_MODEL:
            issues.append(
                _issue(
                    OptimizationIssueCode.MARKET_SCOPE_TOO_GRANULAR,
                    blocking=False,
                    review=False,
                    market_id=market_id,
                    channel_id=channel_id,
                )
            )

        selected: tuple[ModelConsumptionVariable, ...]
        authority = MappingAuthority.MODEL_CONTRACT_EXACT
        policy: MappingCardinalityPolicy | None = None
        if override is not None:
            authority = override.authority
            policy = override.policy
            by_id = {item.model_variable_id: item for item in contract.variables}
            selected = tuple(
                by_id[item_id]
                for item_id in override.model_variable_ids
                if item_id in by_id
            )
        else:
            selected = bound

        if channel_id in ORGANIC_CHANNEL_IDS:
            for variable in selected:
                if is_budget_optimizable(variable):
                    issues.append(
                        _issue(
                            OptimizationIssueCode.MODEL_VARIABLE_NOT_OPTIMIZABLE,
                            blocking=True,
                            channel_id=channel_id,
                            variable_id=variable.model_variable_id,
                        )
                    )

        if not selected:
            unmapped_cells.append(
                UnmappedPortfolioCell(
                    market_id=market_id,
                    channel_id=channel_id,
                    issue_code=OptimizationIssueCode.PORTFOLIO_CHANNEL_NOT_MODELED,
                )
            )
            if override is not None and override.policy is MappingCardinalityPolicy.EXCLUDED:
                continue
            issues.append(
                _issue(
                    OptimizationIssueCode.PORTFOLIO_CHANNEL_NOT_MODELED,
                    blocking=override is None
                    or override.policy not in {
                        MappingCardinalityPolicy.EXCLUDED,
                        MappingCardinalityPolicy.FIXED_AT_ZERO,
                        MappingCardinalityPolicy.FIXED_BASELINE,
                    },
                    review=override is not None,
                    market_id=market_id,
                    channel_id=channel_id,
                )
            )
            continue

        mapping_kind = MappingKind.ONE_TO_ONE
        if len(selected) > 1:
            mapping_kind = MappingKind.ONE_TO_MANY
        for variable in selected:
            channel_to_variables[channel_id].add(variable.model_variable_id)
            variable_to_channels[variable.model_variable_id].add(channel_id)

        if mapping_kind is MappingKind.ONE_TO_MANY:
            if policy is not MappingCardinalityPolicy.APPROVED_ALLOCATION_SPLIT:
                issues.append(
                    _issue(
                        OptimizationIssueCode.ONE_TO_MANY_MAPPING_REQUIRES_SPLIT,
                        blocking=False,
                        review=True,
                        channel_id=channel_id,
                    )
                )
                conflicts.append(
                    MappingConflict(
                        kind=MappingKind.ONE_TO_MANY,
                        channel_ids=(channel_id,),
                        model_variable_ids=tuple(item.model_variable_id for item in selected),
                        issue_code=OptimizationIssueCode.ONE_TO_MANY_MAPPING_REQUIRES_SPLIT,
                    )
                )

        status = MappingEntryStatus.AUTO_SAFE
        if issues and any(item.review_required for item in issues):
            status = MappingEntryStatus.REVIEW_REQUIRED
        if issues and any(item.blocking for item in issues):
            status = MappingEntryStatus.CONFLICT
        if override is not None and status is MappingEntryStatus.AUTO_SAFE:
            status = MappingEntryStatus.MAPPED
        if not is_budget_optimizable(selected[0]) and mapping_kind is MappingKind.ONE_TO_ONE:
            issues.append(
                _issue(
                    OptimizationIssueCode.MODEL_VARIABLE_NOT_OPTIMIZABLE,
                    blocking=True,
                    channel_id=channel_id,
                    variable_id=selected[0].model_variable_id,
                )
            )
            status = MappingEntryStatus.CONFLICT

        for variable in selected:
            payload = {
                "market_id": market_id,
                "channel_id": channel_id,
                "model_variable_id": variable.model_variable_id,
                "mapping_kind": mapping_kind.value,
                "authority": authority.value,
                "status": status.value,
            }
            entries.append(
                PortfolioModelMappingEntry(
                    mapping_entry_id=new_mapping_entry_id(),
                    market_id=market_id,
                    channel_id=channel_id,
                    model_variable_id=variable.model_variable_id,
                    model_variable_name=variable.model_variable_name,
                    model_market_ref=variable.canonical_market_id,
                    model_geo_scope=variable.model_geo_scope,
                    mapping_kind=mapping_kind,
                    authority=authority,
                    status=status,
                    market_compatibility=market_compat,
                    issues=tuple(issues),
                    fingerprint=_entry_fingerprint(payload),
                )
            )

    many_to_one_channels: dict[str, set[str]] = defaultdict(set)
    aggregated_channels: set[str] = set()
    for variable_id, channel_ids in variable_to_channels.items():
        if len(channel_ids) > 1:
            for channel_id in channel_ids:
                many_to_one_channels[channel_id].add(variable_id)
            override = next(
                (
                    item
                    for item in overrides
                    if item.channel_id in channel_ids
                    and item.policy is MappingCardinalityPolicy.AGGREGATE_FOR_MODEL
                ),
                None,
            )
            if override is None:
                conflicts.append(
                    MappingConflict(
                        kind=MappingKind.MANY_TO_ONE,
                        channel_ids=tuple(sorted(channel_ids)),
                        model_variable_ids=(variable_id,),
                        issue_code=OptimizationIssueCode.MANY_TO_ONE_MAPPING_REDUCES_CONTROL,
                    )
                )
            else:
                aggregated_channels.update(channel_ids)

    many_to_many = False
    multi_var_channels = {ch for ch, vars_ in channel_to_variables.items() if len(vars_) > 1}
    multi_ch_vars = {vid for vid, chs in variable_to_channels.items() if len(chs) > 1}
    if multi_var_channels and multi_ch_vars:
        many_to_many = True
        conflicts.append(
            MappingConflict(
                kind=MappingKind.MANY_TO_MANY,
                channel_ids=tuple(sorted(multi_var_channels)),
                model_variable_ids=tuple(sorted(multi_ch_vars)),
                issue_code=OptimizationIssueCode.MANY_TO_MANY_MAPPING_UNSUPPORTED,
            )
        )

    mapped_variable_ids = {entry.model_variable_id for entry in entries}
    unmapped_variables: list[UnmappedModelVariable] = []
    for variable in contract.variables:
        if not is_budget_optimizable(variable):
            continue
        if variable.model_variable_id in mapped_variable_ids:
            continue
        override = next(
            (
                item
                for item in overrides
                if variable.model_variable_id in item.model_variable_ids
                and item.unmapped_treatment is not None
            ),
            None,
        )
        treatment = (
            UnmappedVariableTreatment.REVIEW_REQUIRED
            if override is None or override.unmapped_treatment is None
            else override.unmapped_treatment
        )
        unmapped_variables.append(
            UnmappedModelVariable(
                model_variable_id=variable.model_variable_id,
                treatment=treatment,
                issue_code=OptimizationIssueCode.MODEL_VARIABLE_WITHOUT_PORTFOLIO_ALLOCATION,
            )
        )

    if many_to_one_channels and not many_to_many:
        for entry_index, entry in enumerate(entries):
            if entry.channel_id not in many_to_one_channels:
                continue
            if entry.channel_id in aggregated_channels:
                entries[entry_index] = entry.model_copy(
                    update={"mapping_kind": MappingKind.MANY_TO_ONE}
                )
                continue
            extra = _issue(
                OptimizationIssueCode.MANY_TO_ONE_MAPPING_REDUCES_CONTROL,
                blocking=False,
                review=True,
                channel_id=entry.channel_id,
                variable_id=entry.model_variable_id,
            )
            entries[entry_index] = entry.model_copy(
                update={
                    "mapping_kind": MappingKind.MANY_TO_ONE,
                    "status": MappingEntryStatus.REVIEW_REQUIRED,
                    "issues": (*entry.issues, extra),
                }
            )

    blocking = any(
        issue.blocking for entry in entries for issue in entry.issues
    ) or any(
        conflict.issue_code is OptimizationIssueCode.MANY_TO_MANY_MAPPING_UNSUPPORTED
        for conflict in conflicts
    )
    review = (
        any(entry.status is MappingEntryStatus.REVIEW_REQUIRED for entry in entries)
        or any(
            conflict.issue_code
            in {
                OptimizationIssueCode.ONE_TO_MANY_MAPPING_REQUIRES_SPLIT,
                OptimizationIssueCode.MANY_TO_ONE_MAPPING_REDUCES_CONTROL,
            }
            for conflict in conflicts
        )
        or any(
            item.treatment is UnmappedVariableTreatment.REVIEW_REQUIRED
            for item in unmapped_variables
        )
        or bool(unmapped_cells)
    )
    if many_to_many:
        status = PortfolioModelMappingStatus.NOT_READY
    elif blocking:
        status = PortfolioModelMappingStatus.NOT_READY
    elif review:
        status = PortfolioModelMappingStatus.REVIEW_REQUIRED
    else:
        status = PortfolioModelMappingStatus.COMPLETE

    mapped_cell_keys = {(entry.market_id, entry.channel_id) for entry in entries}
    review_required_cells = len(
        {
            (entry.market_id, entry.channel_id)
            for entry in entries
            if entry.status is MappingEntryStatus.REVIEW_REQUIRED
        }
    )
    optimizable = [item for item in contract.variables if is_budget_optimizable(item)]
    mapping_id = new_portfolio_model_mapping_id()
    fingerprint = metadata_fingerprint(
        {
            "snapshot_id": snapshot_id,
            "model_version_id": contract.model_version_id,
            "baseline_kind": baseline_kind.value,
            "entries": [entry.fingerprint for entry in entries],
            "unmapped_cells": [item.model_dump(mode="json") for item in unmapped_cells],
            "unmapped_variables": [item.model_dump(mode="json") for item in unmapped_variables],
            "conflicts": [item.model_dump(mode="json") for item in conflicts],
        }
    )
    return PortfolioModelMapping(
        mapping_id=mapping_id,
        tenant_id=tenant_id,
        project_id=project_id,
        portfolio_snapshot_id=snapshot_id,
        model_version_id=contract.model_version_id,
        baseline_kind=baseline_kind,
        mapping_status=status,
        mapping_entries=tuple(entries),
        unmapped_portfolio_cells=tuple(unmapped_cells),
        unmapped_model_variables=tuple(unmapped_variables),
        conflicts=tuple(conflicts),
        portfolio_cells_total=len(cells),
        mapped_cells=len(mapped_cell_keys),
        unmapped_cells=len(unmapped_cells),
        review_required_cells=review_required_cells,
        model_variables_total=len(contract.variables),
        optimizable_model_variables=len(optimizable),
        mapped_optimizable_variables=len(
            {
                entry.model_variable_id
                for entry in entries
                if entry.model_variable_id
                in {item.model_variable_id for item in optimizable}
            }
        ),
        created_at=created_at,
        created_by=created_by,
        fingerprint=fingerprint,
    )
