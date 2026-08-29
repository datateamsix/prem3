"""MEL seam for extended EDA. Evidence only; interpretations are not promoted."""

from __future__ import annotations

from typing import Any

from app.eda.extended_contracts import PreM3ExtendedEDAReport, StatementAuthority
from app.mel.models import LessonType


def eda_learning_evidence(report: PreM3ExtendedEDAReport) -> dict[str, Any]:
    """Structured future-learning payload. Generation is not promotion."""
    return {
        "domain": "EXTENDED_EDA",
        "lesson_type": LessonType.EDA_INTERPRETATION_PATTERN.value,
        "authority": "EVIDENCE_ONLY",
        "can_promote": False,
        "can_mutate_plan": False,
        "report_id": report.report_id,
        "report_fingerprint": report.fingerprint,
        "official_gate_outcome": report.readiness_summary.official_gate_outcome,
        "findings": [
            {
                "finding_id": item.finding_id,
                "official_severity": item.official.severity,
                "official_authority": StatementAuthority.OFFICIAL_MERIDIAN.value,
                "interpretation": None if item.prem3 is None else item.prem3.interpretation,
                "recommendation": None if item.prem3 is None else item.prem3.recommended_action,
                "interpretation_authority": None
                if item.prem3 is None
                else item.prem3.authority.value,
            }
            for item in report.findings
        ],
        "open_modeling_decisions": [
            {
                "decision_type": item.decision_type,
                "status": item.status,
                "authority": item.authority.value,
            }
            for item in report.open_modeling_decisions
        ],
        "note": (
            "Which EDA interpretations lead to better accepted models is a later "
            "MEL evaluation. This payload does not promote an interpretation."
        ),
    }
