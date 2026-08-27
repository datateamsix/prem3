"""Create a new Investment Plan draft from an approved proposal. Does not approve."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Protocol

from openpyxl import Workbook

from app.investment_optimization.authority import require_new_plan_version_on_approval
from app.investment_optimization.contracts import (
    OptimizationProposal,
    OptimizationResultPayload,
    ScenarioArtifact,
)
from app.investment_optimization.enums import (
    ModelVariableOptimizationEligibility,
    OptimizationProposalLifecycleStatus,
)
from app.investment_optimization.errors import (
    ProposalNotApprovedError,
    ProposalSourcePlanStaleError,
)
from app.investment_planning.contracts import InvestmentPlan, PortfolioView
from app.investment_planning.drive_binding import XLSX_MIME
from app.investment_planning.enums import AmountKind, InvestmentPlanStatus
from app.investment_planning.fingerprint import investment_plan_fingerprint
from app.investment_planning.template import TEMPLATE_HEADERS


class PlanningRevisionHost(Protocol):
    def get_plan(self, *, plan_id: str, project_id: str) -> InvestmentPlan: ...

    def revise(
        self,
        *,
        plan_id: str,
        project_id: str,
        actor_id: str,
        source_proposal_id: str | None = None,
        source_decision_receipt_id: str | None = None,
        source_scenario_id: str | None = None,
    ) -> InvestmentPlan: ...

    def ingest_bytes(
        self,
        *,
        plan_id: str,
        project_id: str,
        file_name: str,
        mime_type: str,
        data: bytes,
        actor_id: str,
    ) -> object: ...

    def assemble_portfolio(
        self, *, project_id: str, fiscal_year: int | None, actor_id: str
    ) -> tuple[object, object, PortfolioView]: ...


def compile_revision_workbook(
    *,
    view: PortfolioView,
    payload: OptimizationResultPayload,
) -> bytes:
    recommended = {
        (row.market_id, row.channel_id): row.recommended
        for row in payload.rows
        if row.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE
    }
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Investment Plan"
    sheet.append(list(TEMPLATE_HEADERS))
    grouped: dict[tuple[str, str], dict[int, Decimal]] = {}
    names: dict[str, str] = {}
    for allocation in view.allocations:
        key = (allocation.market_id, allocation.channel_id)
        names[allocation.market_id] = allocation.market_id
        quarter_map = grouped.setdefault(
            key, {1: Decimal("0"), 2: Decimal("0"), 3: Decimal("0"), 4: Decimal("0")}
        )
        amount = Decimal("0")
        for money in allocation.amounts:
            if money.kind is AmountKind.APPROVED and money.value is not None:
                amount = money.value
                break
        if key in recommended and allocation.quarter:
            quarter_map[allocation.quarter] = recommended[key]
        else:
            quarter_map[allocation.quarter] = amount
    for (market_id, channel_id), quarters in sorted(grouped.items()):
        sheet.append(
            [
                market_id,
                names.get(market_id, market_id),
                channel_id,
                format(quarters.get(1, Decimal("0")), "f"),
                format(quarters.get(2, Decimal("0")), "f"),
                format(quarters.get(3, Decimal("0")), "f"),
                format(quarters.get(4, Decimal("0")), "f"),
                "PLANNED",
                "source_proposal",
            ]
        )
    payload_io = BytesIO()
    workbook.save(payload_io)
    return payload_io.getvalue()


def create_plan_revision(
    *,
    planning: PlanningRevisionHost,
    proposal: OptimizationProposal,
    scenario: ScenarioArtifact,
    payload: OptimizationResultPayload,
    actor_id: str,
) -> InvestmentPlan:
    if proposal.status is not OptimizationProposalLifecycleStatus.APPROVED:
        raise ProposalNotApprovedError("Unapproved proposals cannot create a plan revision.")
    require_new_plan_version_on_approval(
        current_status=proposal.status,
        actor_id=actor_id,
    )
    source = planning.get_plan(plan_id=proposal.source_plan_id, project_id=proposal.project_id)
    expected = investment_plan_fingerprint(
        plan_id=source.plan_id,
        project_id=source.project_id,
        revision=source.revision,
        status=source.status.value,
    )
    if (
        source.status is not InvestmentPlanStatus.APPROVED
        or source.revision != proposal.source_plan_revision
        or expected != proposal.source_plan_fingerprint
    ):
        raise ProposalSourcePlanStaleError(
            "Source approved plan changed; rebase with a new proposal."
        )
    if scenario.scenario_id != proposal.scenario_id:
        raise ProposalSourcePlanStaleError("Scenario artifact does not match the proposal.")
    coverage, snapshot, view = planning.assemble_portfolio(
        project_id=proposal.project_id,
        fiscal_year=None,
        actor_id=actor_id,
    )
    del coverage, snapshot
    draft = planning.revise(
        plan_id=source.plan_id,
        project_id=proposal.project_id,
        actor_id=actor_id,
        source_proposal_id=proposal.proposal_id,
        source_decision_receipt_id=proposal.decision_receipt_id,
        source_scenario_id=scenario.scenario_id,
    )
    data = compile_revision_workbook(view=view, payload=payload)
    planning.ingest_bytes(
        plan_id=draft.plan_id,
        project_id=proposal.project_id,
        file_name=f"{draft.plan_id}_proposal.xlsx",
        mime_type=XLSX_MIME,
        data=data,
        actor_id=actor_id,
    )
    return draft
