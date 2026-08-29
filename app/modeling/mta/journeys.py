"""Journey helpers — deterministic IDs, ordering validation, path frequency."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.runtime_contracts import MTAFailureClass


class JourneyCompilationError(ValueError):
    failure_class = MTAFailureClass.JOURNEY_COMPILATION_ERROR


def deterministic_journey_id(
    *,
    subject_key: str,
    conversion_event: str,
    conversion_ts: str | None,
    channels: list[str] | tuple[str, ...],
    touchpoint_times: list[str] | tuple[str, ...],
) -> str:
    payload = {
        "subject_key": subject_key,
        "conversion_event": conversion_event,
        "conversion_ts": conversion_ts,
        "channels": list(channels),
        "touchpoint_times": list(touchpoint_times),
    }
    return "mjny_" + canonical_fingerprint(payload)[:24]


def assert_touchpoint_order(
    touchpoint_times: list[str] | tuple[str, ...],
    *,
    conversion_ts: str | None = None,
) -> None:
    times = list(touchpoint_times)
    if times != sorted(times):
        raise JourneyCompilationError(
            "Touchpoint timestamps must be nondecreasing; refusing silent sort."
        )
    if conversion_ts is not None and times and conversion_ts < times[-1]:
        raise JourneyCompilationError(
            "Conversion timestamp must be >= eligible touchpoint timestamps."
        )


def path_string(channels: list[str] | tuple[str, ...]) -> str:
    return " > ".join(channels)


def reduce_path_frequencies(
    journeys: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deterministic path-frequency reduction."""
    buckets: dict[tuple[str, bool], dict[str, Any]] = {}
    for journey in journeys:
        key = (str(journey["path_string"]), bool(journey.get("converted", False)))
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {
                "path_string": key[0],
                "converted": key[1],
                "occurrences": 1,
                "conversion_value": float(journey.get("conversion_value") or 0.0),
            }
        else:
            bucket["occurrences"] += 1
            bucket["conversion_value"] += float(journey.get("conversion_value") or 0.0)
    return [buckets[k] for k in sorted(buckets.keys(), key=lambda x: (x[0], x[1]))]


def session_key(*, user_pseudo_id: str, ga_session_id: str) -> str:
    digest = sha256(f"{user_pseudo_id}:{ga_session_id}".encode()).hexdigest()[:24]
    return f"msess_{digest}"
