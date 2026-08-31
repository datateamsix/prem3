"""Firestore metadata store for optimization readiness. Amounts never persist."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from app.control_plane.serialization import (
    SCHEMA_VERSION,
    ControlPlaneDocumentError,
    _normalize_inbound,
    _normalize_outbound,
)
from app.investment_optimization.contracts import (
    AdvancedOptimizationReadinessReceipt,
    ConstraintSetRef,
    ModelConsumptionContract,
    OptimizationEvidenceCoverage,
    OptimizationInputContract,
    OptimizationProposal,
    OptimizationReadinessReceipt,
    OptimizationResultRef,
    OptimizationRun,
    PlanningDecisionRecord,
    PortfolioModelMapping,
    ProposalDecisionReceipt,
    ProposalReadinessReceipt,
    ScenarioArtifact,
    ScenarioAssumptionSetRef,
)
from app.investment_optimization.risk.models import (
    CandidatePortfolio,
    FrontierSelection,
    MarketingInvestmentFrontier,
    PortfolioRiskEvaluation,
    RiskEvaluationPolicy,
    RiskNeutralParityReceipt,
)
from app.investment_optimization.simulation.models import (
    MonteCarloSimulationPolicy,
    MonteCarloSimulationReceipt,
    PortfolioOutcomeDistribution,
    ScenarioCorrelationSpec,
    ScenarioDistributionSet,
    SimulationEvidenceHandoff,
    SimulationRun,
    SimulationRunSpec,
)
from app.investment_optimization.store import (
    OptimizationMetadata,
    assert_optimization_metadata_only,
)
from app.investment_planning.errors import PersistenceBarrierError
from app.investment_planning.outcomes.models import (
    DecisionOutcomeLearningReceipt,
    DecisionOutcomeObservation,
    ExecutionAdherence,
    InvestmentDecisionRecord,
    PredictionErrorSummary,
    PredictionEvidenceSet,
    RecommendationAdherence,
    RecommendationOutcomeReceipt,
)

COLLECTION_TENANTS = "tenants"
COLLECTION_WORKSPACES = "workspaces"
COL_MAPPINGS = "portfolio_model_mappings"
COL_INPUTS = "optimization_input_contracts"
COL_RECEIPTS = "optimization_readiness_receipts"
COL_COVERAGE = "optimization_evidence_coverage"
COL_CONTRACTS = "model_consumption_contracts"
COL_RUNS = "optimization_runs"
COL_RESULTS = "optimization_result_refs"
COL_SCENARIOS = "scenario_artifacts"
COL_PROPOSALS = "optimization_proposals"
COL_PROPOSAL_READY = "proposal_readiness_receipts"
COL_DECISIONS = "proposal_decision_receipts"
COL_DECISION_RECORDS = "planning_decision_records"
COL_CONSTRAINT_REFS = "optimization_constraint_set_refs"
COL_ASSUMPTION_REFS = "optimization_assumption_set_refs"
COL_ADVANCED_RECEIPTS = "advanced_optimization_readiness_receipts"
COL_RISK_POLICIES = "risk_evaluation_policies"
COL_CANDIDATES = "candidate_portfolios"
COL_EVALUATIONS = "portfolio_risk_evaluations"
COL_FRONTIERS = "marketing_investment_frontiers"
COL_SELECTIONS = "frontier_selections"
COL_PARITY = "risk_neutral_parity_receipts"
COL_DIST_SETS = "scenario_distribution_sets"
COL_CORRELATIONS = "scenario_correlation_specs"
COL_SIM_POLICIES = "monte_carlo_simulation_policies"
COL_RUN_SPECS = "simulation_run_specs"
COL_SIM_RUNS = "simulation_runs"
COL_OUTCOME_DISTS = "portfolio_outcome_distributions"
COL_SIM_RECEIPTS = "monte_carlo_simulation_receipts"
COL_HANDOFFS = "simulation_evidence_handoffs"
COL_INV_DECISIONS = "investment_decision_records"
COL_REC_ADHERENCE = "recommendation_adherence"
COL_EXEC_ADHERENCE = "execution_adherence"
COL_OBSERVATIONS = "decision_outcome_observations"
COL_PRED_EVIDENCE = "prediction_evidence_sets"
COL_PRED_ERRORS = "prediction_error_summaries"
COL_OUTCOME_RECEIPTS = "recommendation_outcome_receipts"
COL_LEARNING = "decision_outcome_learning_receipts"
COL_INDEX = "investment_optimization_index"


def _to_document(model: BaseModel) -> dict[str, Any]:
    payload = _normalize_outbound(model.model_dump(mode="python"))
    payload["schema_version"] = SCHEMA_VERSION
    return payload


def _from_document[T: BaseModel](model_type: type[T], data: dict[str, Any] | None) -> T:
    if data is None:
        raise ControlPlaneDocumentError(f"Missing document for {model_type.__name__}.")
    if not isinstance(data, dict):
        raise ControlPlaneDocumentError(f"Malformed document for {model_type.__name__}.")
    cleaned = dict(data)
    cleaned.pop("schema_version", None)
    try:
        return model_type.model_validate(_normalize_inbound(cleaned))
    except ValidationError as exc:
        raise ControlPlaneDocumentError(
            f"Rejected malformed {model_type.__name__} document."
        ) from exc


class FirestoreOptimizationMetadataStore:
    def __init__(self, client: Any) -> None:
        self._db = client

    def _workspace(self, tenant_id: str, workspace_id: str):
        return (
            self._db.collection(COLLECTION_TENANTS)
            .document(tenant_id)
            .collection(COLLECTION_WORKSPACES)
            .document(workspace_id)
        )

    def _index(self, kind: str, resource_id: str):
        return self._db.collection(COL_INDEX).document(f"{kind}__{resource_id}")

    def _put_index(
        self,
        *,
        kind: str,
        resource_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> None:
        self._index(kind, resource_id).set({"tenant_id": tenant_id, "workspace_id": workspace_id})

    def _put_lookup(
        self,
        *,
        kind: str,
        key: str,
        resource_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> None:
        self._index(kind, key).set(
            {
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "resource_id": resource_id,
            }
        )

    def _load[T: BaseModel](
        self,
        model_type: type[T],
        *,
        kind: str,
        resource_id: str,
        collection: str,
    ) -> T | None:
        snap = self._index(kind, resource_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        doc = (
            self._workspace(str(data["tenant_id"]), str(data["workspace_id"]))
            .collection(collection)
            .document(resource_id)
            .get()
        )
        if not doc.exists:
            return None
        return _from_document(model_type, doc.to_dict())

    def put(self, value: OptimizationMetadata) -> OptimizationMetadata:
        safe = assert_optimization_metadata_only(value)
        if isinstance(safe, PortfolioModelMapping):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_MAPPINGS).document(
                safe.mapping_id
            ).set(_to_document(safe))
            self._put_index(
                kind="mapping",
                resource_id=safe.mapping_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationInputContract):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_INPUTS).document(
                safe.optimization_input_id
            ).set(_to_document(safe))
            self._put_index(
                kind="input",
                resource_id=safe.optimization_input_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationReadinessReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RECEIPTS).document(
                safe.receipt_id
            ).set(_to_document(safe))
            self._put_index(
                kind="receipt",
                resource_id=safe.receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationEvidenceCoverage):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_COVERAGE).document(
                safe.coverage_id
            ).set(_to_document(safe))
            self._put_index(
                kind="coverage",
                resource_id=safe.coverage_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ModelConsumptionContract):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_CONTRACTS).document(
                safe.consumption_contract_id
            ).set(_to_document(safe))
            self._put_index(
                kind="consumption",
                resource_id=safe.consumption_contract_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationRun):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RUNS).document(
                safe.optimization_run_id
            ).set(_to_document(safe))
            self._put_index(
                kind="run",
                resource_id=safe.optimization_run_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationResultRef):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RESULTS).document(
                safe.result_id
            ).set(_to_document(safe))
            self._put_index(
                kind="result",
                resource_id=safe.result_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ScenarioArtifact):
            existing = self.get_scenario(safe.scenario_id)
            if existing is not None:
                raise PersistenceBarrierError(
                    "ScenarioArtifact is immutable after publish.",
                    code="SCENARIO_IMMUTABLE",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_SCENARIOS).document(
                safe.scenario_id
            ).set(_to_document(safe))
            self._put_index(
                kind="scenario",
                resource_id=safe.scenario_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, OptimizationProposal):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_PROPOSALS).document(
                safe.proposal_id
            ).set(_to_document(safe))
            self._put_index(
                kind="proposal",
                resource_id=safe.proposal_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ProposalReadinessReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_PROPOSAL_READY
            ).document(safe.receipt_id).set(_to_document(safe))
            self._put_index(
                kind="proposal_readiness",
                resource_id=safe.receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ProposalDecisionReceipt):
            if self.get_decision_receipt(safe.decision_receipt_id) is not None:
                raise PersistenceBarrierError(
                    "ProposalDecisionReceipt is immutable.",
                    code="DECISION_RECEIPT_IMMUTABLE",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_DECISIONS).document(
                safe.decision_receipt_id
            ).set(_to_document(safe))
            self._put_index(
                kind="decision",
                resource_id=safe.decision_receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, PlanningDecisionRecord):
            if self.get_decision_record(safe.decision_id) is not None:
                raise PersistenceBarrierError(
                    "PlanningDecisionRecord is immutable.",
                    code="DECISION_RECEIPT_IMMUTABLE",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_DECISION_RECORDS
            ).document(safe.decision_id).set(_to_document(safe))
            self._put_index(
                kind="decision_record",
                resource_id=safe.decision_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ConstraintSetRef):
            if not safe.tenant_id or not safe.project_id:
                raise PersistenceBarrierError(
                    "ConstraintSetRef requires tenant and project identity.",
                    code="PLANNING_PERSISTENCE_BARRIER",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_CONSTRAINT_REFS
            ).document(safe.constraint_set_id).set(_to_document(safe))
            self._put_index(
                kind="constraint_ref",
                resource_id=safe.constraint_set_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ScenarioAssumptionSetRef):
            if not safe.tenant_id or not safe.project_id:
                raise PersistenceBarrierError(
                    "ScenarioAssumptionSetRef requires tenant and project identity.",
                    code="PLANNING_PERSISTENCE_BARRIER",
                )
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_ASSUMPTION_REFS
            ).document(safe.assumption_set_id).set(_to_document(safe))
            self._put_index(
                kind="assumption_ref",
                resource_id=safe.assumption_set_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, AdvancedOptimizationReadinessReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_ADVANCED_RECEIPTS
            ).document(safe.receipt_id).set(_to_document(safe))
            self._put_index(
                kind="advanced_receipt",
                resource_id=safe.receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, RiskEvaluationPolicy):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RISK_POLICIES).document(
                safe.risk_evaluation_policy_id
            ).set(_to_document(safe))
            self._put_index(
                kind="risk_policy",
                resource_id=safe.risk_evaluation_policy_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, CandidatePortfolio):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_CANDIDATES).document(
                safe.candidate_portfolio_id
            ).set(_to_document(safe))
            self._put_index(
                kind="candidate",
                resource_id=safe.candidate_portfolio_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, PortfolioRiskEvaluation):
            policy = self.get_risk_policy(safe.risk_evaluation_policy_ref)
            if policy is None:
                raise PersistenceBarrierError(
                    "PortfolioRiskEvaluation requires a stored policy.",
                    code="PLANNING_PERSISTENCE_BARRIER",
                )
            self._workspace(policy.tenant_id, policy.project_id).collection(
                COL_EVALUATIONS
            ).document(safe.portfolio_risk_evaluation_id).set(_to_document(safe))
            self._put_index(
                kind="risk_evaluation",
                resource_id=safe.portfolio_risk_evaluation_id,
                tenant_id=policy.tenant_id,
                workspace_id=policy.project_id,
            )
            self._put_lookup(
                kind="risk_evaluation_candidate",
                key=safe.candidate_portfolio_id,
                resource_id=safe.portfolio_risk_evaluation_id,
                tenant_id=policy.tenant_id,
                workspace_id=policy.project_id,
            )
            self._put_lookup(
                kind="risk_evaluation_fp",
                key=safe.evaluation_fingerprint,
                resource_id=safe.portfolio_risk_evaluation_id,
                tenant_id=policy.tenant_id,
                workspace_id=policy.project_id,
            )
        elif isinstance(safe, MarketingInvestmentFrontier):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_FRONTIERS).document(
                safe.frontier_id
            ).set(_to_document(safe))
            self._put_index(
                kind="frontier",
                resource_id=safe.frontier_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="frontier_fp",
                key=safe.fingerprint,
                resource_id=safe.frontier_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, FrontierSelection):
            frontier = self.get_frontier(safe.frontier_id)
            if frontier is None:
                raise PersistenceBarrierError(
                    "FrontierSelection requires a stored frontier.",
                    code="PLANNING_PERSISTENCE_BARRIER",
                )
            self._workspace(frontier.tenant_id, frontier.project_id).collection(
                COL_SELECTIONS
            ).document(safe.selection_id).set(_to_document(safe))
            self._put_index(
                kind="frontier_selection",
                resource_id=safe.selection_id,
                tenant_id=frontier.tenant_id,
                workspace_id=frontier.project_id,
            )
            self._put_lookup(
                kind="selection_fp",
                key=safe.selection_fingerprint,
                resource_id=safe.selection_id,
                tenant_id=frontier.tenant_id,
                workspace_id=frontier.project_id,
            )
        elif isinstance(safe, RiskNeutralParityReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_PARITY).document(
                safe.parity_receipt_id
            ).set(_to_document(safe))
            self._put_index(
                kind="parity",
                resource_id=safe.parity_receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ScenarioDistributionSet):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_DIST_SETS).document(
                safe.scenario_distribution_set_id
            ).set(_to_document(safe))
            self._put_index(
                kind="dist_set",
                resource_id=safe.scenario_distribution_set_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ScenarioCorrelationSpec):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_CORRELATIONS).document(
                safe.correlation_spec_id
            ).set(_to_document(safe))
            self._put_index(
                kind="correlation",
                resource_id=safe.correlation_spec_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="correlation_fp",
                key=safe.fingerprint,
                resource_id=safe.correlation_spec_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, MonteCarloSimulationPolicy):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_SIM_POLICIES).document(
                safe.policy_id
            ).set(_to_document(safe))
            self._put_index(
                kind="sim_policy",
                resource_id=safe.policy_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="sim_policy_fp",
                key=safe.fingerprint,
                resource_id=safe.policy_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, SimulationRunSpec):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_RUN_SPECS).document(
                safe.simulation_run_spec_id
            ).set(_to_document(safe))
            self._put_index(
                kind="run_spec",
                resource_id=safe.simulation_run_spec_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="run_spec_fp",
                key=safe.input_fingerprint,
                resource_id=safe.simulation_run_spec_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, SimulationRun):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_SIM_RUNS).document(
                safe.simulation_run_id
            ).set(_to_document(safe))
            self._put_index(
                kind="sim_run",
                resource_id=safe.simulation_run_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="sim_run_fp",
                key=safe.input_fingerprint,
                resource_id=safe.simulation_run_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, PortfolioOutcomeDistribution):
            run = self.get_simulation_run(safe.simulation_run_id)
            if run is None:
                raise PersistenceBarrierError(
                    "PortfolioOutcomeDistribution requires a stored simulation run.",
                    code="PLANNING_PERSISTENCE_BARRIER",
                )
            self._workspace(run.tenant_id, run.project_id).collection(COL_OUTCOME_DISTS).document(
                safe.portfolio_outcome_distribution_id
            ).set(_to_document(safe))
            self._put_index(
                kind="outcome_dist",
                resource_id=safe.portfolio_outcome_distribution_id,
                tenant_id=run.tenant_id,
                workspace_id=run.project_id,
            )
        elif isinstance(safe, MonteCarloSimulationReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_SIM_RECEIPTS).document(
                safe.receipt_id
            ).set(_to_document(safe))
            self._put_index(
                kind="sim_receipt",
                resource_id=safe.receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, SimulationEvidenceHandoff):
            run = self.get_simulation_run(safe.simulation_run_id)
            if run is None:
                raise PersistenceBarrierError(
                    "SimulationEvidenceHandoff requires a stored simulation run.",
                    code="PLANNING_PERSISTENCE_BARRIER",
                )
            self._workspace(run.tenant_id, run.project_id).collection(COL_HANDOFFS).document(
                safe.simulation_evidence_handoff_id
            ).set(_to_document(safe))
            self._put_index(
                kind="sim_handoff",
                resource_id=safe.simulation_evidence_handoff_id,
                tenant_id=run.tenant_id,
                workspace_id=run.project_id,
            )
        elif isinstance(safe, InvestmentDecisionRecord):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_INV_DECISIONS).document(
                safe.investment_decision_id
            ).set(_to_document(safe))
            self._put_index(
                kind="inv_decision",
                resource_id=safe.investment_decision_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="inv_decision_fp",
                key=safe.decision_fingerprint,
                resource_id=safe.investment_decision_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, RecommendationAdherence):
            self._workspace(safe.tenant_id, safe.project_id).collection(COL_REC_ADHERENCE).document(
                safe.recommendation_adherence_id
            ).set(_to_document(safe))
            self._put_index(
                kind="rec_adh",
                resource_id=safe.recommendation_adherence_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="rec_adh_fp",
                key=safe.fingerprint,
                resource_id=safe.recommendation_adherence_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, ExecutionAdherence):
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_EXEC_ADHERENCE
            ).document(safe.execution_adherence_id).set(_to_document(safe))
            self._put_index(
                kind="exec_adh",
                resource_id=safe.execution_adherence_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="exec_adh_fp",
                key=safe.fingerprint,
                resource_id=safe.execution_adherence_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, DecisionOutcomeObservation):
            self._workspace(safe.project_id, safe.project_id).collection(COL_OBSERVATIONS).document(
                safe.decision_outcome_observation_id
            ).set(_to_document(safe))
            self._put_index(
                kind="outcome_obs",
                resource_id=safe.decision_outcome_observation_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="outcome_obs_fp",
                key=safe.observation_fingerprint,
                resource_id=safe.decision_outcome_observation_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, PredictionEvidenceSet):
            self._workspace(safe.project_id, safe.project_id).collection(
                COL_PRED_EVIDENCE
            ).document(safe.prediction_evidence_id).set(_to_document(safe))
            self._put_index(
                kind="pred_ev",
                resource_id=safe.prediction_evidence_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="pred_ev_fp",
                key=safe.fingerprint,
                resource_id=safe.prediction_evidence_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, PredictionErrorSummary):
            self._workspace(safe.project_id, safe.project_id).collection(COL_PRED_ERRORS).document(
                safe.prediction_error_id
            ).set(_to_document(safe))
            self._put_index(
                kind="pred_err",
                resource_id=safe.prediction_error_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="pred_err_fp",
                key=safe.fingerprint,
                resource_id=safe.prediction_error_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, RecommendationOutcomeReceipt):
            self._workspace(safe.tenant_id, safe.project_id).collection(
                COL_OUTCOME_RECEIPTS
            ).document(safe.recommendation_outcome_receipt_id).set(_to_document(safe))
            self._put_index(
                kind="out_rcp",
                resource_id=safe.recommendation_outcome_receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="out_rcp_fp",
                key=safe.receipt_fingerprint,
                resource_id=safe.recommendation_outcome_receipt_id,
                tenant_id=safe.tenant_id,
                workspace_id=safe.project_id,
            )
        elif isinstance(safe, DecisionOutcomeLearningReceipt):
            self._workspace(safe.project_id, safe.project_id).collection(COL_LEARNING).document(
                safe.learning_receipt_id
            ).set(_to_document(safe))
            self._put_index(
                kind="learn_rcp",
                resource_id=safe.learning_receipt_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
            self._put_lookup(
                kind="learn_rcp_fp",
                key=safe.fingerprint,
                resource_id=safe.learning_receipt_id,
                tenant_id=safe.project_id,
                workspace_id=safe.project_id,
            )
        else:
            raise PersistenceBarrierError(
                f"{type(safe).__name__} is not a P6-04/P6-06 persistence contract.",
                code="PLANNING_PERSISTENCE_BARRIER",
            )
        return safe

    def get_mapping(self, mapping_id: str) -> PortfolioModelMapping | None:
        return self._load(
            PortfolioModelMapping, kind="mapping", resource_id=mapping_id, collection=COL_MAPPINGS
        )

    def list_mappings(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[PortfolioModelMapping, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_MAPPINGS).stream()
        return tuple(_from_document(PortfolioModelMapping, doc.to_dict()) for doc in docs)

    def latest_mapping(self, *, tenant_id: str, project_id: str) -> PortfolioModelMapping | None:
        matches = self.list_mappings(tenant_id=tenant_id, project_id=project_id)
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_receipt(self, receipt_id: str) -> OptimizationReadinessReceipt | None:
        return self._load(
            OptimizationReadinessReceipt,
            kind="receipt",
            resource_id=receipt_id,
            collection=COL_RECEIPTS,
        )

    def latest_receipt(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationReadinessReceipt | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_RECEIPTS).stream()
        matches = [_from_document(OptimizationReadinessReceipt, doc.to_dict()) for doc in docs]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_input_contract(self, optimization_input_id: str) -> OptimizationInputContract | None:
        return self._load(
            OptimizationInputContract,
            kind="input",
            resource_id=optimization_input_id,
            collection=COL_INPUTS,
        )

    def get_coverage(self, coverage_id: str) -> OptimizationEvidenceCoverage | None:
        return self._load(
            OptimizationEvidenceCoverage,
            kind="coverage",
            resource_id=coverage_id,
            collection=COL_COVERAGE,
        )

    def get_consumption_for_model(
        self, *, tenant_id: str, project_id: str, model_version_id: str
    ) -> ModelConsumptionContract | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_CONTRACTS).stream()
        matches = [
            _from_document(ModelConsumptionContract, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("model_version_id") == model_version_id
        ]
        if not matches:
            return None
        return matches[-1]

    def get_run(self, optimization_run_id: str) -> OptimizationRun | None:
        return self._load(
            OptimizationRun, kind="run", resource_id=optimization_run_id, collection=COL_RUNS
        )

    def list_runs(self, *, tenant_id: str, project_id: str) -> tuple[OptimizationRun, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_RUNS).stream()
        matches = [_from_document(OptimizationRun, doc.to_dict()) for doc in docs]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def latest_run(self, *, tenant_id: str, project_id: str) -> OptimizationRun | None:
        matches = self.list_runs(tenant_id=tenant_id, project_id=project_id)
        return matches[0] if matches else None

    def get_run_by_idempotency(
        self, *, tenant_id: str, project_id: str, idempotency_key: str
    ) -> OptimizationRun | None:
        matches = [
            item
            for item in self.list_runs(tenant_id=tenant_id, project_id=project_id)
            if item.idempotency_key == idempotency_key
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_result_ref(self, result_id: str) -> OptimizationResultRef | None:
        return self._load(
            OptimizationResultRef, kind="result", resource_id=result_id, collection=COL_RESULTS
        )

    def get_result_ref_for_run(self, optimization_run_id: str) -> OptimizationResultRef | None:
        snap = self._index("run", optimization_run_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        docs = (
            self._workspace(str(data["tenant_id"]), str(data["workspace_id"]))
            .collection(COL_RESULTS)
            .stream()
        )
        matches = [
            _from_document(OptimizationResultRef, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("optimization_run_id") == optimization_run_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def latest_completed_result(
        self, *, tenant_id: str, project_id: str
    ) -> OptimizationResultRef | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_RESULTS).stream()
        matches = [_from_document(OptimizationResultRef, doc.to_dict()) for doc in docs]
        current = [item for item in matches if item.is_current]
        pool = current or matches
        if not pool:
            return None
        return max(pool, key=lambda item: item.created_at)

    def get_scenario(self, scenario_id: str) -> ScenarioArtifact | None:
        return self._load(
            ScenarioArtifact,
            kind="scenario",
            resource_id=scenario_id,
            collection=COL_SCENARIOS,
        )

    def list_scenarios(self, *, tenant_id: str, project_id: str) -> tuple[ScenarioArtifact, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_SCENARIOS).stream()
        matches = [_from_document(ScenarioArtifact, doc.to_dict()) for doc in docs]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def get_proposal(self, proposal_id: str) -> OptimizationProposal | None:
        return self._load(
            OptimizationProposal,
            kind="proposal",
            resource_id=proposal_id,
            collection=COL_PROPOSALS,
        )

    def list_proposals(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[OptimizationProposal, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_PROPOSALS).stream()
        matches = [_from_document(OptimizationProposal, doc.to_dict()) for doc in docs]
        return tuple(sorted(matches, key=lambda item: item.created_at, reverse=True))

    def get_proposal_readiness(self, receipt_id: str) -> ProposalReadinessReceipt | None:
        return self._load(
            ProposalReadinessReceipt,
            kind="proposal_readiness",
            resource_id=receipt_id,
            collection=COL_PROPOSAL_READY,
        )

    def get_proposal_readiness_for_proposal(
        self, proposal_id: str
    ) -> ProposalReadinessReceipt | None:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return None
        docs = (
            self._workspace(proposal.tenant_id, proposal.project_id)
            .collection(COL_PROPOSAL_READY)
            .stream()
        )
        matches = [
            _from_document(ProposalReadinessReceipt, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("proposal_id") == proposal_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_decision_receipt(self, decision_receipt_id: str) -> ProposalDecisionReceipt | None:
        return self._load(
            ProposalDecisionReceipt,
            kind="decision",
            resource_id=decision_receipt_id,
            collection=COL_DECISIONS,
        )

    def get_decision_receipt_for_proposal(self, proposal_id: str) -> ProposalDecisionReceipt | None:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return None
        docs = (
            self._workspace(proposal.tenant_id, proposal.project_id)
            .collection(COL_DECISIONS)
            .stream()
        )
        matches = [
            _from_document(ProposalDecisionReceipt, doc.to_dict())
            for doc in docs
            if (doc.to_dict() or {}).get("proposal_id") == proposal_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def get_decision_record(self, decision_id: str) -> PlanningDecisionRecord | None:
        return self._load(
            PlanningDecisionRecord,
            kind="decision_record",
            resource_id=decision_id,
            collection=COL_DECISION_RECORDS,
        )

    def get_constraint_ref(self, constraint_set_id: str) -> ConstraintSetRef | None:
        return self._load(
            ConstraintSetRef,
            kind="constraint_ref",
            resource_id=constraint_set_id,
            collection=COL_CONSTRAINT_REFS,
        )

    def list_constraint_refs(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ConstraintSetRef, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_CONSTRAINT_REFS).stream()
        return tuple(_from_document(ConstraintSetRef, doc.to_dict()) for doc in docs)

    def get_assumption_ref(self, assumption_set_id: str) -> ScenarioAssumptionSetRef | None:
        return self._load(
            ScenarioAssumptionSetRef,
            kind="assumption_ref",
            resource_id=assumption_set_id,
            collection=COL_ASSUMPTION_REFS,
        )

    def list_assumption_refs(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[ScenarioAssumptionSetRef, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_ASSUMPTION_REFS).stream()
        return tuple(_from_document(ScenarioAssumptionSetRef, doc.to_dict()) for doc in docs)

    def get_advanced_receipt(self, receipt_id: str) -> AdvancedOptimizationReadinessReceipt | None:
        return self._load(
            AdvancedOptimizationReadinessReceipt,
            kind="advanced_receipt",
            resource_id=receipt_id,
            collection=COL_ADVANCED_RECEIPTS,
        )

    def list_advanced_receipts(
        self, *, tenant_id: str, project_id: str
    ) -> tuple[AdvancedOptimizationReadinessReceipt, ...]:
        docs = self._workspace(tenant_id, project_id).collection(COL_ADVANCED_RECEIPTS).stream()
        return tuple(
            _from_document(AdvancedOptimizationReadinessReceipt, doc.to_dict()) for doc in docs
        )

    def get_risk_policy(self, policy_id: str) -> RiskEvaluationPolicy | None:
        return self._load(
            RiskEvaluationPolicy,
            kind="risk_policy",
            resource_id=policy_id,
            collection=COL_RISK_POLICIES,
        )

    def get_risk_policy_by_fingerprint(
        self, *, tenant_id: str, project_id: str, policy_fingerprint: str
    ) -> RiskEvaluationPolicy | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_RISK_POLICIES).stream()
        for doc in docs:
            item = _from_document(RiskEvaluationPolicy, doc.to_dict())
            if item.policy_fingerprint == policy_fingerprint:
                return item
        return None

    def get_candidate(self, candidate_id: str) -> CandidatePortfolio | None:
        return self._load(
            CandidatePortfolio,
            kind="candidate",
            resource_id=candidate_id,
            collection=COL_CANDIDATES,
        )

    def get_candidate_by_fingerprint(
        self, *, tenant_id: str, project_id: str, candidate_fingerprint: str
    ) -> CandidatePortfolio | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_CANDIDATES).stream()
        for doc in docs:
            item = _from_document(CandidatePortfolio, doc.to_dict())
            if item.candidate_fingerprint == candidate_fingerprint:
                return item
        return None

    def get_evaluation(self, evaluation_id: str) -> PortfolioRiskEvaluation | None:
        return self._load(
            PortfolioRiskEvaluation,
            kind="risk_evaluation",
            resource_id=evaluation_id,
            collection=COL_EVALUATIONS,
        )

    def get_evaluation_for_candidate(self, candidate_id: str) -> PortfolioRiskEvaluation | None:
        snap = self._index("risk_evaluation_candidate", candidate_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_evaluation(str(data.get("resource_id", "")))

    def get_evaluation_by_fingerprint(
        self, *, evaluation_fingerprint: str
    ) -> PortfolioRiskEvaluation | None:
        snap = self._index("risk_evaluation_fp", evaluation_fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_evaluation(str(data.get("resource_id", "")))

    def get_frontier(self, frontier_id: str) -> MarketingInvestmentFrontier | None:
        return self._load(
            MarketingInvestmentFrontier,
            kind="frontier",
            resource_id=frontier_id,
            collection=COL_FRONTIERS,
        )

    def get_frontier_by_fingerprint(
        self, *, fingerprint: str
    ) -> MarketingInvestmentFrontier | None:
        snap = self._index("frontier_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_frontier(str(data.get("resource_id", "")))

    def get_selection(self, selection_id: str) -> FrontierSelection | None:
        return self._load(
            FrontierSelection,
            kind="frontier_selection",
            resource_id=selection_id,
            collection=COL_SELECTIONS,
        )

    def get_selection_by_fingerprint(
        self, *, selection_fingerprint: str
    ) -> FrontierSelection | None:
        snap = self._index("selection_fp", selection_fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_selection(str(data.get("resource_id", "")))

    def get_parity_receipt(self, parity_receipt_id: str) -> RiskNeutralParityReceipt | None:
        return self._load(
            RiskNeutralParityReceipt,
            kind="parity",
            resource_id=parity_receipt_id,
            collection=COL_PARITY,
        )

    def get_distribution_set(self, set_id: str) -> ScenarioDistributionSet | None:
        return self._load(
            ScenarioDistributionSet, kind="dist_set", resource_id=set_id, collection=COL_DIST_SETS
        )

    def get_distribution_set_by_fingerprint(
        self, *, tenant_id: str, project_id: str, fingerprint: str
    ) -> ScenarioDistributionSet | None:
        docs = self._workspace(tenant_id, project_id).collection(COL_DIST_SETS).stream()
        for doc in docs:
            item = _from_document(ScenarioDistributionSet, doc.to_dict())
            if item.distribution_set_fingerprint == fingerprint:
                return item
        return None

    def get_correlation_spec(self, spec_id: str) -> ScenarioCorrelationSpec | None:
        return self._load(
            ScenarioCorrelationSpec,
            kind="correlation",
            resource_id=spec_id,
            collection=COL_CORRELATIONS,
        )

    def get_correlation_by_fingerprint(
        self, *, tenant_id: str, project_id: str, fingerprint: str
    ) -> ScenarioCorrelationSpec | None:
        snap = self._index("correlation_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        item = self.get_correlation_spec(str(data.get("resource_id", "")))
        if item is None or item.tenant_id != tenant_id or item.project_id != project_id:
            return None
        return item

    def get_simulation_policy(self, policy_id: str) -> MonteCarloSimulationPolicy | None:
        return self._load(
            MonteCarloSimulationPolicy,
            kind="sim_policy",
            resource_id=policy_id,
            collection=COL_SIM_POLICIES,
        )

    def get_simulation_policy_by_fingerprint(
        self, *, fingerprint: str
    ) -> MonteCarloSimulationPolicy | None:
        snap = self._index("sim_policy_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_simulation_policy(str(data.get("resource_id", "")))

    def get_run_spec(self, spec_id: str) -> SimulationRunSpec | None:
        return self._load(
            SimulationRunSpec, kind="run_spec", resource_id=spec_id, collection=COL_RUN_SPECS
        )

    def get_run_spec_by_fingerprint(self, *, fingerprint: str) -> SimulationRunSpec | None:
        snap = self._index("run_spec_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_run_spec(str(data.get("resource_id", "")))

    def get_simulation_run(self, simulation_run_id: str) -> SimulationRun | None:
        return self._load(
            SimulationRun, kind="sim_run", resource_id=simulation_run_id, collection=COL_SIM_RUNS
        )

    def get_simulation_run_by_fingerprint(self, *, fingerprint: str) -> SimulationRun | None:
        snap = self._index("sim_run_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_simulation_run(str(data.get("resource_id", "")))

    def list_outcome_distributions(
        self, *, simulation_run_id: str
    ) -> tuple[PortfolioOutcomeDistribution, ...]:
        run = self.get_simulation_run(simulation_run_id)
        if run is None:
            return ()
        docs = self._workspace(run.tenant_id, run.project_id).collection(COL_OUTCOME_DISTS).stream()
        loaded = (_from_document(PortfolioOutcomeDistribution, doc.to_dict()) for doc in docs)
        return tuple(item for item in loaded if item.simulation_run_id == simulation_run_id)

    def get_simulation_receipt_for_run(
        self, simulation_run_id: str
    ) -> MonteCarloSimulationReceipt | None:
        run = self.get_simulation_run(simulation_run_id)
        if run is None:
            return None
        docs = self._workspace(run.tenant_id, run.project_id).collection(COL_SIM_RECEIPTS).stream()
        for doc in docs:
            item = _from_document(MonteCarloSimulationReceipt, doc.to_dict())
            if item.simulation_run_id == simulation_run_id:
                return item
        return None

    def get_handoff_for_run(self, simulation_run_id: str) -> SimulationEvidenceHandoff | None:
        run = self.get_simulation_run(simulation_run_id)
        if run is None:
            return None
        docs = self._workspace(run.tenant_id, run.project_id).collection(COL_HANDOFFS).stream()
        for doc in docs:
            item = _from_document(SimulationEvidenceHandoff, doc.to_dict())
            if item.simulation_run_id == simulation_run_id:
                return item
        return None

    def get_simulation_evidence_handoff(self, handoff_id: str) -> SimulationEvidenceHandoff | None:
        return self._load(
            SimulationEvidenceHandoff,
            kind="sim_handoff",
            resource_id=handoff_id,
            collection=COL_HANDOFFS,
        )

    def get_investment_decision(self, decision_id: str) -> InvestmentDecisionRecord | None:
        return self._load(
            InvestmentDecisionRecord,
            kind="inv_decision",
            resource_id=decision_id,
            collection=COL_INV_DECISIONS,
        )

    def get_investment_decision_by_fingerprint(
        self, *, fingerprint: str
    ) -> InvestmentDecisionRecord | None:
        snap = self._index("inv_decision_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_investment_decision(str(data.get("resource_id", "")))

    def get_recommendation_adherence(self, adherence_id: str) -> RecommendationAdherence | None:
        return self._load(
            RecommendationAdherence,
            kind="rec_adh",
            resource_id=adherence_id,
            collection=COL_REC_ADHERENCE,
        )

    def get_recommendation_adherence_by_fingerprint(
        self, *, fingerprint: str
    ) -> RecommendationAdherence | None:
        snap = self._index("rec_adh_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_recommendation_adherence(str(data.get("resource_id", "")))

    def get_execution_adherence(self, adherence_id: str) -> ExecutionAdherence | None:
        return self._load(
            ExecutionAdherence,
            kind="exec_adh",
            resource_id=adherence_id,
            collection=COL_EXEC_ADHERENCE,
        )

    def get_execution_adherence_by_fingerprint(
        self, *, fingerprint: str
    ) -> ExecutionAdherence | None:
        snap = self._index("exec_adh_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_execution_adherence(str(data.get("resource_id", "")))

    def get_outcome_observation(self, observation_id: str) -> DecisionOutcomeObservation | None:
        return self._load(
            DecisionOutcomeObservation,
            kind="outcome_obs",
            resource_id=observation_id,
            collection=COL_OBSERVATIONS,
        )

    def get_outcome_observation_by_fingerprint(
        self, *, fingerprint: str
    ) -> DecisionOutcomeObservation | None:
        snap = self._index("outcome_obs_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_outcome_observation(str(data.get("resource_id", "")))

    def get_prediction_evidence(self, evidence_id: str) -> PredictionEvidenceSet | None:
        return self._load(
            PredictionEvidenceSet,
            kind="pred_ev",
            resource_id=evidence_id,
            collection=COL_PRED_EVIDENCE,
        )

    def get_prediction_evidence_by_fingerprint(
        self, *, project_id: str, fingerprint: str
    ) -> PredictionEvidenceSet | None:
        snap = self._index("pred_ev_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        item = self.get_prediction_evidence(str(data.get("resource_id", "")))
        if item is None or item.project_id != project_id:
            return None
        return item

    def get_prediction_error(self, error_id: str) -> PredictionErrorSummary | None:
        return self._load(
            PredictionErrorSummary,
            kind="pred_err",
            resource_id=error_id,
            collection=COL_PRED_ERRORS,
        )

    def get_prediction_error_by_fingerprint(
        self, *, fingerprint: str
    ) -> PredictionErrorSummary | None:
        snap = self._index("pred_err_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_prediction_error(str(data.get("resource_id", "")))

    def get_outcome_receipt(self, receipt_id: str) -> RecommendationOutcomeReceipt | None:
        return self._load(
            RecommendationOutcomeReceipt,
            kind="out_rcp",
            resource_id=receipt_id,
            collection=COL_OUTCOME_RECEIPTS,
        )

    def get_outcome_receipt_by_fingerprint(
        self, *, fingerprint: str
    ) -> RecommendationOutcomeReceipt | None:
        snap = self._index("out_rcp_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_outcome_receipt(str(data.get("resource_id", "")))

    def get_learning_receipt(self, receipt_id: str) -> DecisionOutcomeLearningReceipt | None:
        return self._load(
            DecisionOutcomeLearningReceipt,
            kind="learn_rcp",
            resource_id=receipt_id,
            collection=COL_LEARNING,
        )

    def get_learning_receipt_by_fingerprint(
        self, *, fingerprint: str
    ) -> DecisionOutcomeLearningReceipt | None:
        snap = self._index("learn_rcp_fp", fingerprint).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return self.get_learning_receipt(str(data.get("resource_id", "")))
