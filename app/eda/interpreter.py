"""Bounded EDA interpretation. Agent may explain; it cannot set official severity."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.core.meridian_eda_contracts import MeridianEDAFinding, MeridianEDASeverity
from app.eda.extended_contracts import (
    KNOTS_NORMATIVE_REF,
    EDAInterpretationContext,
    Prem3FindingInterpretation,
    StatementAuthority,
)
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION, PINNED_UPSTREAM_COMMIT

CHECK_IMPLICATION = {
    "PAIRWISE_CORRELATION": (
        "COLLINEARITY_REVIEW",
        "Review whether correlated series should stay as separate treatments or be combined.",
    ),
    "MULTICOLLINEARITY": (
        "COLLINEARITY_REVIEW",
        "Review control and treatment roles before fitting; "
        "collinearity can distort channel effects.",
    ),
    "VARIABLE_GEO_TIME_COLLINEARITY": (
        "CONTROL_SELECTION",
        "Time-only or geo-invariant controls affect knot identifiability and time-effect design.",
    ),
    "STANDARD_DEVIATION": (
        "GEO_SCOPE_REVIEW",
        "Outliers or low variability can change geo pooling, "
        "transformations, or channel inclusion.",
    ),
    "COST_PER_MEDIA_UNIT": (
        "TREATMENT_CLASSIFICATION",
        "Cost-per-unit outliers can indicate mapping, scaling, or treatment-definition issues.",
    ),
    "KPI_INVARIABILITY": (
        "DATA_ADEQUACY",
        "KPI variation is a modeling feasibility signal, not a readiness override.",
    ),
    "DATA_ADEQUACY": (
        "DATA_ADEQUACY",
        "Data-to-parameter ratio informs MCMC preparation and holdout ambition, not MODEL_READY.",
    ),
    "PRIOR_PROBABILITY": (
        "PRIOR_REVIEW",
        "Prior predictive diagnostics belong in Model Design prior review, "
        "not EDA ModelSpec promotion.",
    ),
    "POPULATION_CORRELATION": (
        "GEO_SCOPE_REVIEW",
        "Population scaling and geo correlation should be reviewed for geo models.",
    ),
}

MATERIAL_INFO_TYPES = {
    "DATA_ADEQUACY",
    "PAIRWISE_CORRELATION",
    "MULTICOLLINEARITY",
    "VARIABLE_GEO_TIME_COLLINEARITY",
    "PRIOR_PROBABILITY",
}


class EDAInterpreter(Protocol):
    def interpret(
        self, context: EDAInterpretationContext
    ) -> Prem3FindingInterpretation: ...


class DeterministicEDAInterpreter:
    """Evidence-grounded templates. Does not invent official severity or metrics."""

    def interpret(self, context: EDAInterpretationContext) -> Prem3FindingInterpretation:
        implication_type, implication = CHECK_IMPLICATION.get(
            context.check_type,
            ("OTHER", "Carry this official finding into Model Design review."),
        )
        decision_required = context.official_severity in {
            MeridianEDASeverity.ERROR.value,
            MeridianEDASeverity.ATTENTION.value,
        }
        business = tuple(
            f"{item.label}: {item.statement}" for item in context.business_iq_facts
        )
        if context.official_severity == MeridianEDASeverity.ERROR.value:
            interpretation = (
                "Official Meridian rejected this input. PreM3 cannot override that ERROR."
            )
            why = (
                "An official ERROR blocks EDA completion and cannot establish MODEL_READY."
            )
            action = "Correct the cited source or specification, then rerun pre-modeling."
            uncertainty = "none — official ERROR is deterministic."
            authority = StatementAuthority.PREM3_RECOMMENDATION
            decision_type = "RESOLVE_EDA_ERROR"
        elif context.official_severity == MeridianEDASeverity.ATTENTION.value:
            interpretation = (
                "Official Meridian flagged this as ATTENTION. It remains ATTENTION; "
                "PreM3 concern does not change official severity."
            )
            why = (
                "ATTENTION can change Model Design choices without blocking MODEL_READY."
            )
            action = "Review this finding during Model Design; do not silently change ModelSpec."
            uncertainty = "medium — impact depends on business context and modeler judgment."
            authority = StatementAuthority.PREM3_INTERPRETATION
            decision_type = implication_type
        else:
            interpretation = (
                "Official Meridian recorded an informational finding. "
                "PreM3 keeps commentary concise unless it is material to design."
            )
            why = (
                "INFO does not change official readiness. It may still inform later monitoring."
                if context.check_type not in MATERIAL_INFO_TYPES
                else "This INFO is material to Model Design or a known limitation."
            )
            action = (
                "No blocking action. Carry forward if Model Design needs the signal."
            )
            uncertainty = "low — informational unless later design evidence elevates it."
            authority = StatementAuthority.PREM3_INTERPRETATION
            decision_type = None
            decision_required = context.check_type in MATERIAL_INFO_TYPES
        evidence = (
            f"official_finding:{context.finding_id}",
            *context.meridian_normative_refs,
        )
        if business:
            interpretation = (
                f"{interpretation} Business IQ is context, not a Meridian finding. "
                + " ".join(business)
            )
        return Prem3FindingInterpretation(
            interpretation=interpretation,
            why_it_matters=why,
            business_context_relevance=business,
            modeling_implication=implication,
            recommended_action=action,
            alternatives=(),
            uncertainty=uncertainty,
            decision_required=decision_required,
            decision_type=decision_type,
            authority=authority
            if not decision_required
            else (
                StatementAuthority.HUMAN_DECISION_REQUIRED
                if context.official_severity == MeridianEDASeverity.ERROR.value
                else authority
            ),
            evidence_refs=evidence,
        )


def default_normative_refs() -> tuple[str, ...]:
    return (
        KNOTS_NORMATIVE_REF,
        f"meridian:{PINNED_UPSTREAM_COMMIT}",
        f"google-meridian=={PINNED_RUNTIME_VERSION}",
    )


def finding_is_material(finding: MeridianEDAFinding) -> bool:
    if finding.severity in {MeridianEDASeverity.ERROR.value, MeridianEDASeverity.ATTENTION.value}:
        return True
    return finding.check_type in MATERIAL_INFO_TYPES


def wrap_interpreter(
    interpreter: EDAInterpreter,
    *,
    on_failure: Callable[[Exception], None] | None = None,
) -> EDAInterpreter:
    class _Soft:
        def interpret(self, context: EDAInterpretationContext) -> Prem3FindingInterpretation:
            try:
                return interpreter.interpret(context)
            except Exception as exc:  # noqa: BLE001 — fail-soft interpretation
                if on_failure is not None:
                    on_failure(exc)
                raise

    return _Soft()
