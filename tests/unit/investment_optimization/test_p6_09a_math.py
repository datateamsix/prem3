"""Distribution families, correlation fail-closed, and seeded RNG."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from app.investment_optimization.enums import (
    CorrelationAuthority,
    DistributionAuthority,
    DistributionFamily,
    SimulationSemanticType,
)
from app.investment_optimization.errors import (
    ScenarioCorrelationInvalidError,
    ScenarioDistributionNotGovernedError,
)
from app.investment_optimization.simulation.correlation import (
    apply_iman_conover,
    validate_correlation_spec,
)
from app.investment_optimization.simulation.distributions import pin_variable, sample_variable
from app.investment_optimization.simulation.models import ScenarioCorrelationSpec
from app.investment_optimization.simulation.sampling import parent_generator


def _sample(family, parameters, *, seed=1, count=32, **kwargs):
    variable = pin_variable(
        semantic_type=kwargs.pop("semantic_type", SimulationSemanticType.DEMAND_MULTIPLIER),
        family=family,
        parameters=parameters,
        source_authority=kwargs.pop("source_authority", DistributionAuthority.USER_APPROVED),
        source_refs=kwargs.pop("source_refs", ("fixture",)),
        **kwargs,
    )
    first = sample_variable(variable, generator=parent_generator(seed), count=count)[0]
    second = sample_variable(variable, generator=parent_generator(seed), count=count)[0]
    other = sample_variable(variable, generator=parent_generator(seed + 1), count=count)[0]
    assert np.allclose(first, second)
    if family is not DistributionFamily.FIXED:
        assert not np.allclose(first, other)
    return first


def test_families_are_seeded() -> None:
    _sample(DistributionFamily.NORMAL, {"mean": 1.0, "std": 0.1})
    _sample(DistributionFamily.LOGNORMAL, {"mean": 0.0, "sigma": 0.2})
    _sample(DistributionFamily.TRIANGULAR, {"low": 0.8, "mode": 1.0, "high": 1.2})
    _sample(
        DistributionFamily.BETA,
        {"a": 2.0, "b": 5.0},
        semantic_type=SimulationSemanticType.VIEWABILITY,
        unit="1",
    )
    _sample(DistributionFamily.DISCRETE, {"values": (0.9, 1.0, 1.1), "weights": (0.2, 0.6, 0.2)})
    fixed = _sample(DistributionFamily.FIXED, {"value": 1.25})
    assert np.allclose(fixed, 1.25)
    _sample(
        DistributionFamily.EMPIRICAL,
        {},
        empirical_samples=(0.9, 1.0, 1.1, 0.95),
        source_authority=DistributionAuthority.HISTORICAL_EMPIRICAL,
    )


def test_ungoverned_distribution_fails() -> None:
    with pytest.raises(ScenarioDistributionNotGovernedError):
        pin_variable(
            semantic_type=SimulationSemanticType.FUTURE_CPM,
            family=DistributionFamily.NORMAL,
            parameters={"mean": 8.0, "std": 1.0},
            source_authority=DistributionAuthority.USER_APPROVED,
            source_refs=(),
        )


def test_impossible_cpm_without_truncate_fails() -> None:
    variable = pin_variable(
        semantic_type=SimulationSemanticType.FUTURE_CPM,
        family=DistributionFamily.NORMAL,
        parameters={"mean": -8.0, "std": 0.1},
        source_authority=DistributionAuthority.DATA_FOUNDATION_DERIVED,
        source_refs=("df:cpm",),
        unit="USD",
        truncate=False,
    )
    with pytest.raises(ScenarioDistributionNotGovernedError):
        sample_variable(variable, generator=parent_generator(1), count=16)


def test_correlation_invalid_matrix_fails() -> None:
    created = datetime.now(UTC)
    spec = ScenarioCorrelationSpec(
        correlation_spec_id="oscor_x",
        tenant_id="t",
        project_id="p",
        authority=CorrelationAuthority.USER_APPROVED_CORRELATION,
        variable_ids=("a", "b"),
        matrix=((1.0, 0.2), (0.3, 1.0)),
        fingerprint="fp",
        created_at=created,
    )
    with pytest.raises(ScenarioCorrelationInvalidError):
        validate_correlation_spec(spec)
    diagonal = ScenarioCorrelationSpec(
        correlation_spec_id="oscor_y",
        tenant_id="t",
        project_id="p",
        authority=CorrelationAuthority.USER_APPROVED_CORRELATION,
        variable_ids=("a", "b"),
        matrix=((0.5, 0.0), (0.0, 0.5)),
        fingerprint="fp2",
        created_at=created,
    )
    with pytest.raises(ScenarioCorrelationInvalidError):
        validate_correlation_spec(diagonal)
    bounds = ScenarioCorrelationSpec(
        correlation_spec_id="oscor_z",
        tenant_id="t",
        project_id="p",
        authority=CorrelationAuthority.USER_APPROVED_CORRELATION,
        variable_ids=("a", "b"),
        matrix=((1.0, 1.5), (1.5, 1.0)),
        fingerprint="fp3",
        created_at=created,
    )
    with pytest.raises(ScenarioCorrelationInvalidError):
        validate_correlation_spec(bounds)
    npsd = ScenarioCorrelationSpec(
        correlation_spec_id="oscor_w",
        tenant_id="t",
        project_id="p",
        authority=CorrelationAuthority.USER_APPROVED_CORRELATION,
        variable_ids=("a", "b"),
        matrix=((1.0, 0.99), (0.99, 1.0)),
        fingerprint="fp4",
        created_at=created,
    )
    validate_correlation_spec(npsd)
    bad_psd = ScenarioCorrelationSpec(
        correlation_spec_id="oscor_v",
        tenant_id="t",
        project_id="p",
        authority=CorrelationAuthority.USER_APPROVED_CORRELATION,
        variable_ids=("a", "b", "c"),
        matrix=((1.0, 0.9, -0.9), (0.9, 1.0, 0.9), (-0.9, 0.9, 1.0)),
        fingerprint="fp5",
        created_at=created,
    )
    with pytest.raises(ScenarioCorrelationInvalidError):
        validate_correlation_spec(bad_psd)
    derived = ScenarioCorrelationSpec(
        correlation_spec_id="oscor_derived",
        tenant_id="t",
        project_id="p",
        authority=CorrelationAuthority.MODEL_DERIVED,
        variable_ids=("a", "b"),
        matrix=((1.0, 0.1), (0.1, 1.0)),
        fingerprint="fp6",
        created_at=created,
    )
    with pytest.raises(ScenarioCorrelationInvalidError):
        validate_correlation_spec(derived)


def test_iman_conover_is_deterministic() -> None:
    spec = ScenarioCorrelationSpec(
        correlation_spec_id="oscor_ic",
        tenant_id="t",
        project_id="p",
        authority=CorrelationAuthority.USER_APPROVED_CORRELATION,
        variable_ids=("a", "b"),
        matrix=((1.0, 0.6), (0.6, 1.0)),
        fingerprint="fp_ic",
        created_at=datetime.now(UTC),
    )
    validate_correlation_spec(spec)
    marginals = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    first = apply_iman_conover(marginals, spec, generator=parent_generator(9))
    second = apply_iman_conover(marginals, spec, generator=parent_generator(9))
    other = apply_iman_conover(marginals, spec, generator=parent_generator(10))
    assert np.allclose(first, second)
    assert not np.allclose(first, other)
