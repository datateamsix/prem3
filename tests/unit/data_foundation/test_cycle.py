from app.data_foundation.enums import CutoffOrigin, CycleCadence, TargetWindowStatus
from tests.unit.data_foundation.conftest import acme_snapshot


def test_cycle_pins_snapshot_and_provisional_window(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    snapshot = acme_snapshot()
    service.load_business_snapshot(df_context, snapshot)
    cycle = service.create_cycle(
        df_context,
        name="Q1 2026 MMM",
        cadence=CycleCadence.QUARTERLY,
        business_profile_snapshot_id=snapshot.snapshot_id,
        data_cutoff="2026-03-31",
        cutoff_origin=CutoffOrigin.USER_SELECTED,
        target_window_start="2025-01-01",
        target_window_end="2026-03-31",
    )
    assert cycle.target_window_status is TargetWindowStatus.PROVISIONAL
    assert cycle.business_profile_snapshot_id == snapshot.snapshot_id
    updated = service.update_cycle(df_context, cycle.cycle_id, name="Q1 2026 MMM revised")
    assert updated.business_profile_snapshot_id == snapshot.snapshot_id
    try:
        service.update_cycle(
            df_context, cycle.cycle_id, business_profile_snapshot_id="bps_other000000000001"
        )
        raised = False
    except PermissionError:
        raised = True
    assert raised
    listed = service.list_cycles(df_context)
    assert listed[0].cadence is CycleCadence.QUARTERLY


def test_confirmed_cycle_is_immutable_and_revise_creates_new_cycle(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    snapshot = acme_snapshot()
    service.load_business_snapshot(df_context, snapshot)
    cycle = service.create_cycle(
        df_context,
        name="Q1 2026 MMM",
        cadence=CycleCadence.QUARTERLY,
        business_profile_snapshot_id=snapshot.snapshot_id,
        data_cutoff="2026-03-31",
        cutoff_origin=CutoffOrigin.USER_SELECTED,
        target_window_start="2025-01-01",
        target_window_end="2026-03-31",
    )
    confirmed = service.update_cycle(
        df_context,
        cycle.cycle_id,
        target_window_status=TargetWindowStatus.CONFIRMED_DOWNSTREAM,
    )
    assert confirmed.target_window_status is TargetWindowStatus.CONFIRMED_DOWNSTREAM
    try:
        service.update_cycle(df_context, cycle.cycle_id, data_cutoff="2026-04-30")
        raised = False
    except PermissionError:
        raised = True
    assert raised
    revised = service.revise_cycle(
        df_context,
        cycle.cycle_id,
        data_cutoff="2026-04-30",
        target_window_end="2026-04-30",
    )
    assert revised.cycle_id != cycle.cycle_id
    assert revised.predecessor_cycle_id == cycle.cycle_id
    assert revised.revision == cycle.revision + 1
    assert revised.target_window_status is TargetWindowStatus.PROVISIONAL
    assert revised.data_cutoff == "2026-04-30"
    original = service.get_cycle(df_context, cycle.cycle_id)
    assert original.data_cutoff == "2026-03-31"
    assert original.target_window_status is TargetWindowStatus.CONFIRMED_DOWNSTREAM
