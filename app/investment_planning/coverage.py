"""Deterministic portfolio evidence coverage. Not optimization readiness."""

from __future__ import annotations

from app.investment_planning.contracts import (
    ActualSpendSourceRef,
    PortfolioEvidenceCoverage,
    PortfolioEvidenceCoverageItem,
    PortfolioSnapshotRef,
)
from app.investment_planning.enums import (
    EvidenceCoverageLabel,
    EvidenceCoverageScope,
    EvidenceCoverageStatus,
)

OPTIMIZATION_READY = "OPTIMIZATION_READY"


def assemble_evidence_coverage(
    *,
    snapshot: PortfolioSnapshotRef | None,
    actuals_source: ActualSpendSourceRef | None,
    accepted_mmm_result_ref: str | None = None,
    mta_result_ref: str | None = None,
    experiment_ref: str | None = None,
    brand_ref: str | None = None,
    exposure_integrity_ref: str | None = None,
    stale_actuals: bool = False,
) -> PortfolioEvidenceCoverage:
    items: list[PortfolioEvidenceCoverageItem] = []
    labels: list[EvidenceCoverageLabel] = []
    if actuals_source is not None:
        labels.append(EvidenceCoverageLabel.DATA_FOUNDATION)
        items.append(
            PortfolioEvidenceCoverageItem(
                category=EvidenceCoverageLabel.DATA_FOUNDATION,
                scope=EvidenceCoverageScope.PROJECT,
                status=(
                    EvidenceCoverageStatus.REVIEW_REQUIRED
                    if stale_actuals
                    else EvidenceCoverageStatus.COVERED
                ),
                evidence_ref=actuals_source.actuals_source_id,
                causal=False,
            )
        )
    if accepted_mmm_result_ref:
        labels.append(EvidenceCoverageLabel.MMM)
        items.append(
            PortfolioEvidenceCoverageItem(
                category=EvidenceCoverageLabel.MMM,
                scope=EvidenceCoverageScope.PROJECT,
                status=EvidenceCoverageStatus.COVERED,
                evidence_ref=accepted_mmm_result_ref,
                causal=True,
            )
        )
    if mta_result_ref:
        labels.append(EvidenceCoverageLabel.MTA)
        items.append(
            PortfolioEvidenceCoverageItem(
                category=EvidenceCoverageLabel.MTA,
                scope=EvidenceCoverageScope.PROJECT,
                status=EvidenceCoverageStatus.COVERED,
                evidence_ref=mta_result_ref,
                causal=False,
            )
        )
    if experiment_ref:
        labels.append(EvidenceCoverageLabel.EXPERIMENT)
        items.append(
            PortfolioEvidenceCoverageItem(
                category=EvidenceCoverageLabel.EXPERIMENT,
                scope=EvidenceCoverageScope.PROJECT,
                status=EvidenceCoverageStatus.COVERED,
                evidence_ref=experiment_ref,
                causal=False,
            )
        )
    if brand_ref:
        labels.append(EvidenceCoverageLabel.BRAND)
        items.append(
            PortfolioEvidenceCoverageItem(
                category=EvidenceCoverageLabel.BRAND,
                scope=EvidenceCoverageScope.PROJECT,
                status=EvidenceCoverageStatus.COVERED,
                evidence_ref=brand_ref,
                causal=False,
            )
        )
    if exposure_integrity_ref:
        labels.append(EvidenceCoverageLabel.EXPOSURE_INTEGRITY)
        items.append(
            PortfolioEvidenceCoverageItem(
                category=EvidenceCoverageLabel.EXPOSURE_INTEGRITY,
                scope=EvidenceCoverageScope.PROJECT,
                status=EvidenceCoverageStatus.COVERED,
                evidence_ref=exposure_integrity_ref,
                causal=False,
            )
        )
    if not items:
        status = EvidenceCoverageStatus.MISSING
    elif stale_actuals:
        status = EvidenceCoverageStatus.REVIEW_REQUIRED
    elif accepted_mmm_result_ref and mta_result_ref:
        status = EvidenceCoverageStatus.COVERED
    elif accepted_mmm_result_ref or mta_result_ref or actuals_source is not None:
        status = (
            EvidenceCoverageStatus.PARTIAL
            if not accepted_mmm_result_ref
            else EvidenceCoverageStatus.COVERED
        )
    else:
        status = EvidenceCoverageStatus.PARTIAL
    return PortfolioEvidenceCoverage(
        snapshot_id=None if snapshot is None else snapshot.snapshot_id,
        scope=EvidenceCoverageScope.PROJECT,
        status=status,
        labels=tuple(labels),
        items=tuple(items),
        accepted_mmm=accepted_mmm_result_ref is not None,
        mta_available=mta_result_ref is not None,
        exposure_integrity_available=exposure_integrity_ref is not None,
        stale=stale_actuals,
    )


def coverage_payload_has_optimization_ready(coverage: PortfolioEvidenceCoverage) -> bool:
    dumped = coverage.model_dump()
    return OPTIMIZATION_READY in str(dumped)
