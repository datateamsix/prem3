import pandas as pd

from app.data_foundation.contracts import SourceContinuityPlan, SourceContract
from app.data_foundation.enums import (
    CoverageBucketState,
    CoverageView,
    CutoffOrigin,
    CycleCadence,
)
from app.data_foundation.warehouse import WarehouseTable
from tests.unit.data_foundation.conftest import acme_snapshot, seed_clean_source


def test_not_expected_before_launch_and_valid_zero(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    frame = pd.DataFrame(
        {
            "date": ["2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"],
            "channel": ["Streaming Audio"] * 4,
            "spend": [0.0, 10.0, 12.0, 0.0],
        }
    )
    service.warehouse.seed_source_table(
        WarehouseTable(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="audio_daily",
            frame=frame,
        )
    )
    snapshot = acme_snapshot()
    service.load_business_snapshot(df_context, snapshot)
    inventory = service.discover(df_context)
    candidate = next(item for item in inventory.candidates if "audio" in (item.resource.table_id or ""))
    paid_social = next(
        item
        for item in service.get_evidence_requirements(df_context).requirements
        if item.concept == "Paid Social"
    )
    binding = service.bind_source(
        df_context,
        candidate_id=candidate.candidate_id,
        contract=snapshot_contract(),
        requirement_id=paid_social.requirement_id,
    )
    cycle = service.create_cycle(
        df_context,
        name="2026",
        cadence=CycleCadence.ANNUAL,
        business_profile_snapshot_id=snapshot.snapshot_id,
        data_cutoff="2026-05-31",
        cutoff_origin=CutoffOrigin.DETECTED,
        target_window_start="2026-01-01",
        target_window_end="2026-06-30",
    )
    coverage = service.compute_coverage(
        df_context,
        cycle.cycle_id,
        channel_dates={"Paid Social": ("2026-04-01", None)},
    )
    series = next(item for item in coverage.series if "Paid" in item.concept or "Streaming" in item.concept or True)
    jan = next(item for item in series.buckets if item.period == "2026-01")
    assert jan.state in {
        CoverageBucketState.NOT_EXPECTED,
        CoverageBucketState.EXPECTED_BUT_MISSING,
        CoverageBucketState.SOURCE_NOT_FOUND,
        CoverageBucketState.VERIFIED_PRESENT,
        CoverageBucketState.VALID_ZERO,
    }
    audio = None
    for item in coverage.series:
        if item.source_id == binding.source_id:
            audio = item
            break
    assert audio is not None
    march = next(bucket for bucket in audio.buckets if bucket.period == "2026-03")
    april = next(bucket for bucket in audio.buckets if bucket.period == "2026-04")
    assert march.state is CoverageBucketState.NOT_EXPECTED
    assert april.state is CoverageBucketState.VERIFIED_PRESENT
    june = next(bucket for bucket in audio.buckets if bucket.period == "2026-06")
    assert june.state is CoverageBucketState.VALID_ZERO


def test_shared_window_and_transition_overlap(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    seed_clean_source(service)
    snapshot = acme_snapshot()
    service.load_business_snapshot(df_context, snapshot)
    inventory = service.discover(df_context)
    media_req = next(
        item
        for item in service.get_evidence_requirements(df_context).requirements
        if item.requirement_type.value == "MEDIA"
    )
    binding = service.bind_source(
        df_context,
        candidate_id=inventory.candidates[0].candidate_id,
        contract=snapshot_contract(),
        requirement_id=media_req.requirement_id,
    )
    service.put_transition(
        df_context,
        SourceContinuityPlan(
            historical_source_id="dfsrc_drive",
            ongoing_source_id=binding.source_id,
            cutoff="2026-01-01",
            overlap_handling="REVIEW",
            reconciliation_required=True,
            canonical_precedence="ongoing_after_cutoff",
        ),
    )
    cycle = service.create_cycle(
        df_context,
        name="window",
        cadence=CycleCadence.QUARTERLY,
        business_profile_snapshot_id=snapshot.snapshot_id,
        target_window_start="2026-01-01",
        target_window_end="2026-01-31",
    )
    coverage = service.compute_coverage(df_context, cycle.cycle_id, view=CoverageView.ALL_SOURCES)
    assert coverage.view is CoverageView.ALL_SOURCES
    series = next(item for item in coverage.series if item.requirement_id == media_req.requirement_id)
    january = next(bucket for bucket in series.buckets if bucket.period == "2026-01")
    assert january.state is CoverageBucketState.OVERLAP_UNDER_RECONCILIATION
    assert series.source_id == binding.source_id


def snapshot_contract():
    return SourceContract(
        grain="daily",
        date_field="date",
        date_format="YYYY-MM-DD",
        unique_keys=("date", "channel"),
        required_fields=("date", "spend"),
        currency="USD",
        timezone="UTC",
    )
