"""Build the Music Center extended EDA proof from actual published finding IDs."""

from __future__ import annotations

from typing import Any

from app.eda.compiler import compile_extended_eda_report
from app.eda.extended_contracts import TRUSTED_GENERATED_MERIDIAN_HTML, StatementAuthority
from app.eda.html_trust import html_sha256, inspect_generated_html
from app.eda.mel import eda_learning_evidence
from app.eda.music_center import (
    MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
    MUSIC_CENTER_CYCLE_ID,
    MUSIC_CENTER_DATASET_FINGERPRINT,
    MUSIC_CENTER_FINDING_IDS,
    MUSIC_CENTER_HTML_REF,
    MUSIC_CENTER_MODEL_READY_FINGERPRINT,
    MUSIC_CENTER_MODEL_READY_REF,
    MUSIC_CENTER_OFFICIAL_HTML_SHA256,
    MUSIC_CENTER_RECEIPT_REF,
    MUSIC_CENTER_RUN_ID,
    OFFICIAL_HTML_FIXTURE,
    music_center_business_context,
    music_center_foundation_facts,
    music_center_official_html,
    music_center_receipt,
)


def compile_music_center_extended_report(*, report_id: str = "edarep_music_center_proof"):
    official_html = music_center_official_html()
    return compile_extended_eda_report(
        tenant_id="ten_music_center",
        project_id="wsp_music_center",
        cycle_id=MUSIC_CENTER_CYCLE_ID,
        track_id="trk_mmm",
        report_id=report_id,
        version=1,
        receipt=music_center_receipt(),
        official_html=official_html,
        official_html_ref=MUSIC_CENTER_HTML_REF,
        eda_receipt_ref=MUSIC_CENTER_RECEIPT_REF,
        model_ready_manifest_ref=MUSIC_CENTER_MODEL_READY_REF,
        model_ready_fingerprint=MUSIC_CENTER_MODEL_READY_FINGERPRINT,
        business_context=music_center_business_context(),
        data_foundation_facts=music_center_foundation_facts(),
        data_foundation_fingerprint=MUSIC_CENTER_DATASET_FINGERPRINT,
        expected_html_sha256=MUSIC_CENTER_OFFICIAL_HTML_SHA256,
    )


def music_center_extended_eda_proof() -> dict[str, Any]:
    official_html = music_center_official_html()
    report = compile_music_center_extended_report()
    ready = report.readiness_summary
    handoff = report.model_design_handoff
    inspection = inspect_generated_html(
        official_html, artifact_class=TRUSTED_GENERATED_MERIDIAN_HTML
    )
    fixture_sha = html_sha256(OFFICIAL_HTML_FIXTURE)
    return {
        "assignment": "Music Center Dataset A",
        "source_finding_ids": list(MUSIC_CENTER_FINDING_IDS),
        "source_finding_ids_are_published_cloud_evidence": True,
        "published_evidence_ref": "evaluation/dataset_a_cloud_run_bundle.json",
        "premodel_run_id": MUSIC_CENTER_RUN_ID,
        "official_html_ref": MUSIC_CENTER_HTML_REF,
        "official_html_sha256": report.source.official_html_sha256,
        "official_html_live_gcs_bytes_vendored": True,
        "official_html_sha256_scope": (
            "SHA-256 of the live GCS object bytes. The vendored copy at "
            "evaluation/fixtures/music_center_meridian_eda_report.html is byte-identical "
            "and unaltered."
        ),
        "local_html_fixture_sha256": fixture_sha,
        "local_html_fixture_ref": "prem3-fixture://meridian_eda_report.html",
        "live_and_fixture_sha_are_distinct": (
            report.source.official_html_sha256 != fixture_sha
        ),
        "official_html_embed": {
            "artifact_class": inspection.artifact_class,
            "has_scripts": inspection.has_scripts,
            "sandbox": inspection.sandbox,
            "csp": inspection.csp,
            "allow_same_origin": False,
            "allow_top_navigation": False,
        },
        "eda_receipt_ref": MUSIC_CENTER_RECEIPT_REF,
        "eda_receipt_fingerprint": report.source.eda_receipt_fingerprint,
        "business_profile_snapshot_id": MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
        "model_ready_fingerprint": MUSIC_CENTER_MODEL_READY_FINGERPRINT,
        "data_foundation_fingerprint": MUSIC_CENTER_DATASET_FINGERPRINT,
        "official_severity_summary": {
            "max_severity": ready.max_official_severity,
            "error_count": ready.error_count,
            "attention_count": ready.attention_count,
            "info_count": ready.info_count,
            "official_gate_status": ready.official_gate_status,
            "official_gate_outcome": ready.official_gate_outcome,
            "review_recommended": ready.review_recommended,
            "safe_to_model": ready.safe_to_model,
        },
        "extended_finding_count": len(report.findings),
        "modeling_implication_count": len(report.model_design_implications),
        "open_decision_count": len(report.open_modeling_decisions),
        "next_actions": [
            {
                "action_type": item.action_type.value,
                "owner": item.owner.value,
                "blocking": item.blocking,
                "route_hint": item.route_hint,
            }
            for item in report.recommended_next_steps
        ],
        "report_version": report.version,
        "report_fingerprint": report.fingerprint,
        "interpretation_policy_version": report.interpretation_policy_version,
        "knowledge_version": report.knowledge_version,
        "authority_example": _authority_example(report),
        "eda_model_design_handoff": handoff.model_dump(mode="json"),
        "knot_fallback_is_not_final_knots": any(
            item.implication_type.value == "KNOT_STRATEGY"
            for item in report.model_design_implications
        ),
        "mel_evidence": eda_learning_evidence(report),
        "business_iq_labeled_as_context": all(
            item.label == "BUSINESS_IQ_CONTEXT"
            or item.label == "DATA_FOUNDATION_CONTEXT"
            or item.label == "MODEL_READY_CONTEXT"
            for item in report.business_context.labeled_facts
        ),
    }


def _authority_example(report) -> dict[str, Any]:
    attention = next(
        item for item in report.findings if item.official.severity == "ATTENTION"
    )
    return {
        "finding_id": attention.finding_id,
        "official_meridian": {
            "authority": StatementAuthority.OFFICIAL_MERIDIAN.value,
            "severity": attention.official.severity,
            "explanation": attention.official.explanation,
        },
        "prem3_interpretation": {
            "authority": None if attention.prem3 is None else attention.prem3.authority.value,
            "interpretation": None if attention.prem3 is None else attention.prem3.interpretation,
        },
        "prem3_recommendation": {
            "authority": StatementAuthority.PREM3_RECOMMENDATION.value,
            "statement": None if attention.prem3 is None else attention.prem3.recommended_action,
        },
        "human_decision_required": {
            "authority": StatementAuthority.HUMAN_DECISION_REQUIRED.value,
            "open_decision_types": [
                item.decision_type for item in report.open_modeling_decisions
            ],
        },
        "severity_unchanged": attention.official.severity == "ATTENTION",
    }
