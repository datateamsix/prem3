"""Meridian 1.8.0 results adapter — version-specific, fail-closed.

Official methods used (google-meridian==1.8.0 Analyzer):
- roi()
- incremental_outcome()
- marginal_roi()
- summary_metrics() → pct_of_contribution / spend / intervals
- response_curves()
- get_historical_spend() when available

Unsupported / not called:
- contribution() — not a public Analyzer method on 1.8.0
- BudgetOptimizer / ScenarioPlanner
"""

from __future__ import annotations

from typing import Any, Protocol

from app.modeling.common.errors import ModelingError
from app.modeling.mmm.results import ADAPTER_VERSION, MERIDIAN_RUNTIME_VERSION
from app.modeling.mmm.results.contracts import (
    RawChannelMetricBundle,
    RawMeridianResultsEvidence,
    RawResponseCurveBundle,
    ResponseCurvePoint,
)


class UnsupportedMeridianVersionError(ModelingError):
    code = "UNSUPPORTED_MERIDIAN_VERSION"


class MeridianAnalyzerLike(Protocol):
    def roi(self, **kwargs: Any) -> Any: ...

    def incremental_outcome(self, **kwargs: Any) -> Any: ...

    def marginal_roi(self, **kwargs: Any) -> Any: ...

    def summary_metrics(self, **kwargs: Any) -> Any: ...

    def response_curves(self, **kwargs: Any) -> Any: ...


SUPPORTED_SOURCE_METHODS = (
    "Analyzer.roi",
    "Analyzer.incremental_outcome",
    "Analyzer.marginal_roi",
    "Analyzer.summary_metrics",
    "Analyzer.response_curves",
    "Analyzer.get_historical_spend",
)


def _to_float_list(value: Any) -> list[float | None]:
    if value is None:
        return []
    if hasattr(value, "numpy"):
        try:
            value = value.numpy()
        except Exception:
            return []
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception:
            return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        out: list[float | None] = []
        for item in value:
            if isinstance(item, (list, tuple)):
                # Aggregate draws → mean for point estimate path when nested.
                flat = [float(x) for x in item if isinstance(x, (int, float))]
                out.append(sum(flat) / len(flat) if flat else None)
            elif isinstance(item, (int, float)):
                out.append(float(item))
            else:
                out.append(None)
        return out
    return []


def _mean_over_draws(value: Any) -> list[float | None]:
    """Collapse Analyzer tensors to per-channel point estimates when possible."""
    if value is None:
        return []
    if hasattr(value, "numpy"):
        try:
            value = value.numpy()
        except Exception:
            return []
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception:
            return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if not isinstance(value, (list, tuple)):
        return []
    # Common shapes: [channel], [draw, channel], [chain, draw, channel]
    if value and isinstance(value[0], (int, float)):
        return [float(x) for x in value]
    if value and isinstance(value[0], (list, tuple)):
        # If last axis looks like channels, average leading axes.
        first = value[0]
        if first and isinstance(first[0], (list, tuple)):
            # [chain, draw, channel]
            channels = len(first[0])
            sums = [0.0] * channels
            counts = [0] * channels
            for chain in value:
                for draw in chain:
                    for idx, item in enumerate(draw):
                        if isinstance(item, (int, float)):
                            sums[idx] += float(item)
                            counts[idx] += 1
            return [
                (sums[i] / counts[i] if counts[i] else None) for i in range(channels)
            ]
        channels = len(first)
        sums = [0.0] * channels
        counts = [0] * channels
        for draw in value:
            for idx, item in enumerate(draw):
                if isinstance(item, (int, float)):
                    sums[idx] += float(item)
                    counts[idx] += 1
        return [(sums[i] / counts[i] if counts[i] else None) for i in range(channels)]
    return []


def _xr_metric(dataset: Any, name: str, channel_coord: str = "channel") -> dict[str, Any]:
    """Best-effort extract of summary_metrics / response_curves fields."""
    if dataset is None:
        return {}
    try:
        data_vars = getattr(dataset, "data_vars", None)
        if data_vars is not None and name not in data_vars and name not in getattr(dataset, "coords", {}):
            if name not in dataset:
                return {}
        arr = dataset[name]
    except Exception:
        return {}
    try:
        channels = [str(x) for x in arr.coords[channel_coord].values]
    except Exception:
        try:
            channels = [str(x) for x in dataset.coords[channel_coord].values]
        except Exception:
            channels = []
    try:
        values = arr.values
        if hasattr(values, "tolist"):
            values = values.tolist()
    except Exception:
        return {}
    # Prefer median / mean if distributional dims present.
    if isinstance(values, list) and values and isinstance(values[0], list):
        collapsed = _mean_over_draws(values)
    elif isinstance(values, (int, float)):
        collapsed = [float(values)]
    else:
        collapsed = _to_float_list(values)
    result: dict[str, Any] = {}
    if channels and len(channels) == len(collapsed):
        for channel, value in zip(channels, collapsed, strict=False):
            result[channel] = value
    elif not channels and len(collapsed) == 1:
        result["__scalar__"] = collapsed[0]
    return result


class Meridian180ResultsAdapter:
    """Thin adapter that keeps Meridian 1.8.0 quirks out of generic contracts."""

    def __init__(self, *, expected_meridian_version: str = MERIDIAN_RUNTIME_VERSION) -> None:
        self.expected_meridian_version = expected_meridian_version
        self.adapter_version = ADAPTER_VERSION

    def assert_supported_version(self, meridian_version: str | None) -> None:
        if meridian_version != self.expected_meridian_version:
            raise UnsupportedMeridianVersionError(
                f"Meridian180ResultsAdapter requires {self.expected_meridian_version}; "
                f"got {meridian_version!r}."
            )

    def extract_from_analyzer(
        self,
        analyzer: Any,
        *,
        channel_ids: tuple[str, ...] | list[str],
        meridian_version: str = MERIDIAN_RUNTIME_VERSION,
        confidence_level: float = 0.9,
        use_kpi: bool = False,
    ) -> RawMeridianResultsEvidence:
        self.assert_supported_version(meridian_version)
        channels = tuple(str(c) for c in channel_ids)
        used: list[str] = []
        unavailable: list[str] = []
        notes: list[str] = []

        # contribution() is NOT a 1.8.0 Analyzer method.
        if hasattr(analyzer, "contribution") and callable(getattr(analyzer, "contribution")):
            notes.append(
                "Analyzer.contribution present but unused; 1.8.0 authority is summary_metrics."
            )

        roi_by_channel = self._call_channel_metric(
            analyzer, "roi", channels, used, unavailable, use_kpi=use_kpi
        )
        incremental_by_channel = self._call_channel_metric(
            analyzer, "incremental_outcome", channels, used, unavailable, use_kpi=use_kpi
        )
        mroi_by_channel = self._call_channel_metric(
            analyzer, "marginal_roi", channels, used, unavailable, use_kpi=use_kpi
        )

        contribution_by_channel: dict[str, float | None] = {}
        spend_by_channel: dict[str, float | None] = {}
        intervals: dict[str, dict[str, tuple[float | None, float | None]]] = {}
        if callable(getattr(analyzer, "summary_metrics", None)):
            try:
                summary = analyzer.summary_metrics(
                    use_kpi=use_kpi, confidence_level=confidence_level
                )
                used.append("Analyzer.summary_metrics")
                contribution_by_channel = {
                    k: (float(v) if isinstance(v, (int, float)) else None)
                    for k, v in _xr_metric(summary, "pct_of_contribution").items()
                }
                spend_map = _xr_metric(summary, "spend")
                if not spend_map:
                    spend_map = _xr_metric(summary, "media_spend")
                spend_by_channel = {
                    k: (float(v) if isinstance(v, (int, float)) else None)
                    for k, v in spend_map.items()
                }
                for metric_name in ("roi", "marginal_roi", "incremental_outcome", "pct_of_contribution"):
                    lo = _xr_metric(summary, f"{metric_name}_ci_lo")
                    hi = _xr_metric(summary, f"{metric_name}_ci_hi")
                    if not lo and not hi:
                        continue
                    key = (
                        "contribution"
                        if metric_name == "pct_of_contribution"
                        else metric_name
                    )
                    for channel in channels:
                        intervals.setdefault(channel, {})[key] = (
                            lo.get(channel),
                            hi.get(channel),
                        )
            except Exception:
                unavailable.append("Analyzer.summary_metrics")
        else:
            unavailable.append("Analyzer.summary_metrics")

        if callable(getattr(analyzer, "get_historical_spend", None)):
            try:
                hist = analyzer.get_historical_spend()
                used.append("Analyzer.get_historical_spend")
                hist_map = _mean_over_draws(hist)
                if len(hist_map) == len(channels):
                    for channel, value in zip(channels, hist_map, strict=True):
                        if channel not in spend_by_channel or spend_by_channel[channel] is None:
                            spend_by_channel[channel] = value
            except Exception:
                unavailable.append("Analyzer.get_historical_spend")
        else:
            unavailable.append("Analyzer.get_historical_spend")

        response_curves = self._extract_response_curves(
            analyzer, channels, used, unavailable, use_kpi=use_kpi, confidence_level=confidence_level
        )

        bundles: list[RawChannelMetricBundle] = []
        for channel in channels:
            iv = intervals.get(channel, {})
            flags: dict[str, str] = {}
            for name, point in (
                ("roi", roi_by_channel.get(channel)),
                ("marginal_roi", mroi_by_channel.get(channel)),
                ("incremental_outcome", incremental_by_channel.get(channel)),
                ("contribution", contribution_by_channel.get(channel)),
            ):
                if point is None:
                    flags[name] = "NOT_AVAILABLE"
            bundles.append(
                RawChannelMetricBundle(
                    channel_id=channel,
                    channel_name=channel,
                    spend=spend_by_channel.get(channel),
                    incremental_outcome=incremental_by_channel.get(channel),
                    incremental_outcome_lower=(iv.get("incremental_outcome") or (None, None))[0],
                    incremental_outcome_upper=(iv.get("incremental_outcome") or (None, None))[1],
                    contribution=contribution_by_channel.get(channel),
                    contribution_lower=(iv.get("contribution") or (None, None))[0],
                    contribution_upper=(iv.get("contribution") or (None, None))[1],
                    roi=roi_by_channel.get(channel),
                    roi_lower=(iv.get("roi") or (None, None))[0],
                    roi_upper=(iv.get("roi") or (None, None))[1],
                    marginal_roi=mroi_by_channel.get(channel),
                    marginal_roi_lower=(iv.get("marginal_roi") or (None, None))[0],
                    marginal_roi_upper=(iv.get("marginal_roi") or (None, None))[1],
                    source_methods=tuple(used),
                    metric_flags=flags,
                )
            )

        return RawMeridianResultsEvidence(
            meridian_version=meridian_version,
            adapter_version=self.adapter_version,
            source_methods_used=tuple(dict.fromkeys(used)),
            source_methods_unavailable=tuple(dict.fromkeys(unavailable)),
            channels=tuple(bundles),
            response_curves=tuple(response_curves),
            confidence_level=confidence_level,
            notes=tuple(notes),
            synthetic=False,
        )

    def _call_channel_metric(
        self,
        analyzer: Any,
        method_name: str,
        channels: tuple[str, ...],
        used: list[str],
        unavailable: list[str],
        *,
        use_kpi: bool,
    ) -> dict[str, float | None]:
        source = f"Analyzer.{method_name}"
        fn = getattr(analyzer, method_name, None)
        if not callable(fn):
            unavailable.append(source)
            return {channel: None for channel in channels}
        try:
            raw = fn(use_kpi=use_kpi) if method_name != "roi" else fn(use_kpi=use_kpi)
            # roi also accepts use_kpi
            values = _mean_over_draws(raw)
            used.append(source)
            if len(values) != len(channels):
                # Preserve ordering when lengths match partially; else mark unavailable.
                if not values:
                    unavailable.append(source)
                    return {channel: None for channel in channels}
                # Pad / truncate conservatively without inventing values.
                out: dict[str, float | None] = {}
                for idx, channel in enumerate(channels):
                    out[channel] = values[idx] if idx < len(values) else None
                return out
            return {channel: values[idx] for idx, channel in enumerate(channels)}
        except TypeError:
            try:
                raw = fn()
                values = _mean_over_draws(raw)
                used.append(source)
                return {
                    channel: (values[idx] if idx < len(values) else None)
                    for idx, channel in enumerate(channels)
                }
            except Exception:
                unavailable.append(source)
                return {channel: None for channel in channels}
        except Exception:
            unavailable.append(source)
            return {channel: None for channel in channels}

    def _extract_response_curves(
        self,
        analyzer: Any,
        channels: tuple[str, ...],
        used: list[str],
        unavailable: list[str],
        *,
        use_kpi: bool,
        confidence_level: float,
    ) -> list[RawResponseCurveBundle]:
        fn = getattr(analyzer, "response_curves", None)
        if not callable(fn):
            unavailable.append("Analyzer.response_curves")
            return []
        try:
            dataset = fn(use_kpi=use_kpi, confidence_level=confidence_level)
            used.append("Analyzer.response_curves")
        except Exception:
            unavailable.append("Analyzer.response_curves")
            return []

        bundles: list[RawResponseCurveBundle] = []
        try:
            channel_coord = "channel"
            channel_values = [str(x) for x in dataset.coords[channel_coord].values]
        except Exception:
            channel_values = list(channels)

        for channel in channels:
            if channel not in channel_values and channel_values:
                continue
            points: list[ResponseCurvePoint] = []
            try:
                subset = dataset.sel({channel_coord: channel})
            except Exception:
                subset = dataset
            try:
                spend = subset["spend"].values.tolist()
            except Exception:
                try:
                    spend = subset["spend_level"].values.tolist()
                except Exception:
                    spend = []
            try:
                outcome = subset["incremental_outcome"].values.tolist()
            except Exception:
                try:
                    outcome = subset["outcome"].values.tolist()
                except Exception:
                    outcome = []
            lo: list[Any] = []
            hi: list[Any] = []
            try:
                lo = subset["incremental_outcome_ci_lo"].values.tolist()
            except Exception:
                lo = []
            try:
                hi = subset["incremental_outcome_ci_hi"].values.tolist()
            except Exception:
                hi = []
            if isinstance(spend, (int, float)):
                spend = [spend]
            if isinstance(outcome, (int, float)):
                outcome = [outcome]
            for idx, spend_level in enumerate(spend if isinstance(spend, list) else []):
                if not isinstance(spend_level, (int, float)):
                    continue
                expected = outcome[idx] if idx < len(outcome) else None
                if isinstance(expected, list):
                    expected = _mean_over_draws(expected)[0] if expected else None
                point_lo = lo[idx] if idx < len(lo) else None
                point_hi = hi[idx] if idx < len(hi) else None
                if isinstance(point_lo, list):
                    point_lo = _mean_over_draws(point_lo)[0] if point_lo else None
                if isinstance(point_hi, list):
                    point_hi = _mean_over_draws(point_hi)[0] if point_hi else None
                points.append(
                    ResponseCurvePoint(
                        spend_level=float(spend_level),
                        expected_outcome=float(expected) if isinstance(expected, (int, float)) else None,
                        outcome_lower=float(point_lo) if isinstance(point_lo, (int, float)) else None,
                        outcome_upper=float(point_hi) if isinstance(point_hi, (int, float)) else None,
                    )
                )
            spend_levels = [p.spend_level for p in points]
            bundles.append(
                RawResponseCurveBundle(
                    channel_id=channel,
                    points=tuple(points),
                    current_spend=None,
                    uncertainty_available=any(
                        p.outcome_lower is not None and p.outcome_upper is not None for p in points
                    ),
                    observed_spend_min=min(spend_levels) if spend_levels else None,
                    observed_spend_max=max(spend_levels) if spend_levels else None,
                )
            )
        return bundles

    def extract_from_raw_evidence(
        self, evidence: RawMeridianResultsEvidence
    ) -> RawMeridianResultsEvidence:
        """Pass-through for fixtures / recording adapters."""
        self.assert_supported_version(evidence.meridian_version)
        return evidence
