"""Shapley compute preflight — fail closed on unbounded coalitions."""

from __future__ import annotations

from math import comb

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import ShapleyPreflight, ShapleyPreflightState


def estimate_shapley_work(
    *,
    distinct_channel_count: int,
    size: int | None,
    order_aware: bool,
) -> int:
    n = distinct_channel_count
    k = size if size is not None else n
    k = max(0, min(k, n))
    total = sum(comb(n, i) for i in range(0, k + 1))
    if order_aware:
        # Order-aware expands work roughly by factorial of coalition size upper bound.
        # Use a conservative multiplier for preflight only.
        total *= max(1, k)
    return int(total)


def run_shapley_preflight(
    *,
    distinct_channel_count: int,
    max_path_length: int | None = None,
    p95_path_length: float | None = None,
    configured_size: int | None = None,
    order_aware: bool = False,
    grouped_path_count: int | None = None,
    soft_channel_limit: int = 12,
    hard_channel_limit: int = 20,
    work_review_threshold: int = 50_000,
    work_block_threshold: int = 500_000,
) -> ShapleyPreflight:
    notes: list[str] = []
    truncation_size = None
    work = estimate_shapley_work(
        distinct_channel_count=distinct_channel_count,
        size=configured_size,
        order_aware=order_aware,
    )
    compute_class = "SMALL"
    if work >= work_block_threshold or distinct_channel_count > hard_channel_limit:
        state = ShapleyPreflightState.NOT_RECOMMENDED
        compute_class = "BLOCKED"
        notes.append("Shapley combinatorial work exceeds safe production bounds.")
    elif distinct_channel_count > soft_channel_limit or work >= work_review_threshold:
        if configured_size is not None and configured_size < distinct_channel_count:
            state = ShapleyPreflightState.ELIGIBLE_WITH_TRUNCATION
            truncation_size = configured_size
            compute_class = "TRUNCATED"
            notes.append(
                f"Pinned Shapley size={configured_size}; paths truncated explicitly."
            )
        else:
            state = ShapleyPreflightState.REVIEW_REQUIRED
            compute_class = "REVIEW"
            notes.append(
                "Shapley requires human review or an explicit pinned truncation size."
            )
    else:
        state = ShapleyPreflightState.ELIGIBLE
        if configured_size is not None and configured_size < distinct_channel_count:
            state = ShapleyPreflightState.ELIGIBLE_WITH_TRUNCATION
            truncation_size = configured_size
            notes.append("Pinned Shapley size applies truncation.")

    payload = {
        "state": state.value,
        "distinct_channel_count": distinct_channel_count,
        "configured_size": configured_size,
        "order_aware": order_aware,
        "work": work,
    }
    return ShapleyPreflight(
        state=state,
        distinct_channel_count=distinct_channel_count,
        max_path_length=max_path_length,
        p95_path_length=p95_path_length,
        configured_size=configured_size,
        order_aware=order_aware,
        estimated_combinatorial_work=work,
        grouped_path_count=grouped_path_count,
        compute_class=compute_class,
        truncation_size=truncation_size,
        notes=tuple(notes),
        fingerprint=canonical_fingerprint(payload),
    )
