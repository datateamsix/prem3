"""Versioned deterministic MTA result policies: sensitivity, role, position, observability."""

from __future__ import annotations

from statistics import mean, median

from app.modeling.mta.results_contracts import (
    OBSERVABILITY_POLICY_VERSION,
    POSITION_POLICY_SINGLE_TOUCH,
    POSITION_POLICY_VERSION,
    ROLE_POLICY_VERSION,
    SENSITIVITY_POLICY_VERSION,
    ChannelRoleLabel,
    ChannelRolePolicy,
    MTALimitation,
    MTALimitationType,
    MTAModelSensitivityPolicy,
    MTAObservabilitySummary,
    ObservabilityStatus,
    SensitivityLabel,
)

DEFAULT_SENSITIVITY_POLICY = MTAModelSensitivityPolicy()
DEFAULT_ROLE_POLICY = ChannelRolePolicy()


def classify_sensitivity(
    dispersion: float | None,
    *,
    policy: MTAModelSensitivityPolicy | None = None,
) -> SensitivityLabel | None:
    if dispersion is None:
        return None
    policy = policy or DEFAULT_SENSITIVITY_POLICY
    if dispersion < policy.low_lt:
        return SensitivityLabel.LOW
    if dispersion < policy.moderate_lt:
        return SensitivityLabel.MODERATE
    if dispersion < policy.high_lt:
        return SensitivityLabel.HIGH
    return SensitivityLabel.VERY_HIGH


def share_dispersion(shares: list[float]) -> float | None:
    """max_share − min_share. Not a confidence interval or posterior width."""
    if len(shares) < 2:
        return None
    return max(shares) - min(shares)


def share_stats(shares: list[float]) -> dict[str, float | None]:
    if not shares:
        return {
            "min": None,
            "max": None,
            "range": None,
            "mean": None,
            "median": None,
            "dispersion": None,
        }
    d = share_dispersion(shares) if len(shares) >= 2 else 0.0
    return {
        "min": min(shares),
        "max": max(shares),
        "range": (max(shares) - min(shares)) if len(shares) >= 2 else 0.0,
        "mean": float(mean(shares)),
        "median": float(median(shares)),
        "dispersion": d,
    }


def classify_channel_roles(
    *,
    channel_id: str,
    first_share: float,
    middle_share: float,
    last_share: float,
    journey_presence_rate: float,
    journey_presence_count: int,
    sensitivity: SensitivityLabel | None,
    observability: ObservabilityStatus,
    policy: ChannelRolePolicy | None = None,
) -> tuple[ChannelRoleLabel, ...]:
    """Numeric-feature classifier. Never uses channel display name."""
    policy = policy or DEFAULT_ROLE_POLICY
    labels: list[ChannelRoleLabel] = []
    low_obs = (
        journey_presence_rate < policy.presence_rate_floor
        or journey_presence_count < policy.volume_floor
        or observability is ObservabilityStatus.LIMITED
        and journey_presence_rate < (policy.presence_rate_floor * 2)
    )
    if low_obs:
        labels.append(ChannelRoleLabel.LOW_OBSERVABILITY)
    else:
        if first_share >= policy.introducer_first_min and last_share <= policy.introducer_last_max:
            labels.append(ChannelRoleLabel.INTRODUCER)
        if middle_share >= policy.assister_middle_min:
            labels.append(ChannelRoleLabel.ASSISTER)
        if last_share >= policy.converter_last_min and first_share <= policy.converter_first_max:
            labels.append(ChannelRoleLabel.CONVERTER)
        position_hits = sum(
            1
            for share in (first_share, middle_share, last_share)
            if share >= policy.multi_role_position_min
        )
        if position_hits >= 2:
            labels.append(ChannelRoleLabel.MULTI_ROLE)
    if channel_id == "direct" and last_share >= policy.direct_capture_last_min:
        labels.append(ChannelRoleLabel.DIRECT_CAPTURE)
    if sensitivity in (SensitivityLabel.HIGH, SensitivityLabel.VERY_HIGH):
        labels.append(ChannelRoleLabel.MODEL_SENSITIVE)
    # Stable order by enum declaration.
    order = {label: i for i, label in enumerate(ChannelRoleLabel)}
    return tuple(sorted(set(labels), key=lambda item: order[item]))


def classify_observability(
    *,
    user_pseudo_id_coverage: float | None = None,
    user_id_coverage: float | None = None,
    traffic_source_coverage: float | None = None,
    channel_mapping_coverage: float | None = None,
    other_unclassified_share: float | None = None,
    conversion_value_coverage: float | None = None,
    nonconverting_path_coverage: float | None = None,
    identity_strategy: str | None = None,
    source_cutoff: str | None = None,
    limitations: tuple[MTALimitation, ...] | list[MTALimitation] = (),
) -> MTAObservabilitySummary:
    """GOOD | REVIEW | LIMITED from coverage fields that actually exist."""
    mapping = channel_mapping_coverage
    identity = user_pseudo_id_coverage
    traffic = traffic_source_coverage
    unmapped = other_unclassified_share
    scores: list[ObservabilityStatus] = []
    if mapping is not None:
        if mapping >= 0.95:
            scores.append(ObservabilityStatus.GOOD)
        elif mapping >= 0.85:
            scores.append(ObservabilityStatus.REVIEW)
        else:
            scores.append(ObservabilityStatus.LIMITED)
    if identity is not None:
        if identity >= 0.80:
            scores.append(ObservabilityStatus.GOOD)
        elif identity >= 0.50:
            scores.append(ObservabilityStatus.REVIEW)
        else:
            scores.append(ObservabilityStatus.LIMITED)
    if traffic is not None:
        if traffic >= 0.90:
            scores.append(ObservabilityStatus.GOOD)
        elif traffic >= 0.70:
            scores.append(ObservabilityStatus.REVIEW)
        else:
            scores.append(ObservabilityStatus.LIMITED)
    if unmapped is not None:
        if unmapped <= 0.05:
            scores.append(ObservabilityStatus.GOOD)
        elif unmapped <= 0.15:
            scores.append(ObservabilityStatus.REVIEW)
        else:
            scores.append(ObservabilityStatus.LIMITED)
    if not scores:
        status = ObservabilityStatus.REVIEW
    elif ObservabilityStatus.LIMITED in scores:
        status = ObservabilityStatus.LIMITED
    elif ObservabilityStatus.REVIEW in scores:
        status = ObservabilityStatus.REVIEW
    else:
        status = ObservabilityStatus.GOOD
    return MTAObservabilitySummary(
        identity_strategy=identity_strategy,
        user_pseudo_id_coverage=user_pseudo_id_coverage,
        user_id_coverage=user_id_coverage,
        traffic_source_coverage=traffic_source_coverage,
        channel_mapping_coverage=channel_mapping_coverage,
        other_unclassified_share=other_unclassified_share,
        conversion_value_coverage=conversion_value_coverage,
        nonconverting_path_coverage=nonconverting_path_coverage,
        source_cutoff=source_cutoff,
        status=status,
        policy_version=OBSERVABILITY_POLICY_VERSION,
        limitations=tuple(limitations),
    )


def position_policy_description() -> str:
    return (
        f"{POSITION_POLICY_VERSION} uses {POSITION_POLICY_SINGLE_TOUCH}: "
        "a one-touch journey increments both first and last position counts. "
        "Shares use converted_journey_count as denominator and are not a "
        "3-way partition of 1.0 for a channel."
    )


def unmapped_limitation(channel_ids: tuple[str, ...] | list[str]) -> MTALimitation | None:
    if not channel_ids:
        return None
    return MTALimitation(
        limitation_type=MTALimitationType.UNMAPPED_TRAFFIC,
        statement=("One or more result channel_id values are absent from Channel Registry V1."),
        affected_channels=tuple(channel_ids),
    )


__all__ = [
    "DEFAULT_ROLE_POLICY",
    "DEFAULT_SENSITIVITY_POLICY",
    "ROLE_POLICY_VERSION",
    "SENSITIVITY_POLICY_VERSION",
    "classify_channel_roles",
    "classify_observability",
    "classify_sensitivity",
    "position_policy_description",
    "share_dispersion",
    "share_stats",
    "unmapped_limitation",
]
