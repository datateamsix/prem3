"""Optimization readiness evaluation. Readiness is not execution approval."""

from __future__ import annotations

from datetime import datetime

from app.investment_optimization.compatibility import (
    approved_plan_present,
    currency_issues,
    period_issues,
    spend_semantics_issues,
)
from app.investment_optimization.contracts import (
    ModelConsumptionContract,
    OptimizationEvidenceCoverage,
    OptimizationInputContract,
    OptimizationIssue,
    OptimizationReadinessCheck,
    OptimizationReadinessReceipt,
    PortfolioModelMapping,
)
from app.investment_optimization.eligibility import is_budget_optimizable
from app.investment_optimization.enums import (
    BLOCKING_OBSERVATION_TYPES,
    POLICY_VERSION,
    REQUIRED_READINESS_CHECKS,
    MappingEntryStatus,
    OptimizationInputStatus,
    OptimizationIssueCode,
    OptimizationReadinessCheckCode,
    OptimizationReadinessStatus,
    PortfolioModelMappingStatus,
    UnmappedVariableTreatment,
)
from app.investment_optimization.ids import new_optimization_input_id, new_readiness_receipt_id
from app.investment_planning.contracts import PortfolioSnapshotRef, PortfolioView
from app.investment_planning.enums import PortfolioBaselineKind, PortfolioCoverageState
from app.investment_planning.fingerprint import metadata_fingerprint


def _issue(
    code: OptimizationIssueCode,
    *,
    blocking: bool,
    review: bool = False,
) -> OptimizationIssue:
    return OptimizationIssue(
        code=code,
        blocking=blocking,
        review_required=review,
        message_key=code.value,
    )


def _check(code: OptimizationReadinessCheckCode, passed: bool) -> OptimizationReadinessCheck:
    return OptimizationReadinessCheck(code=code, passed=passed)


def _horizon_bounds(fiscal_year: int) -> tuple[str, str]:
    return f"{fiscal_year}-01-01", f"{fiscal_year}-12-31"


def build_optimization_input_contract(
    *,
    tenant_id: str,
    project_id: str,
    snapshot: PortfolioSnapshotRef,
    view: PortfolioView,
    mapping: PortfolioModelMapping,
    contract: ModelConsumptionContract,
    created_at: datetime,
    issues: tuple[OptimizationIssue, ...],
) -> OptimizationInputContract:
    start, end = _horizon_bounds(view.fiscal_year)
    optimizable = [
        variable.model_variable_id
        for variable in contract.variables
        if is_budget_optimizable(variable)
        and any(
            entry.model_variable_id == variable.model_variable_id
            and entry.status in {MappingEntryStatus.AUTO_SAFE, MappingEntryStatus.MAPPED}
            for entry in mapping.mapping_entries
        )
    ]
    fixed = [
        item.model_variable_id
        for item in mapping.unmapped_model_variables
        if item.treatment
        in {UnmappedVariableTreatment.FIXED_AT_ZERO, UnmappedVariableTreatment.FIXED_BASELINE}
    ]
    excluded = [
        item.model_variable_id
        for item in mapping.unmapped_model_variables
        if item.treatment is UnmappedVariableTreatment.EXCLUDED
    ]
    if mapping.mapping_status is PortfolioModelMappingStatus.COMPLETE and not any(
        issue.blocking or issue.review_required for issue in issues
    ):
        status = OptimizationInputStatus.READY
    elif any(issue.blocking for issue in issues):
        status = OptimizationInputStatus.NOT_READY
    else:
        status = OptimizationInputStatus.REVIEW_REQUIRED
    fingerprint = metadata_fingerprint(
        {
            "portfolio_snapshot_id": snapshot.snapshot_id,
            "model_version_id": contract.model_version_id,
            "baseline_kind": PortfolioBaselineKind.APPROVED_PLAN.value,
            "period": [start, end],
            "currency": view.currency,
            "optimizable_variable_ids": optimizable,
            "fixed_variable_ids": fixed,
            "excluded_variable_ids": excluded,
            "mapping_fingerprint": mapping.fingerprint,
            "portfolio_fingerprint": snapshot.fingerprint,
            "model_contract_fingerprint": contract.fingerprint,
        }
    )
    return OptimizationInputContract(
        optimization_input_id=new_optimization_input_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        portfolio_snapshot_id=snapshot.snapshot_id,
        model_version_id=contract.model_version_id,
        mapping_id=mapping.mapping_id,
        baseline_kind=PortfolioBaselineKind.APPROVED_PLAN,
        budget_period_start=start,
        budget_period_end=end,
        currency=view.currency,
        plan_id=snapshot.investment_plan_id,
        plan_version_fingerprint=snapshot.fingerprint,
        drive_file_id=snapshot.drive_artifact_file_id,
        optimizable_variable_ids=tuple(optimizable),
        fixed_variable_ids=tuple(fixed),
        excluded_variable_ids=tuple(excluded),
        mapping_fingerprint=mapping.fingerprint,
        portfolio_fingerprint=snapshot.fingerprint,
        model_contract_fingerprint=contract.fingerprint,
        status=status,
        issues=issues,
        fingerprint=fingerprint,
        created_at=created_at,
    )


def evaluate_readiness(
    *,
    tenant_id: str,
    project_id: str,
    coverage_state: PortfolioCoverageState,
    snapshot: PortfolioSnapshotRef | None,
    view: PortfolioView | None,
    contract: ModelConsumptionContract | None,
    mapping: PortfolioModelMapping | None,
    coverage: OptimizationEvidenceCoverage | None,
    input_contract: OptimizationInputContract | None,
    created_at: datetime,
    extra_issues: tuple[OptimizationIssue, ...] = (),
    fiscal_start_month: int = 1,
) -> OptimizationReadinessReceipt:
    issues: list[OptimizationIssue] = list(extra_issues)
    if coverage_state is PortfolioCoverageState.NEITHER:
        return _receipt(
            tenant_id=tenant_id,
            project_id=project_id,
            snapshot=snapshot,
            contract=contract,
            mapping=mapping,
            input_contract=input_contract,
            created_at=created_at,
            status=OptimizationReadinessStatus.NOT_CONFIGURED,
            checks=tuple(
                _check(code, False) for code in REQUIRED_READINESS_CHECKS
            ),
            issues=(),
        )
    if coverage_state is PortfolioCoverageState.ACTUALS_ONLY:
        issues.append(_issue(OptimizationIssueCode.APPROVED_PLAN_REQUIRED, blocking=True))
        return _receipt(
            tenant_id=tenant_id,
            project_id=project_id,
            snapshot=snapshot,
            contract=contract,
            mapping=mapping,
            input_contract=input_contract,
            created_at=created_at,
            status=OptimizationReadinessStatus.NOT_READY,
            checks=tuple(_check(code, False) for code in REQUIRED_READINESS_CHECKS),
            issues=tuple(issues),
        )
    if view is not None and view.baseline_kind is not PortfolioBaselineKind.APPROVED_PLAN:
        issues.append(
            _issue(OptimizationIssueCode.ACTUALS_NEVER_REPLACE_APPROVED_BASELINE, blocking=True)
        )

    if view is not None:
        for observation in view.observations:
            if observation.observation_type.value in BLOCKING_OBSERVATION_TYPES:
                issues.append(
                    OptimizationIssue(
                        code=OptimizationIssueCode.OBSERVATION_BLOCKER,
                        blocking=True,
                        review_required=False,
                        message_key=observation.observation_type.value,
                        subject_market_id=observation.subject_market_id,
                        subject_channel_id=observation.subject_channel_id,
                    )
                )

    if mapping is not None:
        for entry in mapping.mapping_entries:
            issues.extend(entry.issues)
        for conflict in mapping.conflicts:
            issues.append(
                _issue(
                    conflict.issue_code,
                    blocking=conflict.issue_code
                    is OptimizationIssueCode.MANY_TO_MANY_MAPPING_UNSUPPORTED,
                    review=conflict.issue_code
                    is not OptimizationIssueCode.MANY_TO_MANY_MAPPING_UNSUPPORTED,
                )
            )
        for cell in mapping.unmapped_portfolio_cells:
            issues.append(
                _issue(cell.issue_code, blocking=True, review=False)
            )
        for variable in mapping.unmapped_model_variables:
            issues.append(
                _issue(
                    variable.issue_code,
                    blocking=False,
                    review=variable.treatment is UnmappedVariableTreatment.REVIEW_REQUIRED,
                )
            )
    if contract is not None:
        issues.extend(contract.issues)
        if view is not None:
            issues.extend(
                period_issues(
                    view=view, contract=contract, fiscal_start_month=fiscal_start_month
                )
            )
            issues.extend(currency_issues(view=view, contract=contract))
        if mapping is not None:
            issues.extend(spend_semantics_issues(mapping=mapping, contract=contract))
    if coverage is not None:
        issues.extend(coverage.issues)

    def _has(code: OptimizationIssueCode) -> bool:
        return any(issue.code is code for issue in issues)

    def _blocking(code: OptimizationIssueCode) -> bool:
        return any(issue.code is code and issue.blocking for issue in issues)

    approved = (
        coverage_state
        in {PortfolioCoverageState.PLAN_ONLY, PortfolioCoverageState.PLAN_AND_ACTUALS}
        and view is not None
        and approved_plan_present(view)
        and snapshot is not None
        and snapshot.baseline_kind is PortfolioBaselineKind.APPROVED_PLAN
    )
    snapshot_valid = snapshot is not None and view is not None
    model_accepted = (
        contract is not None
        and contract.complete
        and contract.accepted_model_state == "MODEL_ACCEPTED"
        and not _has(OptimizationIssueCode.NO_ACCEPTED_MODEL)
        and not _has(OptimizationIssueCode.MULTIPLE_ACCEPTED_MODELS)
    )
    contract_valid = contract is not None and contract.complete
    artifacts = (
        contract is not None
        and bool(contract.optimizer_artifact_ref or contract.response_evidence_ref)
        and not _has(OptimizationIssueCode.OPTIMIZER_INPUT_ARTIFACT_MISSING)
        and not _has(OptimizationIssueCode.MODEL_RUNTIME_INCOMPATIBLE)
    )
    market_ok = (
        mapping is not None
        and not _blocking(OptimizationIssueCode.MARKET_NOT_MODELED)
        and not any(
            issue.code is OptimizationIssueCode.MARKET_SCOPE_TOO_GRANULAR and issue.review_required
            for issue in issues
        )
    )
    channels_ok = (
        mapping is not None
        and mapping.unmapped_cells == 0
        and mapping.mapping_status is not PortfolioModelMappingStatus.NOT_READY
        and not _blocking(OptimizationIssueCode.PORTFOLIO_CHANNEL_NOT_MODELED)
    )
    period_ok = not any(
        issue.code is OptimizationIssueCode.PERIOD_COMPATIBILITY_REVIEW_REQUIRED
        for issue in issues
    )
    currency_ok = not any(
        issue.code is OptimizationIssueCode.CURRENCY_COMPATIBILITY_REVIEW_REQUIRED
        for issue in issues
    )
    spend_ok = not _has(OptimizationIssueCode.SPEND_SEMANTICS_MISMATCH)
    variables_ok = not _blocking(OptimizationIssueCode.MODEL_VARIABLE_NOT_OPTIMIZABLE)
    conflicts_ok = (
        mapping is not None
        and not mapping.conflicts
        and mapping.mapping_status is PortfolioModelMappingStatus.COMPLETE
    )
    input_ok = (
        input_contract is not None
        and bool(input_contract.fingerprint)
        and input_contract.baseline_kind is PortfolioBaselineKind.APPROVED_PLAN
    )

    checks = (
        _check(OptimizationReadinessCheckCode.APPROVED_PLAN_AVAILABLE, approved),
        _check(OptimizationReadinessCheckCode.PORTFOLIO_SNAPSHOT_VALID, snapshot_valid),
        _check(OptimizationReadinessCheckCode.MODEL_ACCEPTED, model_accepted),
        _check(
            OptimizationReadinessCheckCode.MODEL_CONSUMPTION_CONTRACT_VALID, contract_valid
        ),
        _check(OptimizationReadinessCheckCode.MODEL_OPTIMIZER_ARTIFACTS_AVAILABLE, artifacts),
        _check(OptimizationReadinessCheckCode.MARKET_COMPATIBLE, market_ok),
        _check(OptimizationReadinessCheckCode.CHANNEL_MAPPING_COMPLETE, channels_ok),
        _check(OptimizationReadinessCheckCode.PERIOD_COMPATIBLE, period_ok),
        _check(OptimizationReadinessCheckCode.CURRENCY_COMPATIBLE, currency_ok),
        _check(OptimizationReadinessCheckCode.SPEND_SEMANTICS_COMPATIBLE, spend_ok),
        _check(OptimizationReadinessCheckCode.OPTIMIZABLE_VARIABLES_VALID, variables_ok),
        _check(OptimizationReadinessCheckCode.NO_UNRESOLVED_MAPPING_CONFLICTS, conflicts_ok),
        _check(OptimizationReadinessCheckCode.INPUT_CONTRACT_FINGERPRINTED, input_ok),
    )
    unique_issues: list[OptimizationIssue] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for issue in issues:
        key = (issue.code.value, issue.subject_channel_id, issue.subject_variable_id)
        if key in seen:
            continue
        seen.add(key)
        unique_issues.append(issue)

    all_passed = all(item.passed for item in checks)
    any_blocking = any(issue.blocking for issue in unique_issues)
    any_review = any(issue.review_required for issue in unique_issues)
    if all_passed and not any_blocking and not any_review:
        status = OptimizationReadinessStatus.OPTIMIZATION_READY
    elif any_review and not any_blocking:
        status = OptimizationReadinessStatus.REVIEW_REQUIRED
    else:
        status = OptimizationReadinessStatus.NOT_READY

    return _receipt(
        tenant_id=tenant_id,
        project_id=project_id,
        snapshot=snapshot,
        contract=contract,
        mapping=mapping,
        input_contract=input_contract,
        created_at=created_at,
        status=status,
        checks=checks,
        issues=tuple(unique_issues),
    )


def _receipt(
    *,
    tenant_id: str,
    project_id: str,
    snapshot: PortfolioSnapshotRef | None,
    contract: ModelConsumptionContract | None,
    mapping: PortfolioModelMapping | None,
    input_contract: OptimizationInputContract | None,
    created_at: datetime,
    status: OptimizationReadinessStatus,
    checks: tuple[OptimizationReadinessCheck, ...],
    issues: tuple[OptimizationIssue, ...],
) -> OptimizationReadinessReceipt:
    portfolio_fp = None if snapshot is None else snapshot.fingerprint
    model_fp = None if contract is None else contract.fingerprint
    mapping_fp = None if mapping is None else mapping.fingerprint
    input_fp = None if input_contract is None else input_contract.fingerprint
    consumption_fp = None if contract is None else contract.model_consumption_contract_fingerprint
    fingerprint = metadata_fingerprint(
        {
            "status": status.value,
            "checks": [(item.code.value, item.passed) for item in checks],
            "issues": [issue.code.value for issue in issues],
            "portfolio_fingerprint": portfolio_fp,
            "model_fingerprint": model_fp,
            "mapping_fingerprint": mapping_fp,
            "input_contract_fingerprint": input_fp,
            "model_consumption_contract_fingerprint": consumption_fp,
            "policy_version": POLICY_VERSION,
        }
    )
    return OptimizationReadinessReceipt(
        receipt_id=new_readiness_receipt_id(),
        tenant_id=tenant_id,
        project_id=project_id,
        portfolio_snapshot_id=None if snapshot is None else snapshot.snapshot_id,
        model_version_id=None if contract is None else contract.model_version_id,
        mapping_id=None if mapping is None else mapping.mapping_id,
        optimization_input_id=(
            None if input_contract is None else input_contract.optimization_input_id
        ),
        status=status,
        checks=checks,
        issues=issues,
        portfolio_fingerprint=portfolio_fp,
        model_fingerprint=model_fp,
        mapping_fingerprint=mapping_fp,
        input_contract_fingerprint=input_fp,
        model_consumption_contract_fingerprint=consumption_fp,
        policy_version=POLICY_VERSION,
        created_at=created_at,
        fingerprint=fingerprint,
    )


def receipt_is_stale(
    receipt: OptimizationReadinessReceipt,
    *,
    portfolio_fingerprint: str | None,
    model_fingerprint: str | None,
    mapping_fingerprint: str | None,
) -> bool:
    if receipt.status is OptimizationReadinessStatus.STALE:
        return True
    if portfolio_fingerprint and receipt.portfolio_fingerprint != portfolio_fingerprint:
        return True
    if model_fingerprint and receipt.model_fingerprint != model_fingerprint:
        return True
    if mapping_fingerprint and receipt.mapping_fingerprint != mapping_fingerprint:
        return True
    return False
