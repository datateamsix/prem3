"""M5-02A real DP6 1.0.11 tests. Fake adapter is never invoked on these paths."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

pytest.importorskip("marketing_attribution_models")
from marketing_attribution_models import MAM

from app.domain.channels import cached_channel_registry
from app.modeling.mta.adapters.dp6_mam_v1_0_11 import (
    DP6_MAM_PINNED_VERSION,
    SHARE_SUM_TOLERANCE,
    DP6MAMAdapter,
    DP6MissingParameterError,
    DP6UnknownChannelError,
    MTAFakeRuntimeNotAllowed,
    assert_pinned_dp6_version,
    assert_real_runtime_allowed,
    installed_dp6_version,
)
from app.modeling.mta.contracts import (
    AttributionModelId,
    GA4SettlementPolicy,
    IdentityStrategy,
    SessionizationPolicy,
    SessionTrafficSourcePolicy,
    ShapleyPreflightState,
)
from app.modeling.mta.dispatch import FakeMTADispatcher
from app.modeling.mta.input_contract import build_input_contract
from app.modeling.mta.runtime_contracts import MTAInputMode
from app.modeling.mta.service import MTAService
from app.modeling.mta.shapley_preflight import run_shapley_preflight

pytest.importorskip("marketing_attribution_models")

pytestmark = pytest.mark.real_dp6

PATHS = [
    ["social_paid", "search_organic", "search_paid"],
    ["display", "search_organic", "direct"],
    ["email", "direct"],
    ["ai_search", "search_organic", "search_paid"],
    ["search_paid"],
    ["direct"],
]
CONVERSIONS = [1.0] * len(PATHS)
DECAY = {"decay_over_time": 7, "frequency": 2}
POSITION = {"first_weight": 0.4, "middle_weight": 0.2, "last_weight": 0.4}
MARKOV = {"transition_to_same_state": False, "conversion_value_as_frequency": True}
SHAPLEY = {"size": 4, "order": True, "values_col": "conversions"}


@pytest.fixture(scope="module")
def real_adapter() -> DP6MAMAdapter:
    adapter = DP6MAMAdapter(fake=False)
    assert adapter.is_fake is False
    return adapter


def _run(adapter: DP6MAMAdapter, model: AttributionModelId, params: dict | None = None):
    return adapter.run_model(
        model,
        paths=PATHS,
        conversions=CONVERSIONS,
        parameters=params or {},
        input_mode=MTAInputMode.RAW_JOURNEYS,
    )


def test_run_real_does_not_delegate_to_fake():
    source = inspect.getsource(DP6MAMAdapter._run_real)
    assert "_run_fake" not in source
    assert "attribution_first_click" in source
    assert "attribution_shapley" in source


def test_dp6_runtime_version_is_exact_1_0_11():
    assert installed_dp6_version() == "1.0.11"
    assert assert_pinned_dp6_version(allow_missing_for_fake=False) == DP6_MAM_PINNED_VERSION


def test_dp6_expected_api_contract():
    assert "but_not_this_channel" in inspect.signature(MAM.attribution_last_click_non).parameters
    assert "decay_over_time" in inspect.signature(MAM.attribution_time_decay).parameters
    assert "frequency" in inspect.signature(MAM.attribution_time_decay).parameters
    assert "list_positions_first_middle_last" in inspect.signature(
        MAM.attribution_position_based
    ).parameters
    assert "transition_to_same_state" in inspect.signature(MAM.attribution_markov).parameters
    assert "conversion_value_as_frequency" in inspect.signature(MAM.attribution_markov).parameters
    shapley = inspect.signature(MAM.attribution_shapley)
    assert shapley.parameters["size"].default == 4
    assert shapley.parameters["order"].default is False
    assert shapley.parameters["values_col"].default == "conv_rate"


def test_worker_image_pins_dp6_1_0_11():
    text = Path("deployment/prem3_mta_worker/requirements.txt").read_text(encoding="utf-8")
    assert "1.0.11" in text
    assert "Marketing-Attribution-Models" in text


def test_real_dp6_first_touch(real_adapter):
    result = _run(real_adapter, AttributionModelId.FIRST_TOUCH)
    assert result.runtime == "DP6_1_0_11"
    assert result.credits
    assert not real_adapter.is_fake


def test_real_dp6_last_touch(real_adapter):
    assert _run(real_adapter, AttributionModelId.LAST_TOUCH).credits


def test_real_dp6_last_non_direct(real_adapter):
    result = _run(real_adapter, AttributionModelId.LAST_NON_DIRECT)
    assert result.credits
    assert result.runtime == "DP6_1_0_11"


def test_real_dp6_linear(real_adapter):
    assert _run(real_adapter, AttributionModelId.LINEAR).credits


def test_real_dp6_time_decay_with_exact_parameters(real_adapter):
    result = _run(real_adapter, AttributionModelId.TIME_DECAY, DECAY)
    assert result.credits
    with pytest.raises(DP6MissingParameterError):
        real_adapter.run_model(
            AttributionModelId.TIME_DECAY, paths=PATHS, conversions=CONVERSIONS, parameters={}
        )


def test_real_dp6_position_based_with_exact_weights(real_adapter):
    result = _run(real_adapter, AttributionModelId.POSITION_BASED, POSITION)
    assert result.credits
    with pytest.raises(DP6MissingParameterError):
        real_adapter.run_model(
            AttributionModelId.POSITION_BASED,
            paths=PATHS,
            conversions=CONVERSIONS,
            parameters={"first_weight": 0.5, "middle_weight": 0.5, "last_weight": 0.5},
        )


def test_real_dp6_markov_channel_credit(real_adapter):
    result = _run(real_adapter, AttributionModelId.MARKOV, MARKOV)
    assert result.markov is not None
    assert result.markov.credits


def test_real_dp6_markov_transition_matrix(real_adapter):
    result = _run(real_adapter, AttributionModelId.MARKOV, MARKOV)
    states = {a for a, _b, _p in result.markov.transitions} | {
        b for _a, b, _p in result.markov.transitions
    }
    assert "(inicio)" in states
    assert "(conversion)" in states
    assert "START" not in states


def test_real_dp6_markov_removal_effects(real_adapter):
    result = _run(real_adapter, AttributionModelId.MARKOV, MARKOV)
    assert result.markov.removal_effects


def test_real_dp6_shapley_credit(real_adapter):
    result = _run(real_adapter, AttributionModelId.SHAPLEY, SHAPLEY)
    assert result.shapley is not None
    assert result.shapley.size == 4
    assert result.shapley.order_aware is True
    assert result.shapley.values_col == "conversions"


def test_shapley_size_parameter_reaches_runtime(real_adapter):
    result = _run(real_adapter, AttributionModelId.SHAPLEY, SHAPLEY)
    assert result.shapley.size == 4


def test_shapley_order_parameter_reaches_runtime(real_adapter):
    result = _run(real_adapter, AttributionModelId.SHAPLEY, {**SHAPLEY, "order": True})
    assert result.shapley.order_aware is True


def test_shapley_values_col_parameter_reaches_runtime(real_adapter):
    result = _run(real_adapter, AttributionModelId.SHAPLEY, SHAPLEY)
    assert result.shapley.values_col == "conversions"


def test_shapley_preflight_still_gates_real_runtime():
    blocked = run_shapley_preflight(
        distinct_channel_count=50, configured_size=None, order_aware=True
    )
    assert blocked.state in {
        ShapleyPreflightState.NOT_RECOMMENDED,
        ShapleyPreflightState.REVIEW_REQUIRED,
    }


def test_shapley_path_limit_is_reported(real_adapter):
    long = [["search_paid", "social_paid", "display", "email", "ai_search", "direct"]]
    result = real_adapter.run_model(
        AttributionModelId.SHAPLEY,
        paths=long,
        conversions=[1.0],
        parameters=SHAPLEY,
    )
    assert result.shapley.path_limit_applied is True
    assert "SHAPLEY_PATH_LIMIT_APPLIED" in result.limitations


def test_grouped_path_frequency_matches_expanded_paths(real_adapter):
    expanded = [
        ["search_paid", "direct"],
        ["search_paid", "direct"],
        ["email", "direct"],
    ]
    grouped_paths = [["search_paid", "direct"], ["email", "direct"]]
    grouped_freq = [2.0, 1.0]
    a = real_adapter.run_model(
        AttributionModelId.MARKOV, paths=expanded, conversions=[1, 1, 1], parameters=MARKOV
    )
    b = real_adapter.run_model(
        AttributionModelId.MARKOV,
        paths=grouped_paths,
        conversions=grouped_freq,
        parameters=MARKOV,
    )
    shares_a = {c.channel_id: c.attribution_share for c in a.credits}
    shares_b = {c.channel_id: c.attribution_share for c in b.credits}
    for channel in set(shares_a) | set(shares_b):
        assert abs(shares_a.get(channel, 0) - shares_b.get(channel, 0)) < 0.05


def test_markov_transition_same_state_parameter_reaches_runtime(real_adapter):
    result = _run(
        real_adapter,
        AttributionModelId.MARKOV,
        {"transition_to_same_state": True, "conversion_value_as_frequency": True},
    )
    assert result.markov is not None


def test_markov_output_channels_are_canonical(real_adapter):
    result = _run(real_adapter, AttributionModelId.MARKOV, MARKOV)
    known = set(cached_channel_registry(1).channel_ids())
    for credit in result.credits:
        assert credit.channel_id in known


def test_real_model_shares_sum_within_tolerance(real_adapter):
    for model, params in (
        (AttributionModelId.FIRST_TOUCH, {}),
        (AttributionModelId.LINEAR, {}),
        (AttributionModelId.MARKOV, MARKOV),
    ):
        result = _run(real_adapter, model, params)
        total = sum(c.attribution_share for c in result.credits)
        assert abs(total - 1.0) <= SHARE_SUM_TOLERANCE


def test_real_model_output_has_no_nan_inf(real_adapter):
    result = _run(real_adapter, AttributionModelId.LINEAR)
    for credit in result.credits:
        assert credit.attributed_credit == credit.attributed_credit
        assert credit.attribution_share not in (float("inf"), float("-inf"))


def test_real_runtime_unknown_channel_fails_closed(real_adapter):
    with pytest.raises(DP6UnknownChannelError):
        real_adapter.run_model(
            AttributionModelId.LAST_TOUCH,
            paths=[["not_a_registry_channel"]],
            conversions=[1.0],
        )


def test_live_execution_cannot_use_fake_adapter():
    with pytest.raises(MTAFakeRuntimeNotAllowed):
        assert_real_runtime_allowed(runtime_mode="LIVE", proof_label="TEST", fake=True)


def test_synthetic_demo_execution_cannot_use_fake_adapter():
    with pytest.raises(MTAFakeRuntimeNotAllowed):
        assert_real_runtime_allowed(
            runtime_mode="SYNTHETIC_DEMO", proof_label="SYNTHETIC_DEMO", fake=True
        )


def test_unit_test_mode_may_use_fake_adapter():
    assert_real_runtime_allowed(runtime_mode="FAKE_TEST", proof_label="SYNTHETIC", fake=True)
    adapter = DP6MAMAdapter(fake=True)
    assert adapter.is_fake is True
    result = adapter.run_model(
        AttributionModelId.FIRST_TOUCH, paths=[["search_paid"]], conversions=[1.0]
    )
    assert result.runtime == "TEST_FAKE_RUNTIME"


def test_fake_runtime_is_explicitly_labeled():
    adapter = DP6MAMAdapter(fake=True)
    result = adapter.run_model(
        AttributionModelId.LINEAR, paths=[["email", "direct"]], conversions=[1.0]
    )
    assert result.runtime == "TEST_FAKE_RUNTIME"
    assert adapter.is_fake is True


def test_service_synthetic_demo_rejects_fake_adapter():
    service = MTAService(
        dispatcher=FakeMTADispatcher(),
        dp6=DP6MAMAdapter(fake=True),
    )
    contract = build_input_contract(
        input_contract_id="ic_guard",
        tenant_id="t",
        project_id="p",
        cycle_id="c",
        track_id="mta",
        ga4_dataset_id="analytics_music_center_synthetic",
        source_schema_version="v1",
        settlement_policy=GA4SettlementPolicy.DAILY_SETTLED,
        conversion_event="purchase",
        conversion_period_start="2024-09-01",
        conversion_period_end="2024-09-30",
        lookback_window_days=30,
        identity_strategy=IdentityStrategy.PSEUDO_ID_ONLY,
        sessionization_policy=SessionizationPolicy.GA4_SESSION_ID_V1,
        traffic_source_policy=SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1,
        channel_grouping_version="v1",
        attribution_models=(AttributionModelId.FIRST_TOUCH,),
    )
    service.repo.put_contract(contract)
    service.evaluate_readiness(
        tenant_id="t",
        project_id="p",
        cycle_id="c",
        track_id="mta",
        contract=contract,
        ga4_dataset_exists=True,
        daily_shards_continuous=True,
        key_event_present=True,
        conversion_volume_ok=True,
        channel_grouping_approved=True,
        unmapped_share_ok=True,
        uses_intraday_for_canonical=False,
        lookback_covered=True,
        user_pseudo_id_coverage=0.99,
    )
    run = service.start_run(
        tenant_id="t",
        project_id="p",
        cycle_id="c",
        track_id="mta",
        journeys=[{"subject_key": "u", "channels": ["search_paid"], "converted": True}],
        proof_label="SYNTHETIC_DEMO",
        runtime_mode="SYNTHETIC_DEMO",
    )
    with pytest.raises(MTAFakeRuntimeNotAllowed):
        service.execute_fit_dispatch(dispatch_id=run.dispatch_id)
