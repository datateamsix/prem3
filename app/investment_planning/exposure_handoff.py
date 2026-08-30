"""P6-06 proposal limitations and P6-09 exposure-risk handoff. No approval."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from app.investment_optimization.enums import ProposalLimitationCode
from app.investment_planning.contracts import FrozenModel
from app.investment_planning.enums import SensitiveDataClass
from app.investment_planning.exposure_guardrails import ExposureGuardrailQualificationReceipt
from app.investment_planning.exposure_profile import PortfolioExposureRiskProfile
from app.investment_planning.exposure_scenarios import ExposureRiskScenario
from app.investment_planning.fingerprint import metadata_fingerprint
from app.investment_planning.ids import new_exposure_handoff_id

EXPOSURE_PROPOSAL_LIMITATION = ProposalLimitationCode.EXPOSURE_RISK_FLAGS_PRESENT


class ExposureRiskHandoff(FrozenModel):
    """P6-09 input. P6-08 does not price downside risk."""

    sensitive_data_class: ClassVar[SensitiveDataClass] = SensitiveDataClass.CONTROL_PLANE_METADATA
    handoff_id: str
    project_id: str
    period: str
    exposure_risk_evidence_refs: tuple[str, ...]
    qualified_guardrail_ids: tuple[str, ...]
    scenario_ids: tuple[str, ...]
    coverage_fingerprint: str
    freshness: str
    risk_flags: tuple[str, ...]
    portfolio_entity_mapping: tuple[str, ...]
    limitations: tuple[str, ...]
    fingerprint: str
    created_at: datetime


def proposal_exposure_limitations(
    profile: PortfolioExposureRiskProfile,
) -> tuple[ProposalLimitationCode, ...]:
    if not profile.risk_flags:
        return ()
    return (EXPOSURE_PROPOSAL_LIMITATION,)


def compile_p6_09_handoff(
    *,
    profile: PortfolioExposureRiskProfile,
    qualifications: tuple[ExposureGuardrailQualificationReceipt, ...],
    scenarios: tuple[ExposureRiskScenario, ...],
    created_at: datetime,
) -> ExposureRiskHandoff:
    qualified = tuple(
        item.guardrail_id
        for item in qualifications
        if item.role_supported
    )
    entity_mapping = tuple(
        ref for ref in (profile.market_id, profile.channel_id, profile.campaign_id) if ref
    )
    handoff_id = new_exposure_handoff_id()
    flags = tuple(flag.value for flag in profile.risk_flags)
    fingerprint = metadata_fingerprint(
        {
            "handoff_id": handoff_id,
            "evidence": profile.metric_evidence_refs,
            "guardrails": qualified,
            "scenarios": tuple(item.scenario_id for item in scenarios),
            "coverage": profile.coverage.fingerprint,
            "flags": flags,
        }
    )
    return ExposureRiskHandoff(
        handoff_id=handoff_id,
        project_id=profile.project_id,
        period=profile.period,
        exposure_risk_evidence_refs=profile.metric_evidence_refs,
        qualified_guardrail_ids=qualified,
        scenario_ids=tuple(item.scenario_id for item in scenarios),
        coverage_fingerprint=profile.coverage.fingerprint,
        freshness=profile.coverage.items[-1].status.value if profile.coverage.items else "MISSING",
        risk_flags=flags,
        portfolio_entity_mapping=entity_mapping,
        limitations=profile.limitations,
        fingerprint=fingerprint,
        created_at=created_at,
    )
