"""Narrow agent tools. Mutating calls accept IDs only."""

from __future__ import annotations

from app.data_foundation.context import DataFoundationContext
from app.data_foundation.service import DataFoundationService


def inspect_data_foundation(service: DataFoundationService, context: DataFoundationContext) -> dict:
    overview = service.get_overview(context)
    return overview.model_dump(mode="json")


def list_source_findings(
    service: DataFoundationService, context: DataFoundationContext, source_id: str
) -> dict:
    return service.get_quality_overview(context, source_id).model_dump(mode="json")


def request_quality_explanation(observed_fact: str, finding_id: str) -> dict:
    return {
        "finding_id": finding_id,
        "observed_fact": observed_fact,
        "agent_interpretation": None,
        "note": "Interpretation is stored separately from observed_fact.",
    }


def propose_registered_transformation(
    service: DataFoundationService,
    context: DataFoundationContext,
    *,
    source_id: str,
    transformation_plan_id: str | None = None,
) -> dict:
    del service, context
    if transformation_plan_id is None:
        raise PermissionError("Agent must reference a compiled transformation_plan_id.")
    return {"source_id": source_id, "transformation_plan_id": transformation_plan_id}


def request_business_clarification(*, finding_id: str, question: str) -> dict:
    return {"finding_id": finding_id, "question": question, "sql": None, "path": None}
