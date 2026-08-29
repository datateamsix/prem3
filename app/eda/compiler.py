"""Compile PreM3ExtendedEDAReport. Does not scrape HTML and cannot change MODEL_READY."""

from __future__ import annotations

from typing import Any

from app.core.meridian_eda_contracts import (
    EDA_MODEL_SPEC_GEO_TIME_INVARIANT,
    MeridianEDAFinding,
    MeridianEDAReceipt,
    MeridianEDASeverity,
)
from app.eda.extended_contracts import (
    INTERPRETATION_POLICY_VERSION,
    KNOT_FALLBACK_STATEMENT,
    KNOTS_NORMATIVE_REF,
    TRUSTED_GENERATED_MERIDIAN_HTML,
    EDAActionOwner,
    EDAActionType,
    EDAImplicationType,
    EDAInterpretationContext,
    EDAModelDesignHandoff,
    EDAModelingImplication,
    EDAOpenModelingDecision,
    EDARecommendedAction,
    ExtendedEDABusinessContext,
    ExtendedEDAEvidenceItem,
    ExtendedEDAExecutiveSummary,
    ExtendedEDAFinding,
    ExtendedEDAReadinessSummary,
    ExtendedEDAReportStatus,
    ExtendedEDASource,
    LabeledContextFact,
    OfficialEDAFindingView,
    PreM3ExtendedEDAReport,
    StatementAuthority,
)
from app.eda.fingerprint import (
    eda_receipt_fingerprint,
    knowledge_version,
    report_fingerprint,
    version_binding,
)
from app.eda.html_trust import assert_html_binding, html_sha256
from app.eda.interpreter import (
    DeterministicEDAInterpreter,
    EDAInterpreter,
    default_normative_refs,
    finding_is_material,
)
from app.eda.mel import eda_learning_evidence
from app.eda.music_center import OFFICIAL_HTML_FIXTURE, known_official_html_sha256
from app.tools.meridian_eda_gate import (
    build_meridian_feedback,
    evaluate_meridian_eda_gate,
)


def compile_extended_eda_report(
    *,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    track_id: str,
    report_id: str,
    version: int,
    receipt: MeridianEDAReceipt,
    official_html: bytes,
    official_html_ref: str,
    eda_receipt_ref: str,
    model_ready_manifest_ref: str | None = None,
    model_ready_fingerprint: str | None = None,
    business_context: ExtendedEDABusinessContext | None = None,
    data_foundation_facts: tuple[LabeledContextFact, ...] = (),
    data_foundation_fingerprint: str | None = None,
    interpreter: EDAInterpreter | None = None,
    official_html_artifact_class: str = TRUSTED_GENERATED_MERIDIAN_HTML,
    expected_html_sha256: str | None = None,
) -> PreM3ExtendedEDAReport:
    if official_html_artifact_class != TRUSTED_GENERATED_MERIDIAN_HTML:
        raise ValueError("Official EDA HTML must be TRUSTED_GENERATED_MERIDIAN_HTML.")
    html_digest = assert_html_binding(
        official_html_ref=official_html_ref,
        payload=official_html,
        expected_sha256=expected_html_sha256,
        fixture_sha256=html_sha256(OFFICIAL_HTML_FIXTURE),
        known_live_sha256=known_official_html_sha256(),
    )
    receipt_fp = eda_receipt_fingerprint(receipt)
    gate = evaluate_meridian_eda_gate(receipt=receipt, html_persisted=True)
    feedback = build_meridian_feedback(receipt=receipt, gate=gate)
    evidence = gate["evidence"]
    business = business_context or ExtendedEDABusinessContext()
    interpreter_impl: EDAInterpreter = interpreter or DeterministicEDAInterpreter()
    status = ExtendedEDAReportStatus.COMPLETE
    findings: list[ExtendedEDAFinding] = []
    interpretation_digest_parts: list[dict[str, Any]] = []
    for item in receipt.findings:
        official = _official_view(item)
        prem3 = None
        if finding_is_material(item) or item.severity != MeridianEDASeverity.INFO.value:
            context = _bounded_context(
                item,
                evidence=evidence,
                business=business,
                data_foundation_facts=data_foundation_facts,
            )
            try:
                prem3 = interpreter_impl.interpret(context)
                if item.finding_id not in prem3.evidence_refs and not any(
                    item.finding_id in ref for ref in prem3.evidence_refs
                ):
                    raise ValueError("interpretation missing official finding evidence ref")
            except Exception:  # noqa: BLE001 — interpretation must fail soft
                status = ExtendedEDAReportStatus.FAILED_INTERPRETATION
                prem3 = None
        material = finding_is_material(item)
        if item.severity == MeridianEDASeverity.INFO.value and not material:
            if status is not ExtendedEDAReportStatus.FAILED_INTERPRETATION:
                continue
        findings.append(
            ExtendedEDAFinding(
                finding_id=item.finding_id,
                official=official,
                prem3=prem3,
                material=material,
            )
        )
        if prem3 is not None:
            interpretation_digest_parts.append(
                {
                    "finding_id": item.finding_id,
                    "authority": prem3.authority.value,
                    "interpretation": prem3.interpretation,
                    "recommended_action": prem3.recommended_action,
                }
            )
    if status is ExtendedEDAReportStatus.FAILED_INTERPRETATION and any(
        item.prem3 is not None for item in findings
    ):
        status = ExtendedEDAReportStatus.PARTIAL
    implications, open_decisions = _implications(
        receipt=receipt,
        findings=tuple(findings),
        gate=gate,
    )
    actions = _actions(receipt=receipt, gate=gate, findings=tuple(findings))
    executive = _executive_summary(
        gate=gate,
        receipt=receipt,
        implications=implications,
        actions=actions,
    )
    readiness = ExtendedEDAReadinessSummary(
        official_gate_status=str(gate["status"]),
        official_gate_outcome=str(gate["outcome"]),
        max_official_severity=str(evidence["max_severity"]),
        error_count=int(evidence["error_count"]),
        attention_count=int(evidence["attention_count"]),
        info_count=int(evidence["info_count"]),
        review_recommended=bool(gate["review_recommended"]),
        safe_to_model=bool(feedback.safe_to_model),
        data_adequacy_summary={
            "n_geos": evidence["n_geos"],
            "n_times": evidence["n_times"],
            "n_knots": evidence["n_knots"],
            "n_controls": evidence["n_controls"],
            "n_treatments": evidence["n_treatments"],
            "n_parameters": evidence["n_parameters"],
            "n_data_points": evidence["n_data_points"],
            "ratio": evidence["data_adequacy_ratio"],
            "captured": evidence["data_adequacy_captured"],
            "knots_identifiable": evidence["knots_identifiable"],
            "source": "OFFICIAL_MERIDIAN",
        },
        unresolved_user_required_count=sum(
            1 for item in feedback.corrections if item.owner == "USER_REQUIRED"
        ),
    )
    handoff = EDAModelDesignHandoff(
        report_id=report_id,
        modeling_implications=implications,
        open_modeling_decisions=open_decisions,
        known_limitations=_limitations(receipt),
        relevant_finding_refs=tuple(item.finding_id for item in findings if item.material),
        recommended_starting_actions=tuple(item.action_type.value for item in actions[:3]),
    )
    knowledge = knowledge_version()
    binding = version_binding(
        eda_receipt_fingerprint_value=receipt_fp,
        official_html_sha256=html_digest,
        model_ready_fingerprint=model_ready_fingerprint,
        business_profile_snapshot_id=business.business_profile_snapshot_id,
        data_foundation_fingerprint=data_foundation_fingerprint,
        knowledge_version_value=knowledge,
        interpretation_digest=report_fingerprint({"parts": interpretation_digest_parts}),
    )
    fingerprint = report_fingerprint(binding)
    evidence_index = (
        ExtendedEDAEvidenceItem(
            evidence_id="official_html",
            kind="OFFICIAL_MERIDIAN_HTML",
            ref=official_html_ref,
            sha256=html_digest,
            authority=StatementAuthority.OFFICIAL_MERIDIAN,
        ),
        ExtendedEDAEvidenceItem(
            evidence_id="eda_receipt",
            kind="MERIDIAN_EDA_RECEIPT",
            ref=eda_receipt_ref,
            sha256=receipt_fp,
            authority=StatementAuthority.OFFICIAL_MERIDIAN,
        ),
        ExtendedEDAEvidenceItem(
            evidence_id="eda_gate",
            kind="MERIDIAN_EDA_GATE",
            ref=f"gate:{gate['status']}:{gate['outcome']}",
            sha256=None,
            authority=StatementAuthority.OFFICIAL_MERIDIAN,
        ),
        ExtendedEDAEvidenceItem(
            evidence_id="meridian_user_feedback",
            kind="MERIDIAN_USER_FEEDBACK",
            ref=f"feedback:{feedback.status}",
            sha256=None,
            authority=StatementAuthority.OFFICIAL_MERIDIAN,
        ),
        ExtendedEDAEvidenceItem(
            evidence_id="knowledge",
            kind="REVIEWED_MERIDIAN_KNOWLEDGE",
            ref=f"intelligence:{knowledge}",
            sha256=None,
            authority=StatementAuthority.PREM3_INTERPRETATION,
        ),
    )
    report = PreM3ExtendedEDAReport(
        report_id=report_id,
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=track_id,
        premodel_run_id=receipt.run_id,
        source=ExtendedEDASource(
            meridian_version=str((receipt.meridian or {}).get("version") or "1.8.0"),
            official_html_ref=official_html_ref,
            official_html_sha256=html_digest,
            eda_receipt_ref=eda_receipt_ref,
            eda_receipt_fingerprint=receipt_fp,
            model_ready_manifest_ref=model_ready_manifest_ref,
            model_ready_fingerprint=model_ready_fingerprint,
        ),
        business_context=business,
        readiness_summary=readiness,
        executive_summary=executive,
        findings=tuple(findings),
        model_design_implications=implications,
        open_modeling_decisions=open_decisions,
        recommended_next_steps=actions,
        evidence_index=evidence_index,
        model_design_handoff=handoff,
        status=status,
        version=version,
        fingerprint=fingerprint,
        interpretation_policy_version=INTERPRETATION_POLICY_VERSION,
        knowledge_version=knowledge,
        data_foundation_fingerprint=data_foundation_fingerprint,
        official_html_artifact_class=TRUSTED_GENERATED_MERIDIAN_HTML,
        resolution_feedback_status=feedback.status,
        mel_evidence_emitted=True,
    )
    eda_learning_evidence(report)
    return report


def _official_view(item: MeridianEDAFinding) -> OfficialEDAFindingView:
    return OfficialEDAFindingView(
        check_type=item.check_type,
        severity=item.severity,
        title=f"{item.check_type} {item.severity}",
        explanation=item.explanation,
        affected_variables=tuple(item.affected_variables),
        evidence_ref=item.finding_id,
        finding_cause=item.finding_cause,
        analysis_level=item.analysis_level,
    )


def _bounded_context(
    item: MeridianEDAFinding,
    *,
    evidence: dict[str, Any],
    business: ExtendedEDABusinessContext,
    data_foundation_facts: tuple[LabeledContextFact, ...],
) -> EDAInterpretationContext:
    return EDAInterpretationContext(
        finding_id=item.finding_id,
        official_severity=item.severity,
        official_explanation=item.explanation,
        check_type=item.check_type,
        affected_variables=tuple(item.affected_variables),
        data_adequacy_summary={
            "n_geos": evidence["n_geos"],
            "n_times": evidence["n_times"],
            "ratio": evidence["data_adequacy_ratio"],
            "source": "OFFICIAL_MERIDIAN",
        },
        business_iq_facts=business.labeled_facts,
        data_foundation_facts=data_foundation_facts,
        model_ready_semantics=(
            "MODEL_READY proves evidence is ready to model; it is not MODEL_ACCEPTED.",
            "EDA ModelSpec remains PRE_MODELING_EDA_ONLY.",
        ),
        meridian_normative_refs=default_normative_refs(),
        unresolved_decisions=(),
    )


def _implications(
    *,
    receipt: MeridianEDAReceipt,
    findings: tuple[ExtendedEDAFinding, ...],
    gate: dict[str, Any],
) -> tuple[tuple[EDAModelingImplication, ...], tuple[EDAOpenModelingDecision, ...]]:
    implications: list[EDAModelingImplication] = []
    decisions: list[EDAOpenModelingDecision] = []
    if receipt.model_spec.source == EDA_MODEL_SPEC_GEO_TIME_INVARIANT:
        implications.append(
            EDAModelingImplication(
                implication_id="imp_knot_strategy",
                implication_type=EDAImplicationType.KNOT_STRATEGY,
                statement=KNOT_FALLBACK_STATEMENT,
                finding_refs=(),
                evidence_refs=(
                    KNOTS_NORMATIVE_REF,
                    f"eda_model_spec:{receipt.model_spec.source}",
                ),
                approved_model_change=False,
                authority=StatementAuthority.PREM3_RECOMMENDATION,
            )
        )
        decisions.append(
            EDAOpenModelingDecision(
                decision_type="KNOT_STRATEGY",
                question="What knot strategy should the fitted ModelSpec use?",
                why_required=(
                    "EDA used a geo-time knot fallback for official EDA compatibility only."
                ),
                finding_refs=(),
                evidence_refs=(KNOTS_NORMATIVE_REF,),
                recommended_option=None,
                alternatives=("Meridian default knots", "modeler-specified knots", "AKS later"),
                authority=StatementAuthority.HUMAN_DECISION_REQUIRED,
                status="PENDING",
            )
        )
    seen_types: set[str] = set()
    for finding in findings:
        if finding.prem3 is None:
            continue
        mapped = _implication_type(finding.official.check_type)
        if mapped.value in seen_types:
            continue
        seen_types.add(mapped.value)
        implications.append(
            EDAModelingImplication(
                implication_id=f"imp_{mapped.value.lower()}",
                implication_type=mapped,
                statement=finding.prem3.modeling_implication,
                finding_refs=(finding.finding_id,),
                evidence_refs=finding.prem3.evidence_refs,
                approved_model_change=False,
            )
        )
        if finding.prem3.decision_required and finding.official.severity != "INFO":
            decisions.append(
                EDAOpenModelingDecision(
                    decision_type=finding.prem3.decision_type or mapped.value,
                    question=f"How should Model Design treat {finding.finding_id}?",
                    why_required=finding.prem3.why_it_matters,
                    finding_refs=(finding.finding_id,),
                    evidence_refs=finding.prem3.evidence_refs,
                    recommended_option=finding.prem3.recommended_action,
                    alternatives=finding.prem3.alternatives,
                    authority=StatementAuthority.HUMAN_DECISION_REQUIRED,
                    status="PENDING",
                )
            )
    if gate["outcome"] == "EDA_BLOCKED":
        decisions.append(
            EDAOpenModelingDecision(
                decision_type="RESOLVE_EDA_ERROR",
                question="What source or specification change clears the official ERROR?",
                why_required="Official ERROR blocks fitting and MODEL_READY.",
                finding_refs=tuple(
                    item.finding_id for item in findings if item.official.severity == "ERROR"
                ),
                evidence_refs=("meridian_eda_receipt",),
                recommended_option="Correct source data and rerun pre-modeling.",
                alternatives=(),
                authority=StatementAuthority.HUMAN_DECISION_REQUIRED,
                status="PENDING",
            )
        )
    return tuple(implications), tuple(decisions)


def _implication_type(check_type: str) -> EDAImplicationType:
    mapping = {
        "PAIRWISE_CORRELATION": EDAImplicationType.COLLINEARITY_REVIEW,
        "MULTICOLLINEARITY": EDAImplicationType.COLLINEARITY_REVIEW,
        "VARIABLE_GEO_TIME_COLLINEARITY": EDAImplicationType.CONTROL_SELECTION,
        "STANDARD_DEVIATION": EDAImplicationType.GEO_SCOPE_REVIEW,
        "COST_PER_MEDIA_UNIT": EDAImplicationType.TREATMENT_CLASSIFICATION,
        "KPI_INVARIABILITY": EDAImplicationType.DATA_ADEQUACY,
        "DATA_ADEQUACY": EDAImplicationType.DATA_ADEQUACY,
        "PRIOR_PROBABILITY": EDAImplicationType.PRIOR_REVIEW,
        "POPULATION_CORRELATION": EDAImplicationType.GEO_SCOPE_REVIEW,
    }
    return mapping.get(check_type, EDAImplicationType.OTHER)


def _actions(
    *,
    receipt: MeridianEDAReceipt,
    gate: dict[str, Any],
    findings: tuple[ExtendedEDAFinding, ...],
) -> tuple[EDARecommendedAction, ...]:
    actions: list[EDARecommendedAction] = []
    if gate["outcome"] == "EDA_BLOCKED":
        error = next(
            (item for item in findings if item.official.severity == "ERROR"),
            None,
        )
        actions.append(
            EDARecommendedAction(
                action_id="act_resolve_eda_error",
                finding_id=None if error is None else error.finding_id,
                action_type=EDAActionType.RESOLVE_EDA_ERROR,
                statement="Resolve the official Meridian ERROR before any fit attempt.",
                owner=EDAActionOwner.DATA_OWNER,
                urgency="blocking",
                blocking=True,
                evidence_required=("official_finding", "source_export"),
                target_capability="premodeling",
                route_hint="RETURN_TO_DATA_FOUNDATION",
            )
        )
        actions.append(
            EDARecommendedAction(
                action_id="act_return_foundation",
                finding_id=None,
                action_type=EDAActionType.RETURN_TO_FOUNDATION,
                statement="Return to Data Foundation if the ERROR is a source/coverage defect.",
                owner=EDAActionOwner.ANALYST,
                urgency="high",
                blocking=True,
                evidence_required=("data_foundation",),
                target_capability="data_foundation",
                route_hint="RETURN_TO_DATA_FOUNDATION",
            )
        )
        actions.append(
            EDARecommendedAction(
                action_id="act_rerun",
                finding_id=None,
                action_type=EDAActionType.RERUN_PREMODELING,
                statement="Rerun pre-modeling only after the official condition is corrected.",
                owner=EDAActionOwner.ANALYST,
                urgency="high",
                blocking=True,
                evidence_required=("corrected_source",),
                target_capability="premodeling",
                route_hint="RERUN_PREMODELING",
            )
        )
        return tuple(actions)
    if int(gate["evidence"]["attention_count"]) > 0:
        first_attention = next(
            (item for item in findings if item.official.severity == "ATTENTION"),
            None,
        )
        actions.append(
            EDARecommendedAction(
                action_id="act_review_attention",
                finding_id=None if first_attention is None else first_attention.finding_id,
                action_type=EDAActionType.REVIEW_ATTENTION_FINDING,
                statement=(
                    "Review official ATTENTION findings in Model Design. "
                    "Severity stays ATTENTION."
                ),
                owner=EDAActionOwner.MODELER,
                urgency="medium",
                blocking=False,
                evidence_required=("official_finding",),
                target_capability="model_design",
                route_hint="REVIEW_ATTENTION_FINDING",
            )
        )
    actions.append(
        EDARecommendedAction(
            action_id="act_proceed_design",
            finding_id=None,
            action_type=EDAActionType.PROCEED_TO_MODEL_DESIGN,
            statement="Proceed to Model Design with the typed EDA handoff. Do not refit EDA knots.",
            owner=EDAActionOwner.MODELER,
            urgency="normal",
            blocking=False,
            evidence_required=("eda_model_design_handoff",),
            target_capability="model_design",
            route_hint="PROCEED_TO_MODEL_DESIGN",
        )
    )
    if receipt.model_spec.source == EDA_MODEL_SPEC_GEO_TIME_INVARIANT:
        actions.append(
            EDARecommendedAction(
                action_id="act_review_knots",
                finding_id=None,
                action_type=EDAActionType.REVIEW_MODEL_SPEC,
                statement=KNOT_FALLBACK_STATEMENT,
                owner=EDAActionOwner.MODELER,
                urgency="medium",
                blocking=False,
                evidence_required=(KNOTS_NORMATIVE_REF,),
                target_capability="model_design",
                route_hint="REVIEW_MODEL_SPEC",
            )
        )
    return tuple(actions)


def _executive_summary(
    *,
    gate: dict[str, Any],
    receipt: MeridianEDAReceipt,
    implications: tuple[EDAModelingImplication, ...],
    actions: tuple[EDARecommendedAction, ...],
) -> ExtendedEDAExecutiveSummary:
    evidence = gate["evidence"]
    if gate["outcome"] == "EDA_BLOCKED":
        status = (
            "Official Meridian EDA produced ERROR findings. MODEL_READY is not established."
        )
    elif evidence["attention_count"]:
        status = (
            "Official Meridian EDA completed with ATTENTION. Review is recommended before fitting."
        )
    else:
        status = "Official Meridian EDA completed without ERROR or ATTENTION."
    strengths: list[str] = []
    if evidence["error_count"] == 0:
        strengths.append("Official ERROR count is 0.")
    if evidence["data_adequacy_captured"]:
        strengths.append("Official data-adequacy scalars were captured from Meridian.")
    if evidence["knots_identifiable"]:
        strengths.append("EDA knots are identifiable for PRE_MODELING_EDA_ONLY.")
    risks: list[str] = []
    if evidence["attention_count"]:
        risks.append(f"{evidence['attention_count']} official ATTENTION findings remain ATTENTION.")
    if receipt.model_spec.source == EDA_MODEL_SPEC_GEO_TIME_INVARIANT:
        risks.append("EDA knot fallback is not the final knot strategy.")
    return ExtendedEDAExecutiveSummary(
        status_statement=status,
        key_strengths=tuple(strengths),
        key_risks=tuple(risks),
        modeling_implications=tuple(item.statement for item in implications[:6]),
        user_actions=tuple(item.statement for item in actions),
    )


def _limitations(receipt: MeridianEDAReceipt) -> tuple[str, ...]:
    items = [
        "EDA ModelSpec is PRE_MODELING_EDA_ONLY and is not the fitted spec.",
        "PreM3 interpretation cannot change official severity or MODEL_READY.",
    ]
    if receipt.model_spec.source == EDA_MODEL_SPEC_GEO_TIME_INVARIANT:
        items.append(KNOT_FALLBACK_STATEMENT)
    return tuple(items)
