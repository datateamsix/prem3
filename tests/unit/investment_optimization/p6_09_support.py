"""P6-09 test fixtures."""

from __future__ import annotations

from app.investment_optimization.risk.models import CandidateShare
from app.investment_optimization.risk.policies import pin_risk_policy
from app.investment_optimization.risk.service import RiskFrontierService
from app.investment_optimization.store import InMemoryOptimizationMetadataStore

TENANT = "ten_p609"
PROJECT = "ws_p609"
RUN = "orun_native_p609"
PLAN = "plan_approved_p609"
MODEL = "mmv_accepted_p609"
READY = "oready_p609"

NATIVE_SHARES = (
    CandidateShare(channel_id="search", share=0.50),
    CandidateShare(channel_id="social", share=0.30),
    CandidateShare(channel_id="video", share=0.20),
)

BASELINE_SHARES = (
    CandidateShare(channel_id="search", share=0.40),
    CandidateShare(channel_id="social", share=0.40),
    CandidateShare(channel_id="video", share=0.20),
)


def risk_service() -> RiskFrontierService:
    return RiskFrontierService(InMemoryOptimizationMetadataStore())


def risk_neutral_policy(*, tenant_id: str = TENANT, project_id: str = PROJECT):
    return pin_risk_policy(
        tenant_id=tenant_id,
        project_id=project_id,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=False,
        minimum_candidate_count=3,
    )


def penalized_policy(*, tenant_id: str = TENANT, project_id: str = PROJECT):
    return pin_risk_policy(
        tenant_id=tenant_id,
        project_id=project_id,
        objective="MAX_EXPECTED_OUTCOME_FIXED_BUDGET",
        model_version_ref=MODEL,
        optimization_readiness_ref=READY,
        risk_penalties_enabled=True,
        minimum_candidate_count=3,
        conservative_expected_floor_ratio=0.85,
    )


def draw_set(kind: str) -> tuple[float, ...]:
    if kind == "high":
        return (12.0, 11.0, 13.0, 12.5, 11.5)
    if kind == "balanced":
        return (10.5, 10.0, 10.8, 10.2, 10.4)
    if kind == "safe":
        return (9.8, 9.7, 9.9, 9.8, 9.85)
    return (10.0, 10.0, 10.0, 10.0, 10.0)
