"""Music Center Dataset A EDA fixture from published finding IDs. No invented findings."""

from __future__ import annotations

from pathlib import Path

from app.core.meridian_eda_contracts import (
    EDA_MODEL_SPEC_GEO_TIME_INVARIANT,
    PINNED_GOOGLE_MERIDIAN,
    MeridianEDACompatibilityEvent,
    MeridianEDADataAdequacy,
    MeridianEDAFinding,
    MeridianEDAModelSpecContext,
    MeridianEDAReceipt,
    category_for_check,
)
from app.eda.extended_contracts import (
    CONTEXT_LABEL_BUSINESS_IQ,
    CONTEXT_LABEL_DATA_FOUNDATION,
    CONTEXT_LABEL_MODEL_READY,
    ExtendedEDABusinessContext,
    LabeledContextFact,
)
from app.eda.html_trust import html_sha256

MUSIC_CENTER_RUN_ID = "m3cloud653724094004"
MUSIC_CENTER_HTML_REF = (
    "gs://modelready-m3-912257136465-artifacts/music-center/mmm-demo/runs/"
    f"{MUSIC_CENTER_RUN_ID}/eda/meridian_eda_report.html"
)
MUSIC_CENTER_OFFICIAL_HTML_SHA256 = (
    "371287f4ba0906fa3a9e5956c9bbf180497e7dfa66bbf01f292bb24cc01266fb"
)
MUSIC_CENTER_OFFICIAL_HTML_PATH = (
    Path(__file__).resolve().parents[2]
    / "evaluation"
    / "fixtures"
    / "music_center_meridian_eda_report.html"
)
MUSIC_CENTER_RECEIPT_REF = (
    "gs://modelready-m3-912257136465-artifacts/music-center/mmm-demo/runs/"
    f"{MUSIC_CENTER_RUN_ID}/eda/meridian_eda_receipt.json"
)
MUSIC_CENTER_MODEL_READY_REF = (
    "gs://modelready-m3-912257136465-artifacts/music-center/mmm-demo/runs/"
    f"{MUSIC_CENTER_RUN_ID}/model_ready_manifest.json"
)
MUSIC_CENTER_DATASET_FINGERPRINT = (
    "7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f"
)
MUSIC_CENTER_MODEL_READY_FINGERPRINT = "mc-q3-2026-model-ready-fingerprint"
MUSIC_CENTER_BUSINESS_SNAPSHOT_ID = "bpsnap_music_center_dataset_a"
MUSIC_CENTER_CYCLE_ID = "cyc_q3_2026"

# Published Music Center official finding IDs from evaluation/dataset_a_cloud_run_bundle.json.
MUSIC_CENTER_FINDING_IDS = (
    "DATA_ADEQUACY.OVERALL.NONE.INFO.01",
    "KPI_INVARIABILITY.NA.NONE.INFO.01",
    "PAIRWISE_CORRELATION.NA.NONE.INFO.01",
    "MULTICOLLINEARITY.NA.NONE.INFO.01",
    "STANDARD_DEVIATION.GEO.OUTLIER.ATTENTION.01",
    "STANDARD_DEVIATION.GEO.VARIABILITY.ATTENTION.01",
    "STANDARD_DEVIATION.GEO.OUTLIER.ATTENTION.02",
    "COST_PER_MEDIA_UNIT.GEO.OUTLIER.ATTENTION.01",
    "PRIOR_PROBABILITY.OVERALL.NONE.INFO.01",
    "POPULATION_CORRELATION.OVERALL.NONE.INFO.01",
    "POPULATION_CORRELATION.OVERALL.NONE.INFO.02",
    "VARIABLE_GEO_TIME_COLLINEARITY.NA.NONE.INFO.01",
    "VARIABLE_GEO_TIME_COLLINEARITY.NA.NONE.INFO.02",
    "COST_PER_MEDIA_UNIT.NATIONAL.OUTLIER.ATTENTION.01",
    "STANDARD_DEVIATION.NATIONAL.OUTLIER.ATTENTION.01",
    "STANDARD_DEVIATION.NATIONAL.VARIABILITY.ATTENTION.01",
    "STANDARD_DEVIATION.NATIONAL.OUTLIER.ATTENTION.02",
    "PAIRWISE_CORRELATION.NA.NONE.INFO.02",
    "COST_PER_MEDIA_UNIT.GEO.OUTLIER.ATTENTION.02",
    "STANDARD_DEVIATION.GEO.OUTLIER.ATTENTION.03",
    "STANDARD_DEVIATION.GEO.VARIABILITY.ATTENTION.02",
    "STANDARD_DEVIATION.GEO.OUTLIER.ATTENTION.04",
)

MUSIC_CENTER_COMPAT_ERROR = (
    "The following controls variables do not vary across geos, "
    "making a model with n_knots=n_time unidentifiable: "
    "[b'music_center_promo']"
)

OFFICIAL_HTML_FIXTURE = (
    b"<!DOCTYPE html><html><head><title>Meridian EDA Report</title></head>"
    b"<body><h1>Meridian EDA Report</h1>"
    b"<p>Official generated Meridian EDA. Not a PreM3 reskin.</p></body></html>"
)
OFFICIAL_HTML_FIXTURE_REF = "prem3-fixture://meridian_eda_report.html"


def music_center_official_html() -> bytes:
    payload = MUSIC_CENTER_OFFICIAL_HTML_PATH.read_bytes()
    digest = html_sha256(payload)
    if digest != MUSIC_CENTER_OFFICIAL_HTML_SHA256:
        raise ValueError("Vendored Music Center HTML does not match the pinned live SHA-256.")
    return payload


def known_official_html_sha256() -> dict[str, str]:
    return {MUSIC_CENTER_HTML_REF: MUSIC_CENTER_OFFICIAL_HTML_SHA256}


def _parse_finding_id(finding_id: str) -> tuple[str, str | None, str, str]:
    check_type, level, cause, severity, _seq = finding_id.split(".")
    analysis_level = None if level == "NA" else level
    return check_type, analysis_level, cause, severity


def music_center_finding(finding_id: str) -> MeridianEDAFinding:
    check_type, analysis_level, cause, severity = _parse_finding_id(finding_id)
    explanation = (
        f"Official Meridian {check_type} {severity} finding {finding_id}."
    )
    if "VARIABLE_GEO_TIME_COLLINEARITY" in finding_id:
        explanation = MUSIC_CENTER_COMPAT_ERROR
    return MeridianEDAFinding(
        finding_id=finding_id,
        check_type=check_type,
        report_category=category_for_check(check_type),
        severity=severity,
        finding_cause=cause,
        explanation=explanation,
        analysis_level=analysis_level,
        affected_variables=["music_center_promo"]
        if check_type == "VARIABLE_GEO_TIME_COLLINEARITY"
        else [],
    )


def music_center_receipt() -> MeridianEDAReceipt:
    findings = [music_center_finding(item) for item in MUSIC_CENTER_FINDING_IDS]
    errors = sum(item.severity == "ERROR" for item in findings)
    attention = sum(item.severity == "ATTENTION" for item in findings)
    info = sum(item.severity == "INFO" for item in findings)
    return MeridianEDAReceipt(
        run_id=MUSIC_CENTER_RUN_ID,
        html_report_uri=MUSIC_CENTER_HTML_REF,
        meridian={"version": PINNED_GOOGLE_MERIDIAN},
        model_input_fingerprint=MUSIC_CENTER_DATASET_FINGERPRINT,
        posterior_sampling=False,
        model_fitted=False,
        findings=findings,
        severity_summary={
            "error_count": errors,
            "attention_count": attention,
            "info_count": info,
            "max_severity": "ATTENTION",
        },
        status="EDA_COMPLETE",
        model_spec=MeridianEDAModelSpecContext(
            source=EDA_MODEL_SPEC_GEO_TIME_INVARIANT,
            knots=130,
            n_knots=130,
            n_time=131,
            enable_aks=False,
            approved_for_final_modeling=False,
            reason=MUSIC_CENTER_COMPAT_ERROR,
        ),
        data_adequacy=MeridianEDADataAdequacy(
            n_geos=4,
            n_times=131,
            n_knots=130,
            n_controls=3,
            n_treatments=4,
            n_parameters=80,
            n_data_points=524,
            ratio=80 / 524,
            source_artifact_ref="DATA_ADEQUACY.OVERALL.01",
        ),
        compatibility_event=MeridianEDACompatibilityEvent(
            official_error=MUSIC_CENTER_COMPAT_ERROR,
            condition={
                "geo_model": True,
                "n_time": 131,
                "time_only_variables": ["music_center_promo"],
            },
            default_model_spec={"knots": None, "effective_knots": 131},
            eda_model_spec={"knots": 130},
        ),
    )


def music_center_business_context() -> ExtendedEDABusinessContext:
    return ExtendedEDABusinessContext(
        business_profile_snapshot_id=MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
        primary_business_outcome="orders",
        markets=("CA", "FL", "NY", "TX"),
        material_channels=("paid_search", "shopping", "paid_social"),
        material_drivers=("promotions", "seasonality"),
        labeled_facts=(
            LabeledContextFact(
                label=CONTEXT_LABEL_BUSINESS_IQ,
                statement="Paid Search is primarily demand capture for Music Center.",
                source_ref=MUSIC_CENTER_BUSINESS_SNAPSHOT_ID,
            ),
            LabeledContextFact(
                label=CONTEXT_LABEL_DATA_FOUNDATION,
                statement=(
                    "Shared usable weekly coverage is 2024-01-01/2026-06-29 "
                    "across CA, FL, NY, TX. Dataset A fingerprint "
                    f"{MUSIC_CENTER_DATASET_FINGERPRINT}."
                ),
                source_ref=MUSIC_CENTER_DATASET_FINGERPRINT,
            ),
            LabeledContextFact(
                label=CONTEXT_LABEL_MODEL_READY,
                statement=(
                    "MODEL_READY is already established for this run. Q3 2026 is the "
                    "Measurement Cycle, not the MMM model window."
                ),
                source_ref=MUSIC_CENTER_MODEL_READY_FINGERPRINT,
            ),
        ),
    )


def music_center_foundation_facts() -> tuple[LabeledContextFact, ...]:
    return music_center_business_context().labeled_facts
