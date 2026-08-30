"""Correlation governance. Invalid matrices are not repaired.

Joint sampling uses Iman–Conover rank reordering via a Cholesky factor of the
approved correlation matrix (ADR-P6-088). No generalized copula framework.
"""

from __future__ import annotations

import numpy as np
from numpy.random import Generator

from app.investment_optimization.enums import CorrelationAuthority
from app.investment_optimization.errors import ScenarioCorrelationInvalidError
from app.investment_optimization.simulation.models import ScenarioCorrelationSpec


def validate_correlation_spec(spec: ScenarioCorrelationSpec) -> None:
    if spec.authority is CorrelationAuthority.INDEPENDENT:
        return
    if spec.authority is CorrelationAuthority.MODEL_DERIVED and not spec.model_derived_artifact_ref:
        raise ScenarioCorrelationInvalidError(
            "MODEL_DERIVED correlation requires a pinned artifact."
        )
    size = len(spec.variable_ids)
    if size < 2:
        raise ScenarioCorrelationInvalidError("Non-independent correlation requires two variables.")
    if len(spec.matrix) != size or any(len(row) != size for row in spec.matrix):
        raise ScenarioCorrelationInvalidError("Correlation matrix does not match the variable set.")
    matrix = np.array(spec.matrix, dtype=float)
    if not np.allclose(matrix, matrix.T, atol=1e-9):
        raise ScenarioCorrelationInvalidError("Correlation matrix must be symmetric.")
    if not np.allclose(np.diag(matrix), np.ones(size), atol=1e-9):
        raise ScenarioCorrelationInvalidError("Correlation matrix diagonal must be unit.")
    if np.any(matrix < -1.0 - 1e-9) or np.any(matrix > 1.0 + 1e-9):
        raise ScenarioCorrelationInvalidError("Correlation coefficients must be in [-1, 1].")
    eigenvalues = np.linalg.eigvalsh((matrix + matrix.T) / 2.0)
    if np.any(eigenvalues < -1e-8):
        raise ScenarioCorrelationInvalidError("Correlation matrix is not positive semidefinite.")


def cholesky_factor(matrix: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as exc:
        raise ScenarioCorrelationInvalidError(
            "Correlation matrix is not positive semidefinite."
        ) from exc


def apply_iman_conover(
    marginals: np.ndarray,
    spec: ScenarioCorrelationSpec,
    *,
    generator: Generator,
) -> np.ndarray:
    """Reorder independent marginals to match the governed correlation."""
    validate_correlation_spec(spec)
    if spec.authority is CorrelationAuthority.INDEPENDENT:
        return marginals
    matrix = np.array(spec.matrix, dtype=float)
    factor = cholesky_factor(matrix)
    count, width = marginals.shape
    scores = generator.standard_normal((count, width)) @ factor.T
    ranked = np.empty_like(marginals)
    for column in range(width):
        order = np.argsort(scores[:, column])
        ranked[order, column] = np.sort(marginals[:, column])
    return ranked
