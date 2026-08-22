"""Presentation-safe Business IQ API contracts."""

from __future__ import annotations

from typing import Any

from app.service.models import ApiModel


class BusinessProfileRequest(ApiModel):
    business_identity: dict[str, Any] | None = None
    measurement_objectives: list[dict[str, Any]] = []
    kpi: str | None = None
    kpi_definition: str | None = None
    kpi_custom_text: str | None = None
    economics_notes: str | None = None
    markets: list[dict[str, Any]] = []
    marketing_portfolio: list[dict[str, Any]] = []
    customer_journey_notes: str | None = None
    decision_process_notes: str | None = None
    commercial_driver_notes: str | None = None
    competition_notes: str | None = None
    facts: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    hypotheses: list[dict[str, Any]] = []
    knowledge_gaps: list[dict[str, Any]] = []
    prior_evidence: list[dict[str, Any]] = []
    metadata: dict[str, Any] | None = None


class ProposalCreateRequest(ApiModel):
    previous_fact: dict[str, Any] | None = None
    observed_evidence: dict[str, Any] = {}
    proposed_fact: dict[str, Any] = {}


class ProposalDecideRequest(ApiModel):
    accept: bool


class ClarificationCreateRequest(ApiModel):
    coverage_gap_id: str | None = None
    fact_id: str | None = None
    question: str


class ClarificationAnswerRequest(ApiModel):
    answer: str
    observed_evidence: dict[str, Any] = {}
