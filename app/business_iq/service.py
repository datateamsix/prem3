"""Workspace-scoped Business IQ service. Deterministic owners first."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.business_iq.brief import compile_grounded_brief
from app.business_iq.contracts import (
    BusinessClarificationRequest,
    BusinessContextReadyReceipt,
    BusinessEvent,
    BusinessFact,
    BusinessHypothesis,
    BusinessIdentity,
    BusinessIntelligenceBrief,
    BusinessProfile,
    BusinessProfileSnapshot,
    BusinessProfileUpdateProposal,
    BusinessProfileVersion,
    BusinessRelationship,
    KnowledgeGap,
    Market,
    MarketingChannel,
    MeasurementObjective,
    PriorEvidenceReference,
    ProfileMetadata,
)
from app.business_iq.enums import (
    ClarificationAnswer,
    KnowledgeState,
    ProposalDecision,
)
from app.business_iq.fingerprint import profile_fingerprint
from app.business_iq.ids import (
    new_clarification_id,
    new_profile_id,
    new_proposal_id,
    new_receipt_id,
    new_snapshot_id,
)
from app.business_iq.readiness import evaluate_business_context_ready
from app.business_iq.store import BusinessIqStore
from app.core.tenancy import require_tenant


class BusinessIqService:
    def __init__(self, *, store: BusinessIqStore) -> None:
        self.store = store

    def get_profile(self, *, tenant_id: str, workspace_id: str) -> BusinessProfile:
        self._authorize(tenant_id)
        found = self.store.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        if found is None:
            raise KeyError("Business profile not found.")
        return found

    def create_profile(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        actor_id: str,
        payload: dict[str, Any],
        organization_display_name: str | None = None,
    ) -> BusinessProfile:
        self._authorize(tenant_id)
        if self.store.get_profile(tenant_id=tenant_id, workspace_id=workspace_id) is not None:
            raise ValueError("Business profile already exists for this workspace.")
        now = datetime.now(UTC)
        profile_id = new_profile_id()
        snapshot_id = new_snapshot_id()
        draft = self._document(
            profile_id=profile_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            version=1,
            snapshot_id=snapshot_id,
            actor_id=actor_id,
            created_at=now,
            payload=payload,
            organization_display_name=organization_display_name,
        )
        return self._persist_version(draft, change_summary="created")

    def patch_profile(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> BusinessProfile:
        current = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        merged = {**current.model_dump(mode="json"), **payload}
        now = datetime.now(UTC)
        snapshot_id = new_snapshot_id()
        draft = self._document(
            profile_id=current.profile_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            version=current.version + 1,
            snapshot_id=snapshot_id,
            actor_id=actor_id,
            created_at=current.created_at,
            updated_at=now,
            payload=merged,
            organization_display_name=current.metadata.organization_display_name,
            created_by=current.created_by,
        )
        previous = self.store.get_snapshot(current.current_snapshot_id)
        if previous is not None and previous.profile.model_dump(mode="json") == current.model_dump(
            mode="json"
        ):
            pass
        return self._persist_version(draft, change_summary="updated")

    def list_versions(self, *, tenant_id: str, workspace_id: str) -> list[BusinessProfileVersion]:
        profile = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        return self.store.list_versions(profile_id=profile.profile_id)

    def get_snapshot(self, *, tenant_id: str, snapshot_id: str) -> BusinessProfileSnapshot:
        self._authorize(tenant_id)
        found = self.store.get_snapshot(snapshot_id)
        if found is None or found.tenant_id != tenant_id:
            raise KeyError("Snapshot not found.")
        return found

    def evaluate_ready(self, *, tenant_id: str, workspace_id: str) -> BusinessContextReadyReceipt:
        profile = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        receipt = evaluate_business_context_ready(
            profile=profile,
            snapshot_id=profile.current_snapshot_id,
            actor_id=require_tenant().user_id or profile.updated_by,
        )
        return self.store.put_ready_receipt(receipt)

    def get_brief(self, *, tenant_id: str, workspace_id: str) -> BusinessIntelligenceBrief:
        self._authorize(tenant_id)
        found = self.store.get_brief(workspace_id=workspace_id)
        if found is None:
            raise KeyError("Brief has not been generated.")
        return found

    def regenerate_brief(self, *, tenant_id: str, workspace_id: str) -> BusinessIntelligenceBrief:
        profile = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        brief = compile_grounded_brief(profile=profile)
        return self.store.put_brief(brief)

    def create_proposal(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        actor_id: str,
        previous_fact: dict[str, Any] | None,
        observed_evidence: dict[str, Any],
        proposed_fact: dict[str, Any],
    ) -> BusinessProfileUpdateProposal:
        profile = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        proposal = BusinessProfileUpdateProposal(
            proposal_id=new_proposal_id(),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            profile_id=profile.profile_id,
            previous_fact=previous_fact,
            observed_evidence=observed_evidence,
            proposed_fact=proposed_fact,
            created_at=datetime.now(UTC),
            created_by=actor_id,
        )
        return self.store.put_proposal(proposal)

    def list_proposals(
        self, *, tenant_id: str, workspace_id: str
    ) -> list[BusinessProfileUpdateProposal]:
        self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        return self.store.list_proposals(workspace_id=workspace_id)

    def decide_proposal(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        proposal_id: str,
        actor_id: str,
        accept: bool,
    ) -> BusinessProfileUpdateProposal:
        profile = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        proposal = self.store.get_proposal(proposal_id)
        if proposal is None or proposal.workspace_id != workspace_id:
            raise KeyError("Proposal not found.")
        if proposal.decision is not ProposalDecision.PENDING:
            raise ValueError("Proposal already decided.")
        decided = proposal.model_copy(
            update={
                "decision": ProposalDecision.ACCEPTED if accept else ProposalDecision.REJECTED,
                "decided_by": actor_id,
                "decided_at": datetime.now(UTC),
                "receipt_id": new_receipt_id(),
            }
        )
        stored = self.store.put_proposal(decided)
        if accept:
            patch = self._proposal_to_patch(profile, decided)
            self.patch_profile(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                actor_id=actor_id,
                payload=patch,
            )
        return stored

    def create_clarification(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        coverage_gap_id: str | None,
        fact_id: str | None,
        question: str,
    ) -> BusinessClarificationRequest:
        profile = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        item = BusinessClarificationRequest(
            clarification_id=new_clarification_id(),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            profile_id=profile.profile_id,
            coverage_gap_id=coverage_gap_id,
            fact_id=fact_id,
            question=question,
            created_at=datetime.now(UTC),
        )
        return self.store.put_clarification(item)

    def answer_clarification(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        clarification_id: str,
        actor_id: str,
        answer: ClarificationAnswer,
        observed_evidence: dict[str, Any],
    ) -> BusinessClarificationRequest:
        profile = self.get_profile(tenant_id=tenant_id, workspace_id=workspace_id)
        item = self.store.get_clarification(clarification_id)
        if item is None or item.workspace_id != workspace_id:
            raise KeyError("Clarification not found.")
        proposal_id = None
        if answer is ClarificationAnswer.CONFIRMED_BUSINESS_PAUSE:
            proposal = self.create_proposal(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                actor_id=actor_id,
                previous_fact={"fact_id": item.fact_id} if item.fact_id else None,
                observed_evidence=observed_evidence,
                proposed_fact={
                    "concept": "channel_lifecycle",
                    "lifecycle_status": "PAUSED",
                    "source": "coverage_gap_clarification",
                },
            )
            proposal_id = proposal.proposal_id
        updated = item.model_copy(
            update={
                "answer": answer,
                "answered_at": datetime.now(UTC),
                "answered_by": actor_id,
                "proposal_id": proposal_id,
            }
        )
        del profile
        return self.store.put_clarification(updated)

    def _persist_version(self, profile: BusinessProfile, *, change_summary: str) -> BusinessProfile:
        fingerprinted = profile.model_copy(update={"fingerprint": profile_fingerprint(profile)})
        snapshot = BusinessProfileSnapshot(
            snapshot_id=fingerprinted.current_snapshot_id,
            profile_id=fingerprinted.profile_id,
            tenant_id=fingerprinted.tenant_id,
            workspace_id=fingerprinted.workspace_id,
            version=fingerprinted.version,
            fingerprint=fingerprinted.fingerprint,
            profile=fingerprinted,
            created_at=fingerprinted.updated_at,
            created_by=fingerprinted.updated_by,
        )
        self.store.put_snapshot(snapshot)
        self.store.put_version(
            BusinessProfileVersion(
                profile_id=fingerprinted.profile_id,
                version=fingerprinted.version,
                snapshot_id=fingerprinted.current_snapshot_id,
                fingerprint=fingerprinted.fingerprint,
                created_at=fingerprinted.updated_at,
                created_by=fingerprinted.updated_by,
                change_summary=change_summary,
            )
        )
        return self.store.put_profile(fingerprinted)

    def _document(
        self,
        *,
        profile_id: str,
        tenant_id: str,
        workspace_id: str,
        version: int,
        snapshot_id: str,
        actor_id: str,
        created_at: datetime,
        payload: dict[str, Any],
        organization_display_name: str | None,
        updated_at: datetime | None = None,
        created_by: str | None = None,
    ) -> BusinessProfile:
        identity_raw = payload.get("business_identity") or {}
        metadata_raw = payload.get("metadata") or {}
        return BusinessProfile(
            profile_id=profile_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            version=version,
            fingerprint="",
            current_snapshot_id=snapshot_id,
            business_identity=BusinessIdentity.model_validate(identity_raw),
            measurement_objectives=tuple(
                MeasurementObjective.model_validate(item)
                for item in payload.get("measurement_objectives") or ()
            ),
            kpi=payload.get("kpi"),
            kpi_definition=payload.get("kpi_definition"),
            kpi_custom_text=payload.get("kpi_custom_text"),
            economics_notes=payload.get("economics_notes"),
            markets=tuple(Market.model_validate(item) for item in payload.get("markets") or ()),
            marketing_portfolio=tuple(
                MarketingChannel.model_validate(item)
                for item in payload.get("marketing_portfolio") or ()
            ),
            customer_journey_notes=payload.get("customer_journey_notes"),
            decision_process_notes=payload.get("decision_process_notes"),
            commercial_driver_notes=payload.get("commercial_driver_notes"),
            competition_notes=payload.get("competition_notes"),
            facts=tuple(BusinessFact.model_validate(item) for item in payload.get("facts") or ()),
            events=tuple(BusinessEvent.model_validate(item) for item in payload.get("events") or ()),
            relationships=tuple(
                BusinessRelationship.model_validate(item) for item in payload.get("relationships") or ()
            ),
            hypotheses=tuple(
                BusinessHypothesis.model_validate(item) for item in payload.get("hypotheses") or ()
            ),
            knowledge_gaps=tuple(
                KnowledgeGap.model_validate(item) for item in payload.get("knowledge_gaps") or ()
            ),
            prior_evidence=tuple(
                PriorEvidenceReference.model_validate(item)
                for item in payload.get("prior_evidence") or ()
            ),
            metadata=ProfileMetadata(
                organization_display_name=organization_display_name
                or metadata_raw.get("organization_display_name"),
                logo_asset_ref=metadata_raw.get("logo_asset_ref"),
            ),
            created_at=created_at,
            updated_at=updated_at or created_at,
            updated_by=actor_id,
            created_by=created_by or actor_id,
        )

    def _proposal_to_patch(
        self, profile: BusinessProfile, proposal: BusinessProfileUpdateProposal
    ) -> dict[str, Any]:
        proposed = proposal.proposed_fact
        if proposed.get("concept") == "channel_lifecycle":
            status = proposed.get("lifecycle_status")
            channels = []
            for channel in profile.marketing_portfolio:
                if status and (
                    channel.canonical_name == proposed.get("channel")
                    or channel.channel_id == proposed.get("channel_id")
                    or proposed.get("channel") is None
                ):
                    channels.append(
                        channel.model_copy(
                            update={"lifecycle_status": status}
                        ).model_dump(mode="json")
                    )
                else:
                    channels.append(channel.model_dump(mode="json"))
            return {"marketing_portfolio": channels}
        if proposed.get("concept"):
            facts = [item.model_dump(mode="json") for item in profile.facts]
            facts.append(
                {
                    "fact_id": proposed.get("fact_id") or new_receipt_id(),
                    "concept": proposed["concept"],
                    "value": proposed.get("value"),
                    "knowledge_state": KnowledgeState.SYSTEM_OBSERVED.value,
                    "custom_text": proposed.get("custom_text"),
                }
            )
            return {"facts": facts}
        return {}

    def _authorize(self, tenant_id: str) -> None:
        if require_tenant().tenant_id != tenant_id:
            raise PermissionError("Tenant mismatch.")
