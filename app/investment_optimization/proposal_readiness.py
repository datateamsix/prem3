"""Proposal readiness is distinct from P6-04 optimizer readiness."""

from __future__ import annotations

from datetime import UTC, datetime

from app.investment_optimization.accepted_model import is_accepted_model
from app.investment_optimization.contracts import (
    DEFAULT_PROPOSAL_APPROVAL_POLICY,
    OptimizationProposal,
    OptimizationRun,
    ProposalReadinessCheck,
    ProposalReadinessReceipt,
    ScenarioArtifact,
)
from app.investment_optimization.enums import (
    DEFAULT_PROPOSAL_LIMITATIONS,
    GOVERNANCE_POLICY_VERSION,
    OptimizationRunStatus,
    ProposalReadinessCheckCode,
    ProposalReadinessStatus,
    ScenarioStatus,
)
from app.investment_optimization.ids import new_proposal_readiness_receipt_id
from app.investment_planning.fingerprint import (
    investment_plan_fingerprint,
    metadata_fingerprint,
)
from app.modeling.mmm.contracts import MMMModelVersion


def evaluate_proposal_readiness(
    *,
    proposal: OptimizationProposal,
    scenario: ScenarioArtifact | None,
    run: OptimizationRun | None,
    version: MMMModelVersion | None,
    source_plan_id: str | None,
    source_plan_revision: int | None,
    source_plan_status: str | None,
    result_readback_ok: bool,
) -> ProposalReadinessReceipt:
    checks = (
        ProposalReadinessCheck(
            code=ProposalReadinessCheckCode.SCENARIO_AVAILABLE,
            passed=scenario is not None
            and scenario.status is ScenarioStatus.AVAILABLE
            and scenario.scenario_id == proposal.scenario_id,
        ),
        ProposalReadinessCheck(
            code=ProposalReadinessCheckCode.SOURCE_PLAN_MATCH,
            passed=(
                source_plan_id == proposal.source_plan_id
                and source_plan_revision == proposal.source_plan_revision
                and source_plan_status == "APPROVED"
                and source_plan_id is not None
                and investment_plan_fingerprint(
                    plan_id=proposal.source_plan_id,
                    project_id=proposal.project_id,
                    revision=proposal.source_plan_revision,
                    status="APPROVED",
                )
                == proposal.source_plan_fingerprint
            ),
        ),
        ProposalReadinessCheck(
            code=ProposalReadinessCheckCode.OPTIMIZATION_RESULT_COMPLETE,
            passed=run is not None
            and run.status is OptimizationRunStatus.COMPLETE
            and run.optimization_run_id == proposal.optimization_run_id,
        ),
        ProposalReadinessCheck(
            code=ProposalReadinessCheckCode.MODEL_ACCEPTED,
            passed=version is not None
            and is_accepted_model(version)
            and version.model_version_id == proposal.model_version_id,
        ),
        ProposalReadinessCheck(
            code=ProposalReadinessCheckCode.RESULT_ARTIFACT_READBACK_VALID,
            passed=result_readback_ok,
        ),
        ProposalReadinessCheck(
            code=ProposalReadinessCheckCode.PROPOSAL_POLICY_VALID,
            passed=proposal.policy_version == GOVERNANCE_POLICY_VERSION
            and DEFAULT_PROPOSAL_APPROVAL_POLICY.requires_distinct_plan_approval,
        ),
        ProposalReadinessCheck(
            code=ProposalReadinessCheckCode.NO_STALE_AUTHORITY,
            passed=True,
        ),
    )
    failed = tuple(item for item in checks if not item.passed)
    source_failed = any(
        item.code is ProposalReadinessCheckCode.SOURCE_PLAN_MATCH and not item.passed
        for item in checks
    )
    model_failed = any(
        item.code is ProposalReadinessCheckCode.MODEL_ACCEPTED and not item.passed
        for item in checks
    )
    if source_failed:
        status = ProposalReadinessStatus.STALE
    elif model_failed:
        status = ProposalReadinessStatus.REVIEW_REQUIRED
    elif failed:
        status = ProposalReadinessStatus.NOT_READY
    else:
        status = ProposalReadinessStatus.PROPOSAL_READY
    now = datetime.now(UTC)
    body = {
        "proposal_id": proposal.proposal_id,
        "status": status.value,
        "checks": tuple((item.code.value, item.passed) for item in checks),
    }
    return ProposalReadinessReceipt(
        receipt_id=new_proposal_readiness_receipt_id(),
        proposal_id=proposal.proposal_id,
        tenant_id=proposal.tenant_id,
        project_id=proposal.project_id,
        status=status,
        checks=checks,
        limitation_codes=DEFAULT_PROPOSAL_LIMITATIONS,
        created_at=now,
        fingerprint=metadata_fingerprint(body),
    )
