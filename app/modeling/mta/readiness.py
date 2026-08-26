"""Deterministic MTA readiness — Gemini cannot mark MTA ready."""

from __future__ import annotations

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import (
    GA4SettlementPolicy,
    MTAInputContract,
    MTAQualityCheckId,
    MTAQualityCheckResult,
    MTAReadinessReceipt,
    MTAReadinessState,
    QualityCheckStatus,
)
from app.modeling.mta.policies import assert_canonical_not_intraday


def _check(
    check_id: MTAQualityCheckId,
    ok: bool,
    *,
    detail: str | None = None,
    warn: bool = False,
) -> MTAQualityCheckResult:
    if ok:
        status = QualityCheckStatus.PASS
    elif warn:
        status = QualityCheckStatus.WARN
    else:
        status = QualityCheckStatus.FAIL
    return MTAQualityCheckResult(check_id=check_id, status=status, detail=detail)


def evaluate_mta_readiness(
    *,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    track_id: str,
    contract: MTAInputContract | None,
    ga4_dataset_exists: bool,
    daily_shards_continuous: bool = True,
    key_event_present: bool = False,
    conversion_volume_ok: bool = False,
    channel_grouping_approved: bool = False,
    unmapped_share_ok: bool = True,
    uses_intraday_for_canonical: bool = False,
    user_pseudo_id_coverage: float | None = None,
    lookback_covered: bool = False,
) -> MTAReadinessReceipt:
    checks: list[MTAQualityCheckResult] = []
    blocking: list[str] = []
    warnings: list[str] = []

    checks.append(
        _check(
            MTAQualityCheckId.GA4_SOURCE_EXISTS,
            ga4_dataset_exists,
            detail=None if ga4_dataset_exists else "GA4 analytics_* dataset not bound",
        )
    )
    if not ga4_dataset_exists:
        blocking.append(MTAQualityCheckId.GA4_SOURCE_EXISTS.value)

    checks.append(
        _check(
            MTAQualityCheckId.DAILY_SHARDS_CONTINUOUS,
            daily_shards_continuous,
            detail=None if daily_shards_continuous else "Daily event shards have gaps",
        )
    )
    if not daily_shards_continuous:
        blocking.append(MTAQualityCheckId.DAILY_SHARDS_CONTINUOUS.value)

    settled_ok = True
    try:
        if contract is not None:
            assert_canonical_not_intraday(
                settlement_policy=contract.settlement_policy,
                uses_intraday_shards=uses_intraday_for_canonical,
            )
    except ValueError as exc:
        settled_ok = False
        blocking.append(MTAQualityCheckId.SOURCE_SETTLED.value)
        checks.append(
            _check(MTAQualityCheckId.SOURCE_SETTLED, False, detail=str(exc))
        )
    else:
        checks.append(_check(MTAQualityCheckId.SOURCE_SETTLED, settled_ok))
        if contract is not None and contract.settlement_policy is GA4SettlementPolicy.DAILY_SETTLED:
            checks.append(
                _check(
                    MTAQualityCheckId.LATE_SHARD_POLICY,
                    True,
                    detail="DAILY_SETTLED lag policy applied",
                )
            )

    key_ok = bool(contract and contract.conversion_event) and key_event_present
    checks.append(
        _check(
            MTAQualityCheckId.KEY_EVENT_EXISTS,
            key_ok,
            detail=None if key_ok else "Conversion/key event not validated in GA4",
        )
    )
    if not key_ok:
        blocking.append(MTAQualityCheckId.KEY_EVENT_EXISTS.value)

    checks.append(
        _check(
            MTAQualityCheckId.CONVERSION_VOLUME,
            conversion_volume_ok,
            detail=None if conversion_volume_ok else "Conversion volume inadequate",
        )
    )
    if not conversion_volume_ok:
        blocking.append(MTAQualityCheckId.CONVERSION_VOLUME.value)

    grouping_ok = bool(contract and contract.channel_grouping_version) and channel_grouping_approved
    if not grouping_ok:
        blocking.append("CHANNEL_GROUPING")
        checks.append(
            MTAQualityCheckResult(
                check_id=MTAQualityCheckId.UNMAPPED_CHANNEL_RATE,
                status=QualityCheckStatus.FAIL,
                detail="Channel grouping not approved",
            )
        )
    else:
        checks.append(
            _check(
                MTAQualityCheckId.UNMAPPED_CHANNEL_RATE,
                unmapped_share_ok,
                detail=None if unmapped_share_ok else "Unmapped share exceeds policy",
                warn=not unmapped_share_ok,
            )
        )
        if not unmapped_share_ok:
            warnings.append(MTAQualityCheckId.UNMAPPED_CHANNEL_RATE.value)

    if user_pseudo_id_coverage is not None:
        ok = user_pseudo_id_coverage >= 0.5
        checks.append(
            _check(
                MTAQualityCheckId.USER_PSEUDO_ID_COVERAGE,
                ok,
                detail=f"coverage={user_pseudo_id_coverage}",
                warn=not ok,
            )
        )
        if not ok:
            warnings.append(MTAQualityCheckId.USER_PSEUDO_ID_COVERAGE.value)

    checks.append(
        _check(
            MTAQualityCheckId.LOOKBACK_COVERAGE,
            lookback_covered,
            detail=None if lookback_covered else "Lookback window not covered by shards",
        )
    )
    if not lookback_covered:
        blocking.append(MTAQualityCheckId.LOOKBACK_COVERAGE.value)

    if contract is None:
        blocking.append("INPUT_CONTRACT_MISSING")

    state = (
        MTAReadinessState.MTA_INPUT_READY
        if not blocking and contract is not None
        else MTAReadinessState.NOT_READY
    )
    receipt_fp = canonical_fingerprint({"track": track_id, "state": state.value})
    receipt_id = f"mta_ready_{receipt_fp[:20]}"
    payload = {
        "state": state.value,
        "blocking": blocking,
        "checks": [c.model_dump(mode="json") for c in checks],
        "contract_fp": None if contract is None else contract.fingerprint,
    }
    return MTAReadinessReceipt(
        receipt_id=receipt_id,
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=track_id,
        state=state,
        checks=tuple(checks),
        input_contract_fingerprint=None if contract is None else contract.fingerprint,
        ga4_dataset_id=None if contract is None else contract.ga4_dataset_id,
        conversion_event=None if contract is None else contract.conversion_event,
        blocking_failures=tuple(blocking),
        warnings=tuple(warnings),
        fingerprint=canonical_fingerprint(payload),
    )
