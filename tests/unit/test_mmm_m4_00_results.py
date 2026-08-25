"""M4-00 MMM results foundation — adapter, persistence, advisor, API tests."""

from __future__ import annotations

import pytest
from app.modeling.mmm.results.adapter_meridian_180 import (
    Meridian180ResultsAdapter,
    UnsupportedMeridianVersionError,
)
from app.modeling.mmm.results.contracts import (
    MetricAvailability,
    MMMResultStatus,
    RawChannelMetricBundle,
    RawMeridianResultsEvidence,
    ResultProvenance,
)
from app.modeling.mmm.results.fixtures import SYNTHETIC_LABEL, snapshot_fixture
from app.modeling.mmm.results.intelligence import (
    assert_verified_finding_has_typed_evidence,
    compile_decision_intelligence_brief,
)
from app.modeling.mmm.results.ledger import InMemoryResultLedger
from app.modeling.mmm.results.store import ResultStore, extract_and_persist
from app.modeling.mmm.results.validation import metric_value
from fastapi.testclient import TestClient

from app.modeling.mmm.contracts import DecisionIntelligenceAuthority
from app.modeling.mmm.service import MMMModelingService


class _FakeAnalyzer:
    def __init__(self, *, channels: list[str], missing: set[str] | None = None) -> None:
        self.channels = channels
        self.missing = missing or set()

    def roi(self, use_kpi: bool = False):
        if "roi" in self.missing:
            raise RuntimeError("roi unavailable")
        return [1.4, 1.5, 0.4][: len(self.channels)]

    def incremental_outcome(self, use_kpi: bool = False):
        if "incremental_outcome" in self.missing:
            raise RuntimeError("missing")
        return [1400.0, 1200.0, 200.0][: len(self.channels)]

    def marginal_roi(self, use_kpi: bool = False):
        if "marginal_roi" in self.missing:
            raise RuntimeError("missing")
        return [1.1, 1.4, 0.2][: len(self.channels)]

    def summary_metrics(self, use_kpi: bool = False, confidence_level: float = 0.9):
        class _DS:
            def __init__(self, channels):
                self.coords = {"channel": type("C", (), {"values": channels})()}
                self._data = {
                    "pct_of_contribution": type(
                        "A",
                        (),
                        {
                            "coords": {"channel": type("C", (), {"values": channels})()},
                            "values": [0.4, 0.35, 0.1][: len(channels)],
                        },
                    )(),
                    "spend": type(
                        "A",
                        (),
                        {
                            "coords": {"channel": type("C", (), {"values": channels})()},
                            "values": [1000.0, 800.0, 500.0][: len(channels)],
                        },
                    )(),
                }

            def __contains__(self, name):
                return name in self._data

            def __getitem__(self, name):
                return self._data[name]

        if "summary_metrics" in self.missing:
            raise RuntimeError("missing")
        return _DS(self.channels)

    def response_curves(self, use_kpi: bool = False, confidence_level: float = 0.9):
        if "response_curves" in self.missing:
            raise RuntimeError("missing")

        class _Curve:
            def __init__(self, channels):
                self.coords = {"channel": type("C", (), {"values": channels})()}
                self._channel = None

            def sel(self, mapping):
                self._channel = mapping["channel"]
                return self

            def __getitem__(self, name):
                if name == "spend":
                    return type("A", (), {"values": type("V", (), {"tolist": lambda self: [400.0, 800.0]})()})()
                if name == "incremental_outcome":
                    return type("A", (), {"values": type("V", (), {"tolist": lambda self: [700.0, 1200.0]})()})()
                raise KeyError(name)

        return _Curve(self.channels)


def _provenance(fit_run_id: str = "fit-1", sha: str = "b" * 64) -> ResultProvenance:
    return ResultProvenance(
        model_ready_fingerprint="mr",
        business_profile_snapshot_id="biz",
        data_foundation_fingerprint="df",
        model_plan_fingerprint="mp",
        fit_plan_fingerprint="fp",
        fit_approval_id="fa",
        fit_run_id=fit_run_id,
        model_artifact_sha256=sha,
        review_pack_fingerprint="rp",
    )


def test_adapter_channel_ordering_and_missing_metric():
    adapter = Meridian180ResultsAdapter()
    channels = ("paid_search", "paid_social", "display")
    raw = adapter.extract_from_analyzer(
        _FakeAnalyzer(channels=list(channels), missing={"marginal_roi"}),
        channel_ids=channels,
    )
    assert [c.channel_id for c in raw.channels] == list(channels)
    assert raw.channels[0].roi == 1.4
    assert raw.channels[0].marginal_roi is None
    assert "Analyzer.marginal_roi" in raw.source_methods_unavailable


def test_adapter_unsupported_meridian_version():
    adapter = Meridian180ResultsAdapter()
    with pytest.raises(UnsupportedMeridianVersionError):
        adapter.assert_supported_version("1.7.0")


def test_zero_vs_missing_vs_invalid_metrics():
    zero = metric_value(0.0)
    missing = metric_value(None)
    invalid = metric_value(float("nan"))
    assert zero.availability is MetricAvailability.ZERO
    assert zero.value == 0.0
    assert missing.availability is MetricAvailability.NOT_AVAILABLE
    assert missing.value is None
    assert invalid.availability is MetricAvailability.INVALID
    assert invalid.value is None


def test_interval_ordering_rejection():
    bad = metric_value(1.0, lower=2.0, upper=1.0)
    assert bad.interval is not None
    assert bad.interval.availability is MetricAvailability.INVALID


def test_result_snapshot_idempotent():
    store = ResultStore(ledger=InMemoryResultLedger())
    raw = RawMeridianResultsEvidence(
        meridian_version="1.8.0",
        adapter_version="m4-00.1",
        channels=(
            RawChannelMetricBundle(
                channel_id="paid_search",
                channel_name="Paid Search",
                spend=100.0,
                incremental_outcome=140.0,
                roi=1.4,
                marginal_roi=1.1,
                contribution=0.5,
            ),
        ),
        synthetic=True,
    )
    kwargs = dict(
        store=store,
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        model_version_id="mv1",
        fit_run_id="fit1",
        model_artifact_sha256="c" * 64,
        raw=raw,
        provenance=_provenance("fit1", "c" * 64),
        fit_complete=True,
        model_accepted=False,
        review_pending=True,
        source_runtime="SYNTHETIC_FIXTURE",
        synthetic_label=SYNTHETIC_LABEL,
    )
    first = extract_and_persist(**kwargs)
    second = extract_and_persist(**kwargs)
    assert first.result_snapshot_id == second.result_snapshot_id
    assert first.result_fingerprint == second.result_fingerprint


def test_result_snapshot_new_when_model_artifact_changes():
    store = ResultStore(ledger=InMemoryResultLedger())
    raw = RawMeridianResultsEvidence(
        meridian_version="1.8.0",
        adapter_version="m4-00.1",
        channels=(
            RawChannelMetricBundle(
                channel_id="paid_search",
                channel_name="Paid Search",
                spend=100.0,
                roi=1.4,
                contribution=0.5,
                incremental_outcome=140.0,
                marginal_roi=1.0,
            ),
        ),
        synthetic=True,
    )
    base = dict(
        store=store,
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        model_version_id="mv1",
        fit_run_id="fit1",
        raw=raw,
        fit_complete=True,
        model_accepted=False,
        review_pending=True,
        source_runtime="SYNTHETIC_FIXTURE",
        synthetic_label=SYNTHETIC_LABEL,
    )
    a = extract_and_persist(
        **base, model_artifact_sha256="d" * 64, provenance=_provenance("fit1", "d" * 64)
    )
    b = extract_and_persist(
        **base, model_artifact_sha256="e" * 64, provenance=_provenance("fit1", "e" * 64)
    )
    assert a.result_snapshot_id != b.result_snapshot_id


def test_latest_and_accepted_pointers_are_separate():
    store = ResultStore(ledger=InMemoryResultLedger())
    raw = RawMeridianResultsEvidence(
        meridian_version="1.8.0",
        adapter_version="m4-00.1",
        channels=(
            RawChannelMetricBundle(
                channel_id="paid_search",
                channel_name="Paid Search",
                spend=10.0,
                roi=1.0,
                contribution=0.2,
                incremental_outcome=10.0,
                marginal_roi=0.9,
            ),
        ),
        synthetic=True,
    )
    accepted = extract_and_persist(
        store=store,
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        model_version_id="mv1",
        fit_run_id="fit-accepted",
        model_artifact_sha256="f" * 64,
        raw=raw,
        provenance=_provenance("fit-accepted", "f" * 64),
        fit_complete=True,
        model_accepted=True,
        review_pending=False,
        source_runtime="SYNTHETIC_FIXTURE",
        synthetic_label=SYNTHETIC_LABEL,
    )
    latest = extract_and_persist(
        store=store,
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        model_version_id="mv2",
        fit_run_id="fit-latest",
        model_artifact_sha256="1" * 64,
        raw=raw,
        provenance=_provenance("fit-latest", "1" * 64),
        fit_complete=True,
        model_accepted=False,
        review_pending=True,
        source_runtime="SYNTHETIC_FIXTURE",
        synthetic_label=SYNTHETIC_LABEL,
    )
    pointer = store.get_pointer(tenant_id="t1", project_id="p1", cycle_id="c1")
    assert pointer is not None
    assert pointer.latest_result_snapshot_id == latest.result_snapshot_id
    assert pointer.accepted_result_snapshot_id == accepted.result_snapshot_id
    assert pointer.latest_result_snapshot_id != pointer.accepted_result_snapshot_id


def test_unaccepted_result_never_replaces_accepted_current():
    store = ResultStore(ledger=InMemoryResultLedger())
    raw = RawMeridianResultsEvidence(
        meridian_version="1.8.0",
        adapter_version="m4-00.1",
        channels=(
            RawChannelMetricBundle(
                channel_id="paid_search",
                channel_name="Paid Search",
                spend=10.0,
                roi=1.0,
                contribution=0.2,
                incremental_outcome=10.0,
                marginal_roi=0.9,
            ),
        ),
        synthetic=True,
    )
    accepted = extract_and_persist(
        store=store,
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        model_version_id="mv1",
        fit_run_id="fit-a",
        model_artifact_sha256="2" * 64,
        raw=raw,
        provenance=_provenance("fit-a", "2" * 64),
        fit_complete=True,
        model_accepted=True,
        review_pending=False,
        source_runtime="SYNTHETIC_FIXTURE",
        synthetic_label=SYNTHETIC_LABEL,
    )
    extract_and_persist(
        store=store,
        tenant_id="t1",
        project_id="p1",
        cycle_id="c1",
        model_version_id="mv2",
        fit_run_id="fit-b",
        model_artifact_sha256="3" * 64,
        raw=raw,
        provenance=_provenance("fit-b", "3" * 64),
        fit_complete=True,
        model_accepted=False,
        review_pending=True,
        source_runtime="SYNTHETIC_FIXTURE",
        synthetic_label=SYNTHETIC_LABEL,
    )
    pointer = store.get_pointer(tenant_id="t1", project_id="p1", cycle_id="c1")
    assert pointer.accepted_result_snapshot_id == accepted.result_snapshot_id


def test_firestore_stores_no_large_nested_arrays():
    store = ResultStore(ledger=InMemoryResultLedger())
    snap = snapshot_fixture(name="healthy_completed_fit")
    store.persist_snapshot(snap)
    meta = store.metadata[snap.result_snapshot_id].model_dump(mode="json")
    assert not any(isinstance(value, list) for value in meta.values())


def test_bigquery_result_readback_fingerprint():
    store = ResultStore(ledger=InMemoryResultLedger())
    snap = snapshot_fixture(name="accepted_fit", artifact_sha="4" * 64, fit_run_id="fit-rb")
    stored = store.persist_snapshot(snap)
    assert stored.ledger_readback_verified is True
    row = store.ledger.read_back(
        table="mmm_result_snapshots", result_snapshot_id=stored.result_snapshot_id
    )
    assert isinstance(row, dict)
    assert row["result_fingerprint"] == stored.result_fingerprint


def test_cross_tenant_results_denied():
    store = ResultStore(ledger=InMemoryResultLedger())
    snap = snapshot_fixture(name="accepted_fit", tenant_id="tenant-a", project_id="project-a")
    store.persist_snapshot(snap, update_accepted_pointer=True)
    with pytest.raises(Exception):
        store.mark_accepted(
            tenant_id="tenant-b",
            project_id="project-a",
            cycle_id=snap.cycle_id,
            result_snapshot_id=snap.result_snapshot_id,
        )


def test_historical_results_immutable():
    store = ResultStore(ledger=InMemoryResultLedger())
    first = snapshot_fixture(name="accepted_fit", artifact_sha="5" * 64, fit_run_id="fit-h1")
    store.persist_snapshot(first, update_accepted_pointer=True)
    original_fp = store.get_snapshot(first.result_snapshot_id).result_fingerprint
    # Re-persist same source returns same immutable snapshot.
    again = store.persist_snapshot(first, update_accepted_pointer=True)
    assert again.result_fingerprint == original_fp
    assert store.get_snapshot(first.result_snapshot_id).channels[0].roi.value == first.channels[0].roi.value


def test_verified_finding_requires_typed_evidence():
    snap = snapshot_fixture(name="accepted_fit")
    brief = compile_decision_intelligence_brief(snapshot=snap)
    assert brief.verified_findings
    for finding in brief.verified_findings:
        assert_verified_finding_has_typed_evidence(finding)
        assert finding.authority is DecisionIntelligenceAuthority.VERIFIED
        assert finding.evidence_refs


def test_interpretation_labeled_separately():
    snap = snapshot_fixture(name="accepted_fit")
    brief = compile_decision_intelligence_brief(snapshot=snap)
    assert brief.interpretations
    assert all(
        item.authority is DecisionIntelligenceAuthority.INTERPRETATION
        for item in brief.interpretations
    )


def test_recommendation_requires_accepted_model_by_default():
    unaccepted = snapshot_fixture(name="unaccepted_fit")
    accepted = snapshot_fixture(name="accepted_fit")
    brief_u = compile_decision_intelligence_brief(snapshot=unaccepted)
    brief_a = compile_decision_intelligence_brief(snapshot=accepted)
    assert not any(item.investment_action for item in brief_u.recommendations)
    assert any(item.investment_action for item in brief_a.recommendations)


def test_preacceptance_brief_has_no_investment_action():
    snap = snapshot_fixture(name="with_review")
    brief = compile_decision_intelligence_brief(snapshot=snap)
    assert snap.result_status is MMMResultStatus.FIT_COMPLETE_REVIEW_PENDING
    assert brief.eligibility.value == "PRE_ACCEPTANCE_RESULTS"
    assert not any(item.investment_action for item in brief.recommendations)


def test_recommendation_includes_evidence_refs():
    snap = snapshot_fixture(name="accepted_fit")
    brief = compile_decision_intelligence_brief(snapshot=snap)
    rec = next(item for item in brief.recommendations if item.investment_action)
    assert rec.evidence_refs


def test_counter_evidence_supported():
    snap = snapshot_fixture(name="accepted_fit")
    brief = compile_decision_intelligence_brief(snapshot=snap)
    # paid_social has wide mROI interval in fixture
    assert brief.counter_evidence


def test_missing_metric_not_rendered_as_zero():
    snap = snapshot_fixture(name="missing_mroi")
    for channel in snap.channels:
        assert channel.marginal_roi.availability is MetricAvailability.NOT_AVAILABLE
        assert channel.marginal_roi.value is None
    brief = compile_decision_intelligence_brief(snapshot=snap)
    assert not any(
        "mROI = 0" in item.statement for item in brief.verified_findings
    )


def test_nan_inf_metric_marked_invalid():
    snap = snapshot_fixture(name="nan_inf_metric")
    paid = next(c for c in snap.channels if c.channel_id == "paid_search")
    assert paid.roi.availability is MetricAvailability.INVALID
    assert paid.roi.value is None


def test_results_not_available_before_fit_complete():
    service = MMMModelingService()
    unavailable = service.get_results_for_cycle(
        tenant_id="t1", project_id="p1", cycle_id="c1"
    )
    assert unavailable.status is MMMResultStatus.NOT_AVAILABLE
    assert unavailable.reason.value == "FIT_NOT_COMPLETE"


def test_api_results_routes():
    from app.control_plane.entitlements import PlanId
    from app.control_plane.memory import InMemoryControlPlaneRepository
    from app.service.app import create_app
    from app.service.auth import FakeIdentityVerifier
    from tests.unit.api_support import auth_header, seed_tenant

    repo = InMemoryControlPlaneRepository()
    tenant, identity = seed_tenant(repo, plan_id=PlanId.PROJECT)
    modeling = MMMModelingService()
    app = create_app(
        control_plane_repository=repo,
        identity_verifier=FakeIdentityVerifier(default=identity),
        mmm_modeling=modeling,
    )
    client = TestClient(app, raise_server_exceptions=False)
    headers = auth_header()
    project_id = client.post(
        "/v1/projects",
        headers=headers,
        json={"name": "Results Project", "scope_type": "BRAND"},
    ).json()["project_id"]

    snap = snapshot_fixture(
        name="accepted_fit",
        tenant_id=tenant.tenant_id,
        project_id=project_id,
        cycle_id="cycle-api",
        model_version_id="mv-api",
        fit_run_id="fit-api",
        artifact_sha="6" * 64,
    )
    modeling.result_store.persist_snapshot(snap, update_accepted_pointer=True)
    brief = compile_decision_intelligence_brief(snapshot=snap)
    modeling.result_store.briefs[brief.brief_id] = brief

    results = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-api/mmm/results", headers=headers
    )
    assert results.status_code == 200, results.text
    body = results.json()
    assert body["status"] == "ACCEPTED"
    assert body["acceptance_computed_by_server"] is True
    assert body["recommendation_eligibility_computed_by_server"] is True
    assert body["channel_results"]

    channel = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-api/mmm/results/channels/paid_social",
        headers=headers,
    )
    assert channel.status_code == 200
    assert len(channel.json()["channel_results"]) == 1

    curves = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-api/mmm/results/response-curves",
        headers=headers,
    )
    assert curves.status_code == 200
    assert curves.json()["curves"]

    brief_resp = client.get(
        f"/v1/projects/{project_id}/cycles/cycle-api/mmm/decision-brief", headers=headers
    )
    assert brief_resp.status_code == 200
    assert brief_resp.json()["investment_recommendations_allowed"] is True

    denied = TestClient(
        create_app(
            control_plane_repository=repo,
            identity_verifier=FakeIdentityVerifier(
                default=seed_tenant(
                    InMemoryControlPlaneRepository(),
                    display_name="Other",
                    provider_org="org_other",
                    provider_user="user_other",
                    plan_id=PlanId.PROJECT,
                )[1]
            ),
            mmm_modeling=modeling,
        ),
        raise_server_exceptions=False,
    ).get(f"/v1/projects/{project_id}/cycles/cycle-api/mmm/results", headers=headers)
    assert denied.status_code in {401, 403, 404}


def test_results_preacceptance_and_accepted_status():
    pre = snapshot_fixture(name="unaccepted_fit")
    acc = snapshot_fixture(name="accepted_fit")
    assert pre.result_status is MMMResultStatus.REVIEWED_NOT_ACCEPTED
    assert acc.result_status is MMMResultStatus.ACCEPTED


def test_music_center_has_no_invented_production_results():
    snap = snapshot_fixture(name="healthy_completed_fit")
    assert snap.synthetic is True
    assert snap.synthetic_label == SYNTHETIC_LABEL
    assert snap.source_runtime == "SYNTHETIC_FIXTURE"
