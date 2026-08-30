"""Optimization-specific causal evidence coverage. MTA is not causal authority."""

from __future__ import annotations

from app.investment_optimization.contracts import (
    ModelConsumptionContract,
    OptimizationEvidenceCoverage,
    OptimizationIssue,
    PortfolioModelMapping,
)
from app.investment_optimization.enums import (
    MappingEntryStatus,
    MarketModelCompatibility,
    OptimizationEvidenceCoverageStatus,
    OptimizationIssueCode,
)
from app.investment_optimization.ids import new_evidence_coverage_id
from app.investment_planning.fingerprint import metadata_fingerprint


def assemble_optimization_evidence_coverage(
    *,
    mapping: PortfolioModelMapping,
    contract: ModelConsumptionContract,
    mta_evidence_ref: str | None = None,
) -> OptimizationEvidenceCoverage:
    covered_channels = tuple(
        sorted(
            {
                entry.channel_id
                for entry in mapping.mapping_entries
                if entry.status
                in {MappingEntryStatus.AUTO_SAFE, MappingEntryStatus.MAPPED}
            }
        )
    )
    uncovered = tuple(
        sorted({cell.channel_id for cell in mapping.unmapped_portfolio_cells})
    )
    review_channels = tuple(
        sorted(
            {
                entry.channel_id
                for entry in mapping.mapping_entries
                if entry.status is MappingEntryStatus.REVIEW_REQUIRED
            }
        )
    )
    covered_markets = tuple(
        sorted(
            {
                entry.market_id
                for entry in mapping.mapping_entries
                if entry.market_compatibility
                in {
                    MarketModelCompatibility.DIRECTLY_MODELED,
                    MarketModelCompatibility.AGGREGATED_IN_MODEL,
                }
            }
        )
    )
    unsupported_markets = tuple(
        sorted(
            {
                entry.market_id
                for entry in mapping.mapping_entries
                if entry.market_compatibility is MarketModelCompatibility.NOT_MODELED
            }
        )
    )
    issues: list[OptimizationIssue] = []
    if mta_evidence_ref and not contract.response_evidence_ref:
        issues.append(
            OptimizationIssue(
                code=OptimizationIssueCode.MTA_NOT_CAUSAL_AUTHORITY,
                blocking=False,
                review_required=False,
                message_key=OptimizationIssueCode.MTA_NOT_CAUSAL_AUTHORITY.value,
            )
        )
    if not covered_channels and uncovered:
        status = OptimizationEvidenceCoverageStatus.MISSING
    elif uncovered or review_channels or unsupported_markets:
        status = OptimizationEvidenceCoverageStatus.PARTIAL
        if review_channels:
            status = OptimizationEvidenceCoverageStatus.REVIEW_REQUIRED
    else:
        status = OptimizationEvidenceCoverageStatus.COVERED
    fingerprint = metadata_fingerprint(
        {
            "model_version_id": contract.model_version_id,
            "snapshot_id": mapping.portfolio_snapshot_id,
            "covered_channel_ids": covered_channels,
            "uncovered_channel_ids": uncovered,
            "accepted_model_ref": contract.model_acceptance_ref,
            "response_evidence_ref": contract.response_evidence_ref,
            "mta_evidence_ref": mta_evidence_ref,
        }
    )
    return OptimizationEvidenceCoverage(
        coverage_id=new_evidence_coverage_id(),
        tenant_id=mapping.tenant_id,
        project_id=mapping.project_id,
        model_version_id=contract.model_version_id,
        portfolio_snapshot_id=mapping.portfolio_snapshot_id,
        covered_channel_ids=covered_channels,
        uncovered_channel_ids=uncovered,
        review_required_channel_ids=review_channels,
        covered_market_ids=covered_markets,
        unsupported_market_ids=unsupported_markets,
        accepted_model_ref=contract.model_acceptance_ref,
        response_evidence_ref=contract.response_evidence_ref,
        optimizer_artifact_ref=contract.optimizer_artifact_ref,
        mta_evidence_ref=mta_evidence_ref,
        status=status,
        issues=tuple(issues),
        fingerprint=fingerprint,
    )
