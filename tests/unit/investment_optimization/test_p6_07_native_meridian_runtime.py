"""Live google-meridian==1.8.0 proof for P6-07. Default CI skips when uninstalled."""

from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.investment_optimization.adapter import NativeMeridianFixedBudgetAdapter
from app.investment_optimization.compile_native import compile_native_spec
from app.investment_optimization.contracts import OptimizerBudgetVector
from app.investment_optimization.enums import (
    PINNED_MERIDIAN_RUNTIME,
    PINNED_OPTIMIZER_GTOL,
    OptimizationBudgetMode,
    OptimizationObjectiveMode,
)
from app.tools.meridian_eda_runtime import meridian_available
from tests.unit.investment_optimization.p6_07_support import budget_line

REQUIRED_OPTIMIZE_PARAMS = (
    "new_data",
    "use_posterior",
    "selected_geos",
    "start_date",
    "end_date",
    "fixed_budget",
    "budget",
    "pct_of_spend",
    "spend_constraint_lower",
    "spend_constraint_upper",
    "target_roi",
    "target_mroi",
    "gtol",
    "use_kpi",
)


def _require_meridian_1_8_0():
    if not meridian_available():
        pytest.skip("google-meridian is not installed in this interpreter")
    import meridian
    from meridian.analysis.optimizer import BudgetOptimizer

    version = getattr(meridian, "__version__", None)
    assert version == PINNED_MERIDIAN_RUNTIME == "1.8.0"
    return meridian, BudgetOptimizer


def _vector() -> OptimizerBudgetVector:
    return OptimizerBudgetVector(
        currency="USD",
        fixed_budget=Decimal("100.00"),
        lines=(budget_line(),),
    )


def _fake_results() -> SimpleNamespace:
    import xarray as xr

    dataset = xr.Dataset(
        {"spend": ("channel", [90.0])},
        coords={"channel": ["search_spend"]},
    )
    return SimpleNamespace(optimized_data=dataset)


def _spy_optimize(monkeypatch, BudgetOptimizer, captured: list[dict[str, object]]):
    from meridian.analysis import optimizer as opt_mod

    original = BudgetOptimizer.optimize

    def fake_init(self, meridian=None, *, analyzer=None) -> None:
        self.meridian = meridian
        self.analyzer = analyzer

    def fake_optimize(self, **kwargs):
        captured.append(kwargs)
        opt_mod._validate_budget(
            bool(kwargs.get("fixed_budget", True)),
            kwargs.get("budget"),
            kwargs.get("target_roi"),
            kwargs.get("target_mroi"),
        )
        inspect.signature(original).bind(self, **kwargs)
        return _fake_results()

    monkeypatch.setattr(BudgetOptimizer, "__init__", fake_init)
    monkeypatch.setattr(BudgetOptimizer, "optimize", fake_optimize)
    monkeypatch.setattr(
        "meridian.schema.serde.meridian_serde.load_meridian",
        lambda path: object(),
    )


@pytest.mark.meridian_eda
def test_installed_meridian_flexible_interface_matches_compile_native() -> None:
    meridian, BudgetOptimizer = _require_meridian_1_8_0()
    from meridian.analysis.tensors import DataTensors

    params = inspect.signature(BudgetOptimizer.optimize).parameters
    for name in REQUIRED_OPTIMIZE_PARAMS:
        assert name in params
    assert "B_min" not in params
    assert "B_max" not in params
    assert "media_spend" in DataTensors.__annotations__
    assert "revenue_per_kpi" in DataTensors.__annotations__
    del meridian

    spec = compile_native_spec(
        vector=_vector(),
        mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        budget_mode=OptimizationBudgetMode.FLEXIBLE,
        constraint_set=None,
        assumptions=None,
        target_roi=2.0,
        target_mroi=None,
        use_kpi=True,
    )
    assert spec.fixed_budget is False
    assert spec.budget is None
    assert spec.target_roi == 2.0
    assert spec.target_mroi is None
    assert spec.gtol == PINNED_OPTIMIZER_GTOL == 0.0001
    inspect.signature(BudgetOptimizer.optimize).bind(
        object(),
        use_posterior=spec.use_posterior,
        fixed_budget=spec.fixed_budget,
        pct_of_spend=list(spec.pct_of_spend),
        spend_constraint_lower=spec.spend_constraint_lower,
        spend_constraint_upper=spec.spend_constraint_upper,
        gtol=spec.gtol,
        use_kpi=spec.use_kpi,
        target_roi=spec.target_roi,
    )


@pytest.mark.meridian_eda
def test_optimize_flexible_budget_reaches_native_interface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, BudgetOptimizer = _require_meridian_1_8_0()
    captured: list[dict[str, object]] = []
    _spy_optimize(monkeypatch, BudgetOptimizer, captured)
    artifact = tmp_path / "accepted.binpb"
    artifact.write_bytes(b"fixture")
    spec = compile_native_spec(
        vector=_vector(),
        mode=OptimizationObjectiveMode.TARGET_ROI_FLEXIBLE_BUDGET,
        budget_mode=OptimizationBudgetMode.FLEXIBLE,
        constraint_set=None,
        assumptions=None,
        target_roi=2.0,
        target_mroi=None,
        use_kpi=True,
    )
    raw = NativeMeridianFixedBudgetAdapter().optimize_flexible_budget(
        model_artifact_ref=str(artifact),
        vector=_vector(),
        spec=spec,
    )
    assert captured
    kwargs = captured[0]
    assert kwargs["fixed_budget"] is False
    assert "budget" not in kwargs
    assert kwargs["target_roi"] == 2.0
    assert "target_mroi" not in kwargs
    assert kwargs["use_posterior"] is True
    assert kwargs["gtol"] == 0.0001
    assert kwargs["use_kpi"] is True
    assert raw.channels[0].model_variable_id == "search_spend"


@pytest.mark.meridian_eda
def test_optimize_fixed_budget_remains_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, BudgetOptimizer = _require_meridian_1_8_0()
    captured: list[dict[str, object]] = []
    _spy_optimize(monkeypatch, BudgetOptimizer, captured)
    artifact = tmp_path / "accepted.binpb"
    artifact.write_bytes(b"fixture")
    raw = NativeMeridianFixedBudgetAdapter().optimize_fixed_budget(
        model_artifact_ref=str(artifact),
        vector=_vector(),
    )
    assert captured
    kwargs = captured[0]
    assert kwargs["fixed_budget"] is True
    assert kwargs["budget"] == 100.0
    assert "target_roi" not in kwargs
    assert "target_mroi" not in kwargs
    assert kwargs["use_posterior"] is True
    assert kwargs["spend_constraint_lower"] == 0.3
    assert kwargs["spend_constraint_upper"] == 0.3
    assert kwargs["gtol"] == 0.0001
    assert raw.channels[0].recommended_spend == 90.0
    source = inspect.getsource(NativeMeridianFixedBudgetAdapter.optimize_fixed_budget)
    assert "fixed_budget=True" in source
