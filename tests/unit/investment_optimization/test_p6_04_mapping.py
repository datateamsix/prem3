"""P6-04 channel, market, and cardinality mapping."""

from __future__ import annotations

import pytest

from app.investment_optimization.contracts import MappingOverride
from app.investment_optimization.enums import (
    MappingAuthority,
    MappingCardinalityPolicy,
    MappingKind,
    MarketModelCompatibility,
    ModelGeoSemantics,
    ModelVariableOptimizationEligibility,
    ModelVariableRole,
    OptimizationIssueCode,
    PortfolioModelMappingStatus,
)
from app.investment_optimization.errors import FuzzyMappingRejectedError
from app.investment_optimization.mapping import (
    build_portfolio_model_mapping,
    reject_forbidden_authority,
)
from tests.unit.investment_optimization.p6_04_support import (
    PROJECT,
    TENANT,
    allocation,
    complete_contract,
    now,
    portfolio_view,
    spend_variable,
)


def _map(view, contract, overrides=(), require_market_level=False):
    return build_portfolio_model_mapping(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot_id=view.snapshot_id,
        baseline_kind=view.baseline_kind,
        view=view,
        contract=contract,
        created_at=now(),
        created_by="user_music_center",
        overrides=overrides,
        require_market_level_optimization=require_market_level,
    )


def test_exact_canonical_channel_mapping() -> None:
    mapping = _map(portfolio_view(), complete_contract())
    assert mapping.mapping_entries[0].channel_id == "search_paid"
    assert mapping.mapping_entries[0].model_variable_id == "search_spend"
    assert mapping.mapping_entries[0].authority is MappingAuthority.MODEL_CONTRACT_EXACT
    assert mapping.mapping_entries[0].mapping_kind is MappingKind.ONE_TO_ONE


def test_channel_name_similarity_not_authority() -> None:
    with pytest.raises(FuzzyMappingRejectedError):
        reject_forbidden_authority("FUZZY_NAME")
    with pytest.raises(FuzzyMappingRejectedError):
        reject_forbidden_authority("STRING_SIMILARITY")
    with pytest.raises(FuzzyMappingRejectedError):
        reject_forbidden_authority("LLM_INFERRED")


def test_unmodeled_portfolio_channel_detected() -> None:
    view = portfolio_view(rows=(allocation("mkt_us", "tv_paid"),))
    mapping = _map(view, complete_contract())
    assert mapping.unmapped_cells == 1
    assert (
        mapping.unmapped_portfolio_cells[0].issue_code
        is OptimizationIssueCode.PORTFOLIO_CHANNEL_NOT_MODELED
    )


def test_control_variable_not_optimizable() -> None:
    contract = complete_contract(
        variables=(
            spend_variable(
                "promo",
                "search_paid",
                eligibility=ModelVariableOptimizationEligibility.CONTROL,
                role=ModelVariableRole.CONTROL,
                semantics=None,
            ),
        )
    )
    mapping = _map(portfolio_view(), contract)
    assert any(
        issue.code is OptimizationIssueCode.MODEL_VARIABLE_NOT_OPTIMIZABLE
        for entry in mapping.mapping_entries
        for issue in entry.issues
    )


def test_organic_channel_not_automatically_optimizable() -> None:
    view = portfolio_view(rows=(allocation("mkt_us", "search_organic"),))
    contract = complete_contract(
        variables=(
            spend_variable(
                "organic_sessions",
                "search_organic",
                eligibility=ModelVariableOptimizationEligibility.OPTIMIZABLE,
            ),
        )
    )
    mapping = _map(view, contract)
    assert mapping.mapping_status is PortfolioModelMappingStatus.NOT_READY
    assert any(
        issue.code is OptimizationIssueCode.MODEL_VARIABLE_NOT_OPTIMIZABLE
        for entry in mapping.mapping_entries
        for issue in entry.issues
    )


def test_exact_canonical_market_mapping() -> None:
    contract = complete_contract(
        geo=ModelGeoSemantics.MARKET_FILTERED,
        variables=(spend_variable(market_id="mkt_us"),),
    )
    mapping = _map(portfolio_view(), contract)
    assert (
        mapping.mapping_entries[0].market_compatibility
        is MarketModelCompatibility.DIRECTLY_MODELED
    )


def test_market_display_label_not_authority() -> None:
    contract = complete_contract(
        geo=ModelGeoSemantics.MARKET_FILTERED,
        variables=(spend_variable(market_id="United States"),),
    )
    mapping = _map(portfolio_view(), contract)
    assert mapping.mapping_entries[0].market_compatibility is MarketModelCompatibility.NOT_MODELED


def test_national_model_does_not_claim_market_level_precision() -> None:
    view = portfolio_view(
        rows=(allocation("mkt_us_east", "search_paid"), allocation("mkt_us_west", "search_paid"))
    )
    mapping = _map(view, complete_contract(geo=ModelGeoSemantics.NATIONAL))
    assert all(
        entry.market_compatibility is MarketModelCompatibility.AGGREGATED_IN_MODEL
        for entry in mapping.mapping_entries
    )
    assert MarketModelCompatibility.DIRECTLY_MODELED not in {
        entry.market_compatibility for entry in mapping.mapping_entries
    }


def test_geo_model_requires_explicit_market_geo_mapping() -> None:
    contract = complete_contract(geo=ModelGeoSemantics.GEO, variables=(spend_variable(),))
    mapping = _map(portfolio_view(), contract)
    assert (
        mapping.mapping_entries[0].market_compatibility
        is MarketModelCompatibility.REVIEW_REQUIRED
    )


def test_unmodeled_market_detected() -> None:
    contract = complete_contract(
        geo=ModelGeoSemantics.MARKET_FILTERED,
        variables=(spend_variable(market_id="mkt_uk"),),
    )
    mapping = _map(portfolio_view(), contract)
    assert mapping.mapping_entries[0].market_compatibility is MarketModelCompatibility.NOT_MODELED
    assert any(
        issue.code is OptimizationIssueCode.MARKET_NOT_MODELED
        for entry in mapping.mapping_entries
        for issue in entry.issues
    )


def test_one_to_one_mapping_ready() -> None:
    mapping = _map(portfolio_view(), complete_contract())
    assert mapping.mapping_status is PortfolioModelMappingStatus.COMPLETE
    assert mapping.mapped_cells == 1
    assert mapping.unmapped_cells == 0


def test_many_to_one_mapping_explicit() -> None:
    view = portfolio_view(
        rows=(allocation("mkt_us", "search_paid"), allocation("mkt_us", "shopping_paid"))
    )
    contract = complete_contract(
        variables=(
            spend_variable("combined", "search_paid"),
            spend_variable("combined", "shopping_paid"),
        )
    )
    # two channels, same variable id via two ModelConsumptionVariable copies with same id
    contract = complete_contract(
        variables=(
            spend_variable("combined_paid_search", "search_paid"),
            spend_variable("combined_paid_search", "shopping_paid"),
        )
    )
    without = _map(view, contract)
    assert any(
        conflict.kind is MappingKind.MANY_TO_ONE for conflict in without.conflicts
    )
    with_policy = _map(
        view,
        contract,
        overrides=(
            MappingOverride(
                channel_id="search_paid",
                model_variable_ids=("combined_paid_search",),
                authority=MappingAuthority.APPROVED_CUSTOM_MAPPING,
                policy=MappingCardinalityPolicy.AGGREGATE_FOR_MODEL,
            ),
            MappingOverride(
                channel_id="shopping_paid",
                model_variable_ids=("combined_paid_search",),
                authority=MappingAuthority.APPROVED_CUSTOM_MAPPING,
                policy=MappingCardinalityPolicy.AGGREGATE_FOR_MODEL,
            ),
        ),
    )
    assert with_policy.conflicts == ()


def test_one_to_many_requires_approved_split() -> None:
    contract = complete_contract(
        variables=(
            spend_variable("meta_spend", "social_paid"),
            spend_variable("tiktok_spend", "social_paid"),
        )
    )
    view = portfolio_view(rows=(allocation("mkt_us", "social_paid"),))
    without = _map(view, contract)
    assert any(
        conflict.issue_code is OptimizationIssueCode.ONE_TO_MANY_MAPPING_REQUIRES_SPLIT
        for conflict in without.conflicts
    )
    with_split = _map(
        view,
        contract,
        overrides=(
            MappingOverride(
                channel_id="social_paid",
                model_variable_ids=("meta_spend", "tiktok_spend"),
                authority=MappingAuthority.USER_CONFIRMED,
                policy=MappingCardinalityPolicy.APPROVED_ALLOCATION_SPLIT,
                split_weights_bps=(5000, 5000),
            ),
        ),
    )
    assert with_split.conflicts == ()


def test_many_to_many_not_supported_v1() -> None:
    view = portfolio_view(
        rows=(allocation("mkt_us", "search_paid"), allocation("mkt_us", "social_paid"))
    )
    contract = complete_contract(
        variables=(
            spend_variable("a", "search_paid"),
            spend_variable("b", "search_paid"),
            spend_variable("a", "social_paid"),
            spend_variable("b", "social_paid"),
        )
    )
    mapping = _map(view, contract)
    assert mapping.mapping_status is PortfolioModelMappingStatus.NOT_READY
    assert any(
        conflict.issue_code is OptimizationIssueCode.MANY_TO_MANY_MAPPING_UNSUPPORTED
        for conflict in mapping.conflicts
    )


def test_mapping_conflict_review_required() -> None:
    contract = complete_contract(
        variables=(
            spend_variable("meta_spend", "social_paid"),
            spend_variable("tiktok_spend", "social_paid"),
        )
    )
    mapping = _map(portfolio_view(rows=(allocation("mkt_us", "social_paid"),)), contract)
    assert mapping.mapping_status is PortfolioModelMappingStatus.REVIEW_REQUIRED
