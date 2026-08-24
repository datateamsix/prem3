"""M3-02A extended Meridian EDA. Official receipt remains truth; this layer is additive."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.control_plane.entitlements import PlanId
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.core.meridian_eda_contracts import (
    MeridianEDAFinding,
    MeridianEDAReceipt,
    category_for_check,
)
from app.eda.compiler import compile_extended_eda_report
from app.eda.extended_contracts import (
    CUSTOMER_UPLOAD_HTML,
    INTERPRETATION_POLICY_VERSION,
    KNOT_FALLBACK_STATEMENT,
    TRUSTED_GENERATED_MERIDIAN_HTML,
)
from app.eda.fingerprint import knowledge_version
from app.eda.html_trust import (
    HtmlBindingError,
    HtmlNotTrustedError,
    html_sha256,
    inspect_generated_html,
)
from app.eda.music_center import (
    MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
    MUSIC_CENTER_CYCLE_ID,
    MUSIC_CENTER_FINDING_IDS,
    MUSIC_CENTER_HTML_REF,
    MUSIC_CENTER_MODEL_READY_FINGERPRINT,
    MUSIC_CENTER_OFFICIAL_HTML_SHA256,
    OFFICIAL_HTML_FIXTURE,
    OFFICIAL_HTML_FIXTURE_REF,
    music_center_business_context,
    music_center_official_html,
    music_center_receipt,
)
from app.eda.proof import compile_music_center_extended_report, music_center_extended_eda_proof
from app.eda.service import ExtendedEDAService
from app.modeling.mmm.design import build_design_brief, proposed_model_plan
from app.modeling.mmm.service import MMMModelingService
from app.tools.meridian_eda_gate import evaluate_meridian_eda_gate
from tests.unit.api_support import auth_header, make_client, seed_tenant
from tests.unit.test_meridian_eda import _finding, _receipt
from tests.unit.test_mmm_modeling import MEDIA, MUSIC_CENTER_FP, MUSIC_CENTER_WINDOW

PROOF_PATH = Path("evaluation/prem3_extended_eda_proof.json")
CUSTOMER_HTML = b"<html><script>alert(1)</script><body>upload</body></html>"


class _BoomInterpreter:
    def interpret(self, context):
        raise RuntimeError("gemini unavailable")


def _compile(receipt: MeridianEDAReceipt, **overrides):
    payload = {
        "tenant_id": "ten_a",
        "project_id": "wsp_a",
        "cycle_id": "cyc_1",
        "track_id": "trk_mmm",
        "report_id": "edarep_test",
        "version": 1,
        "receipt": receipt,
        "official_html": OFFICIAL_HTML_FIXTURE,
        "official_html_ref": OFFICIAL_HTML_FIXTURE_REF,
        "eda_receipt_ref": "prem3-fixture://meridian_eda_receipt.json",
        "model_ready_fingerprint": MUSIC_CENTER_FP,
    }
    payload.update(overrides)
    return compile_extended_eda_report(**payload)


def test_official_severity_and_html_sha_are_immutable() -> None:
    receipt = music_center_receipt()
    report = compile_music_center_extended_report()
    by_id = {item.finding_id: item for item in report.findings}
    for official in receipt.findings:
        if official.finding_id not in by_id:
            continue
        extended = by_id[official.finding_id]
        assert extended.official.severity == official.severity
        assert extended.official.explanation == official.explanation
        assert extended.official.severity != "PASS"
    assert report.readiness_summary.max_official_severity == "ATTENTION"
    assert report.readiness_summary.error_count == 0
    assert report.source.official_html_sha256 == MUSIC_CENTER_OFFICIAL_HTML_SHA256
    assert report.source.official_html_sha256 != html_sha256(OFFICIAL_HTML_FIXTURE)
    assert report.source.official_html_ref == MUSIC_CENTER_HTML_REF


def test_error_cannot_be_downgraded_or_routed_to_fitting() -> None:
    receipt = _receipt(
        _finding(
            finding_id="DATA_ADEQUACY.OVERALL.NONE.ERROR.01",
            check_type="DATA_ADEQUACY",
            report_category="spend_and_media_unit",
            severity="ERROR",
            explanation="Official Meridian rejected data adequacy.",
        )
    )
    report = _compile(receipt)
    assert report.readiness_summary.official_gate_status == "FAIL"
    assert report.readiness_summary.official_gate_outcome == "EDA_BLOCKED"
    assert report.readiness_summary.max_official_severity == "ERROR"
    assert report.findings[0].official.severity == "ERROR"
    types = {item.action_type.value for item in report.recommended_next_steps}
    assert "RESOLVE_EDA_ERROR" in types
    assert "PROCEED_TO_MODEL_DESIGN" not in types


def test_attention_cannot_become_pass() -> None:
    receipt = _receipt(
        _finding(
            finding_id="STANDARD_DEVIATION.GEO.OUTLIER.ATTENTION.01",
            check_type="STANDARD_DEVIATION",
            report_category="individual_variables",
            severity="ATTENTION",
            finding_cause="OUTLIER",
            explanation="Official Meridian ATTENTION on geo outlier.",
        )
    )
    report = _compile(receipt)
    assert report.findings[0].official.severity == "ATTENTION"
    assert report.readiness_summary.official_gate_status == "PASS"
    assert report.readiness_summary.review_recommended is True
    assert "PASS" not in {item.official.severity for item in report.findings}


def test_interpretation_requires_evidence_refs_and_labels_business_iq() -> None:
    report = compile_music_center_extended_report()
    interpreted = [item for item in report.findings if item.prem3 is not None]
    assert interpreted
    for item in interpreted:
        assert item.prem3.evidence_refs
        assert any(item.finding_id in ref for ref in item.prem3.evidence_refs)
    labels = {fact.label for fact in report.business_context.labeled_facts}
    assert "BUSINESS_IQ_CONTEXT" in labels
    assert "DATA_FOUNDATION_CONTEXT" in labels
    joined = " ".join(fact.statement for fact in report.business_context.labeled_facts)
    assert "demand capture" in joined


def test_agent_outage_does_not_block_official_gate() -> None:
    receipt = music_center_receipt()
    gate_before = evaluate_meridian_eda_gate(receipt=receipt, html_persisted=True)
    report = _compile(
        receipt,
        interpreter=_BoomInterpreter(),
        business_context=music_center_business_context(),
    )
    gate_after = evaluate_meridian_eda_gate(receipt=receipt, html_persisted=True)
    assert gate_before["status"] == gate_after["status"] == "PASS"
    assert gate_after["outcome"] == "PRE_MODELING_COMPLETE"
    assert report.status.value in {"PARTIAL", "FAILED_INTERPRETATION"}
    assert report.readiness_summary.official_gate_outcome == "PRE_MODELING_COMPLETE"


def test_recommendation_does_not_create_approved_model_decision() -> None:
    report = compile_music_center_extended_report()
    service = MMMModelingService()
    version = service.start_design(
        tenant_id="ten_a",
        project_id="wsp_a",
        cycle_id=MUSIC_CENTER_CYCLE_ID,
        track_id="trk_mmm",
        actor_id="tester",
        model_ready_run_id="run_mr",
        model_ready_manifest_fingerprint=MUSIC_CENTER_FP,
        model_window_start=MUSIC_CENTER_WINDOW[0],
        model_window_end=MUSIC_CENTER_WINDOW[1],
        scope="GEO",
        media_channels=MEDIA,
        eda_handoff=report.model_design_handoff,
    )
    decisions = service.repo.list_decisions(version.model_version_id)
    assert decisions
    assert all(item.status.value == "PENDING" for item in decisions)
    brief = service.repo.get_brief(version.model_version_id)
    assert brief is not None
    assert any(ref.startswith("eda_report:") for ref in brief.evidence_refs)
    plan = service.repo.get_plan(version.model_version_id)
    assert plan is not None
    assert plan.spec.knots is None
    assert plan.spec.enable_aks is False


def test_handoff_keeps_open_decisions_pending_and_knot_fallback() -> None:
    report = compile_music_center_extended_report()
    handoff = report.model_design_handoff
    assert any(
        item.implication_type.value == "KNOT_STRATEGY" for item in handoff.modeling_implications
    )
    assert KNOT_FALLBACK_STATEMENT in handoff.known_limitations
    assert all(item.status == "PENDING" for item in handoff.open_modeling_decisions)
    assert all(item.approved_model_change is False for item in handoff.modeling_implications)
    brief = build_design_brief(
        model_version_id="mver_1",
        model_window_start=MUSIC_CENTER_WINDOW[0],
        model_window_end=MUSIC_CENTER_WINDOW[1],
        scope="GEO",
        kpi="orders",
        media_channels=MEDIA,
        rf_channels=(),
        evidence_refs=(MUSIC_CENTER_FP,),
        eda_handoff=handoff,
    )
    assert "KNOT_STRATEGY" in brief.decisions_requiring_human_input
    plan = proposed_model_plan(
        model_plan_id="mplan_1",
        model_version_id="mver_1",
        model_ready_run_id="run_mr",
        model_ready_manifest_fingerprint=MUSIC_CENTER_FP,
        business_profile_snapshot_id=MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
        model_window_start=MUSIC_CENTER_WINDOW[0],
        model_window_end=MUSIC_CENTER_WINDOW[1],
        scope="GEO",
        media_channels=MEDIA,
        rf_channels=(),
    )
    assert plan.spec.knots is None


def test_report_versioning_is_idempotent_until_inputs_change() -> None:
    service = ExtendedEDAService()
    receipt = music_center_receipt()
    kwargs = {
        "tenant_id": "ten_a",
        "project_id": "wsp_a",
        "cycle_id": MUSIC_CENTER_CYCLE_ID,
        "track_id": "trk_mmm",
        "receipt": receipt,
        "official_html": OFFICIAL_HTML_FIXTURE,
        "official_html_ref": OFFICIAL_HTML_FIXTURE_REF,
        "eda_receipt_ref": "receipt",
        "model_ready_fingerprint": MUSIC_CENTER_MODEL_READY_FINGERPRINT,
        "business_context": music_center_business_context(),
        "data_foundation_fingerprint": "df1",
    }
    first = service.compile_and_persist(**kwargs)
    second = service.compile_and_persist(**kwargs)
    assert first.report_id == second.report_id
    assert first.fingerprint == second.fingerprint
    assert first.version == 1
    changed = music_center_business_context().model_copy(
        update={"business_profile_snapshot_id": "bpsnap_new"}
    )
    third = service.compile_and_persist(**{**kwargs, "business_context": changed})
    assert third.version == 2
    assert third.fingerprint != first.fingerprint
    historical = service.repo.get_report(
        tenant_id="ten_a", project_id="wsp_a", report_id=first.report_id
    )
    assert historical is not None
    assert historical.fingerprint == first.fingerprint
    assert historical.business_context.business_profile_snapshot_id == (
        MUSIC_CENTER_BUSINESS_SNAPSHOT_ID
    )


def test_new_receipt_creates_new_version() -> None:
    service = ExtendedEDAService()
    kwargs = {
        "tenant_id": "ten_a",
        "project_id": "wsp_a",
        "cycle_id": "cyc_v",
        "track_id": "trk_mmm",
        "official_html": OFFICIAL_HTML_FIXTURE,
        "official_html_ref": OFFICIAL_HTML_FIXTURE_REF,
        "eda_receipt_ref": "receipt",
    }
    first = service.compile_and_persist(receipt=music_center_receipt(), **kwargs)
    extra = music_center_receipt().model_copy(
        update={
            "findings": list(music_center_receipt().findings)
            + [
                MeridianEDAFinding(
                    finding_id="KPI_INVARIABILITY.OVERALL.VARIABILITY.INFO.99",
                    check_type="KPI_INVARIABILITY",
                    report_category=category_for_check("KPI_INVARIABILITY"),
                    severity="INFO",
                    finding_cause="NONE",
                    explanation="Additional official INFO from a new receipt.",
                )
            ]
        }
    )
    second = service.compile_and_persist(receipt=extra, **kwargs)
    assert second.fingerprint != first.fingerprint
    assert second.source.eda_receipt_fingerprint != first.source.eda_receipt_fingerprint
    assert first.interpretation_policy_version == INTERPRETATION_POLICY_VERSION
    assert first.knowledge_version == knowledge_version()


def test_foreign_project_cannot_read_report_or_html() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant_a, identity_a = seed_tenant(repo, plan_id=PlanId.PROJECT)
    _tenant_b, identity_b = seed_tenant(
        repo,
        display_name="Other",
        provider_org="org_other",
        provider_user="user_other",
        plan_id=PlanId.PROJECT,
    )
    client, _ = make_client(
        repo=repo,
        identities={"test-a": identity_a, "test-b": identity_b},
        identity=identity_a,
    )
    created = client.post(
        "/v1/projects",
        headers=auth_header("test-a"),
        json={"name": "Music Center", "scope_type": "BRAND"},
    ).json()
    project_id = created["project_id"]
    client.app.state.extended_eda.compile_and_persist(
        tenant_id=tenant_a.tenant_id,
        project_id=project_id,
        cycle_id=MUSIC_CENTER_CYCLE_ID,
        track_id="trk_mmm",
        receipt=music_center_receipt(),
        official_html=OFFICIAL_HTML_FIXTURE,
        official_html_ref=OFFICIAL_HTML_FIXTURE_REF,
        eda_receipt_ref="receipt",
        business_context=music_center_business_context(),
    )
    ok = client.get(
        f"/v1/projects/{project_id}/cycles/{MUSIC_CENTER_CYCLE_ID}/mmm/eda",
        headers=auth_header("test-a"),
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["extended_report"]["readiness_summary"]["max_official_severity"] == "ATTENTION"
    assert body["official_report"]["artifact_class"] == TRUSTED_GENERATED_MERIDIAN_HTML
    denied = client.get(
        f"/v1/projects/{project_id}/cycles/{MUSIC_CENTER_CYCLE_ID}/mmm/eda",
        headers=auth_header("test-b"),
    )
    assert denied.status_code == 404
    html_ok = client.get(
        f"/v1/projects/{project_id}/cycles/{MUSIC_CENTER_CYCLE_ID}/mmm/eda/official-html",
        headers=auth_header("test-a"),
    )
    assert html_ok.status_code == 200
    assert html_ok.headers["content-type"].startswith("text/html")
    assert "Content-Security-Policy" in html_ok.headers
    html_denied = client.get(
        f"/v1/projects/{project_id}/cycles/{MUSIC_CENTER_CYCLE_ID}/mmm/eda/official-html",
        headers=auth_header("test-b"),
    )
    assert html_denied.status_code == 404


def test_trusted_html_route_rejects_customer_html() -> None:
    service = ExtendedEDAService()
    report = service.compile_and_persist(
        tenant_id="ten_a",
        project_id="wsp_a",
        cycle_id="cyc_1",
        track_id="trk_mmm",
        receipt=music_center_receipt(),
        official_html=OFFICIAL_HTML_FIXTURE,
        official_html_ref=OFFICIAL_HTML_FIXTURE_REF,
        eda_receipt_ref="receipt",
    )
    service._html[report.source.official_html_sha256] = (
        CUSTOMER_HTML,
        CUSTOMER_UPLOAD_HTML,
        report.source.official_html_ref,
    )
    with pytest.raises(HtmlNotTrustedError):
        service.load_trusted_html(
            tenant_id="ten_a",
            project_id="wsp_a",
            cycle_id="cyc_1",
            artifact_class=CUSTOMER_UPLOAD_HTML,
        )
    inspection = inspect_generated_html(CUSTOMER_HTML, artifact_class=CUSTOMER_UPLOAD_HTML)
    assert inspection.embed_allowed is False
    assert inspection.has_scripts is True


def test_music_center_proof_uses_published_finding_ids() -> None:
    proof = music_center_extended_eda_proof()
    assert proof["source_finding_ids"] == list(MUSIC_CENTER_FINDING_IDS)
    assert proof["official_severity_summary"]["error_count"] == 0
    assert proof["official_severity_summary"]["attention_count"] == 12
    assert proof["official_severity_summary"]["info_count"] == 10
    assert proof["official_severity_summary"]["max_severity"] == "ATTENTION"
    assert proof["knot_fallback_is_not_final_knots"] is True
    assert proof["authority_example"]["severity_unchanged"] is True
    assert proof["mel_evidence"]["can_promote"] is False
    assert proof["official_html_sha256"] == MUSIC_CENTER_OFFICIAL_HTML_SHA256
    assert proof["live_and_fixture_sha_are_distinct"] is True
    assert proof["official_html_embed"]["sandbox"] == "allow-scripts"
    assert "allow-same-origin" not in proof["official_html_embed"]["csp"]
    assert "allow-top-navigation" not in proof["official_html_embed"]["csp"]
    PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    assert loaded["eda_receipt_fingerprint"] == proof["eda_receipt_fingerprint"]
    assert loaded["extended_finding_count"] == proof["extended_finding_count"]
    assert loaded["official_html_sha256"] != loaded["local_html_fixture_sha256"]


def test_live_html_ref_cannot_bind_fixture_bytes() -> None:
    with pytest.raises(HtmlBindingError, match="cannot bind local fixture"):
        _compile(
            music_center_receipt(),
            official_html=OFFICIAL_HTML_FIXTURE,
            official_html_ref=MUSIC_CENTER_HTML_REF,
        )


def test_expected_sha_mismatch_is_rejected() -> None:
    with pytest.raises(HtmlBindingError, match="does not match provided bytes"):
        compile_extended_eda_report(
            tenant_id="ten_a",
            project_id="wsp_a",
            cycle_id="cyc_1",
            track_id="trk_mmm",
            report_id="edarep_mismatch",
            version=1,
            receipt=music_center_receipt(),
            official_html=music_center_official_html(),
            official_html_ref=MUSIC_CENTER_HTML_REF,
            eda_receipt_ref="receipt",
            expected_html_sha256=html_sha256(OFFICIAL_HTML_FIXTURE),
        )


def test_fixture_ref_cannot_bind_live_bytes() -> None:
    with pytest.raises(HtmlBindingError, match="Fixture ref does not match"):
        _compile(
            music_center_receipt(),
            official_html=music_center_official_html(),
            official_html_ref=OFFICIAL_HTML_FIXTURE_REF,
        )


def test_trusted_artifact_substitution_is_rejected() -> None:
    service = ExtendedEDAService()
    report = service.compile_and_persist(
        tenant_id="ten_a",
        project_id="wsp_a",
        cycle_id="cyc_sub",
        track_id="trk_mmm",
        receipt=music_center_receipt(),
        official_html=music_center_official_html(),
        official_html_ref=MUSIC_CENTER_HTML_REF,
        eda_receipt_ref="receipt",
        expected_html_sha256=MUSIC_CENTER_OFFICIAL_HTML_SHA256,
    )
    service._html[report.source.official_html_sha256] = (
        OFFICIAL_HTML_FIXTURE,
        TRUSTED_GENERATED_MERIDIAN_HTML,
        report.source.official_html_ref,
    )
    with pytest.raises(HtmlNotTrustedError, match="SHA-256"):
        service.load_trusted_html(
            tenant_id="ten_a", project_id="wsp_a", cycle_id="cyc_sub"
        )
    service._html[report.source.official_html_sha256] = (
        music_center_official_html(),
        TRUSTED_GENERATED_MERIDIAN_HTML,
        OFFICIAL_HTML_FIXTURE_REF,
    )
    with pytest.raises(HtmlNotTrustedError, match="URI/hash mismatch"):
        service.load_trusted_html(
            tenant_id="ten_a", project_id="wsp_a", cycle_id="cyc_sub"
        )


def test_music_center_official_html_uses_isolated_script_policy() -> None:
    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    client, _ = make_client(repo=repo, identity=identity)
    created = client.post(
        "/v1/projects",
        headers=auth_header(),
        json={"name": "Music Center", "scope_type": "BRAND"},
    ).json()
    project_id = created["project_id"]
    client.app.state.extended_eda.compile_and_persist(
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        cycle_id=MUSIC_CENTER_CYCLE_ID,
        track_id="trk_mmm",
        receipt=music_center_receipt(),
        official_html=music_center_official_html(),
        official_html_ref=MUSIC_CENTER_HTML_REF,
        eda_receipt_ref="receipt",
        expected_html_sha256=MUSIC_CENTER_OFFICIAL_HTML_SHA256,
    )
    response = client.get(
        f"/v1/projects/{project_id}/cycles/{MUSIC_CENTER_CYCLE_ID}/mmm/eda/official-html",
        headers=auth_header(),
    )
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    body = response.content
    assert html_sha256(body) == MUSIC_CENTER_OFFICIAL_HTML_SHA256
    assert b"vegaEmbed" in body
    assert "sandbox allow-scripts" in csp
    assert "allow-same-origin" not in csp
    assert "allow-top-navigation" not in csp
    assert "script-src 'unsafe-inline' https://www.gstatic.com" in csp
    assert "connect-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert response.headers["x-frame-options"] == "SAMEORIGIN"


def test_live_gcs_html_sha_matches_vendored_bytes() -> None:
    vendored = music_center_official_html()
    assert html_sha256(vendored) == MUSIC_CENTER_OFFICIAL_HTML_SHA256
    bucket, _, object_name = MUSIC_CENTER_HTML_REF.removeprefix("gs://").partition("/")
    try:
        from google.cloud import storage

        payload = storage.Client().bucket(bucket).blob(object_name).download_as_bytes()
    except Exception as exc:  # noqa: BLE001 — live GCS is optional in offline CI
        pytest.skip(f"live GCS HTML unavailable: {exc}")
    assert html_sha256(payload) == MUSIC_CENTER_OFFICIAL_HTML_SHA256
    assert payload == vendored
