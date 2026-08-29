"""Compile P0 MTAVisualization chart-ready data bound to a result snapshot.

No Vega-Lite. Frontend rendering is out of scope.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import utc_now
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.results_contracts import (
    MarkovAttributionEvidence,
    MetricAvailability,
    MTAFindingAuthority,
    MTAJourneySummary,
    MTAModelComparison,
    MTAModelSensitivityEvidence,
    MTAResultsSnapshot,
    MTAVisualization,
    MTAVisualizationKind,
    ShapleyAttributionEvidence,
)


def _viz(
    *,
    snapshot: MTAResultsSnapshot,
    kind: MTAVisualizationKind,
    title: str,
    description: str,
    data: list[dict[str, Any]],
    evidence_refs: tuple[str, ...],
    available: bool = True,
    unavailable_reason: str | None = None,
    source_model: str | None = None,
    default_view: str | None = None,
) -> MTAVisualization:
    payload = {
        "kind": kind.value,
        "snapshot": snapshot.result_snapshot_id,
        "data": data,
        "available": available,
    }
    return MTAVisualization(
        visualization_id=f"mviz_{canonical_fingerprint(payload)[:20]}",
        kind=kind,
        title=title,
        description=description,
        source_run_id=snapshot.run_id,
        source_result_snapshot_id=snapshot.result_snapshot_id,
        source_model=source_model,
        source_evidence_refs=evidence_refs,
        data=tuple(data),
        available=available,
        unavailable_reason=unavailable_reason,
        default_view=default_view,
        authority=MTAFindingAuthority.VERIFIED,
        generated_at=utc_now(),
        fingerprint=canonical_fingerprint(payload),
    )


def compile_visualizations(
    *,
    snapshot: MTAResultsSnapshot,
    comparison: MTAModelComparison,
    journeys: MTAJourneySummary,
    sensitivity: tuple[MTAModelSensitivityEvidence, ...],
    markov: MarkovAttributionEvidence | None,
    shapley: ShapleyAttributionEvidence,
) -> tuple[MTAVisualization, ...]:
    viz: list[MTAVisualization] = []
    snap_ref = snapshot.result_snapshot_id

    by_channel_model = [
        {
            "channel_id": row.channel_id,
            "model_type": row.model_type,
            "attribution_share": row.attribution_share,
            "attributed_credit": row.attributed_credit,
        }
        for row in comparison.rows
        if row.availability is MetricAvailability.AVAILABLE
    ]
    viz.append(
        _viz(
            snapshot=snapshot,
            kind=MTAVisualizationKind.ATTRIBUTION_BY_CHANNEL_MODEL,
            title="Attributed share by channel and model",
            description="Observable journey credit share for each completed attribution model.",
            data=by_channel_model,
            evidence_refs=(snapshot.channel_results_ref, snapshot.model_comparison_ref),
            default_view="grouped_bar",
        )
    )
    heatmap = [
        {
            "channel_id": row.channel_id,
            "model_type": row.model_type,
            "attribution_share": row.attribution_share,
        }
        for row in comparison.rows
        if row.availability is MetricAvailability.AVAILABLE and row.attribution_share is not None
    ]
    viz.append(
        _viz(
            snapshot=snapshot,
            kind=MTAVisualizationKind.MODEL_COMPARISON_HEATMAP,
            title="Model comparison heatmap",
            description=(
                "Attribution share only — share and credit are not mixed "
                "in this value field."
            ),
            data=heatmap,
            evidence_refs=(snapshot.model_comparison_ref,),
            default_view="heatmap",
        )
    )
    position_rows = [
        {
            "channel_id": pos.channel_id,
            "first_position_share": pos.first_position_share,
            "middle_position_share": pos.middle_position_share,
            "last_position_share": pos.last_position_share,
        }
        for pos in journeys.position_evidence
    ]
    viz.append(
        _viz(
            snapshot=snapshot,
            kind=MTAVisualizationKind.CHANNEL_ROLE_POSITION,
            title="Journey position shares",
            description=(
                "First, middle, and last position shares under FIRST_AND_LAST. "
                "This is the evidence layer beneath role labels."
            ),
            data=position_rows,
            evidence_refs=(snapshot.journey_summary_ref,),
            default_view="stacked_bar",
        )
    )

    if markov is None or markov.availability is not MetricAvailability.AVAILABLE:
        viz.append(
            _viz(
                snapshot=snapshot,
                kind=MTAVisualizationKind.MARKOV_TRANSITION_MATRIX,
                title="Markov transition matrix",
                description="Observed channel-state transition probabilities.",
                data=[],
                evidence_refs=(),
                available=False,
                unavailable_reason=(None if markov is None else markov.unavailable_reason)
                or "Markov evidence was not run.",
                source_model="MARKOV",
            )
        )
        viz.append(
            _viz(
                snapshot=snapshot,
                kind=MTAVisualizationKind.MARKOV_REMOVAL_EFFECT,
                title="Markov removal sensitivity",
                description=markov.removal_effect_explanation
                if markov
                else ("Modeled conversion-probability sensitivity when a channel is removed."),
                data=[],
                evidence_refs=(),
                available=False,
                unavailable_reason=(None if markov is None else markov.unavailable_reason)
                or "Markov evidence was not run.",
                source_model="MARKOV",
            )
        )
    else:
        ordered = sorted({(t.from_channel_id, t.to_channel_id) for t in markov.transitions})
        del ordered
        viz.append(
            _viz(
                snapshot=snapshot,
                kind=MTAVisualizationKind.MARKOV_TRANSITION_MATRIX,
                title="Markov transition matrix",
                description="Observed channel-state transition probabilities.",
                data=[
                    {
                        "from_channel_id": row.from_channel_id,
                        "to_channel_id": row.to_channel_id,
                        "transition_probability": row.transition_probability,
                    }
                    for row in sorted(
                        markov.transitions,
                        key=lambda r: (r.from_channel_id, r.to_channel_id),
                    )
                ],
                evidence_refs=(markov.transition_matrix_ref or snap_ref,),
                source_model="MARKOV",
                default_view="heatmap",
            )
        )
        viz.append(
            _viz(
                snapshot=snapshot,
                kind=MTAVisualizationKind.MARKOV_REMOVAL_EFFECT,
                title="Markov removal sensitivity",
                description=markov.removal_effect_explanation,
                data=[
                    {"channel_id": channel_id, "removal_effect": effect}
                    for channel_id, effect in sorted(
                        markov.removal_effects, key=lambda item: (-item[1], item[0])
                    )
                ],
                evidence_refs=(snapshot.markov_evidence_ref or snap_ref,),
                source_model="MARKOV",
                default_view="ranked_bar",
            )
        )

    if shapley.availability is not MetricAvailability.AVAILABLE:
        viz.append(
            _viz(
                snapshot=snapshot,
                kind=MTAVisualizationKind.SHAPLEY_CONTRIBUTION,
                title="Shapley marginal coalition contribution",
                description="Marginal contribution across observed channel coalitions.",
                data=[],
                evidence_refs=(),
                available=False,
                unavailable_reason=shapley.unavailable_reason or "Shapley was not run.",
                source_model="SHAPLEY",
            )
        )
    else:
        viz.append(
            _viz(
                snapshot=snapshot,
                kind=MTAVisualizationKind.SHAPLEY_CONTRIBUTION,
                title="Shapley marginal coalition contribution",
                description=(
                    "Marginal contribution across observed channel coalitions. "
                    f"size={shapley.size} order={shapley.order} "
                    f"values_col={shapley.values_col} "
                    f"path_limit_applied={shapley.path_limit_applied}"
                ),
                data=[
                    {
                        "channel_id": c.channel_id,
                        "shapley_share": c.shapley_share,
                        "shapley_credit": c.shapley_credit,
                        "size": shapley.size,
                        "order": shapley.order,
                        "values_col": shapley.values_col,
                        "path_limit_applied": shapley.path_limit_applied,
                    }
                    for c in shapley.channel_credit
                ],
                evidence_refs=(snapshot.shapley_evidence_ref or snap_ref,),
                source_model="SHAPLEY",
                default_view="bar",
            )
        )

    viz.append(
        _viz(
            snapshot=snapshot,
            kind=MTAVisualizationKind.TOP_CONVERSION_PATHS,
            title="Top conversion paths",
            description="Ranked observable converting paths. Not a Sankey diagram.",
            data=[
                {
                    "path_rank": p.path_rank,
                    "path_string": p.path_string,
                    "occurrences": p.occurrences,
                    "share_of_converting_paths": p.share_of_converting_paths,
                    "conversion_value": p.conversion_value,
                }
                for p in journeys.top_paths
            ],
            evidence_refs=(snapshot.journey_summary_ref,),
            default_view="ranked_table",
        )
    )
    viz.append(
        _viz(
            snapshot=snapshot,
            kind=MTAVisualizationKind.PATH_LENGTH_DISTRIBUTION,
            title="Path length distribution",
            description="Converted journey counts by touchpoint_count.",
            data=[
                {
                    "touchpoint_count": b.touchpoint_count,
                    "journey_count": b.journey_count,
                    "share": b.share,
                }
                for b in journeys.path_length_distribution
            ],
            evidence_refs=(snapshot.journey_summary_ref,),
            default_view="bar",
        )
    )
    viz.append(
        _viz(
            snapshot=snapshot,
            kind=MTAVisualizationKind.TIME_TO_CONVERSION_DISTRIBUTION,
            title="Time-to-conversion distribution",
            description="Deterministic day buckets from first eligible touch to conversion.",
            data=[
                {
                    "bucket_start": b.bucket_start,
                    "bucket_end": b.bucket_end,
                    "unit": b.unit,
                    "journey_count": b.journey_count,
                    "share": b.share,
                }
                for b in journeys.time_to_conversion_distribution
            ],
            evidence_refs=(snapshot.journey_summary_ref,),
            default_view="bar",
        )
    )
    viz.append(
        _viz(
            snapshot=snapshot,
            kind=MTAVisualizationKind.MODEL_SENSITIVITY_RANGE,
            title="Cross-model attribution range",
            description=(
                "Per-channel min/max/median attribution share across completed models. "
                "Range is model disagreement, not a confidence interval."
            ),
            data=[
                {
                    "channel_id": s.channel_id,
                    "min_share": s.min_attribution_share,
                    "max_share": s.max_attribution_share,
                    "median_share": s.median_attribution_share,
                    "dispersion": s.dispersion,
                    "sensitivity_label": None
                    if s.sensitivity_label is None
                    else s.sensitivity_label.value,
                    "models_included": list(s.models_included),
                    "is_confidence_interval": False,
                }
                for s in sensitivity
            ],
            evidence_refs=(snapshot.model_comparison_ref,),
            default_view="range_dot",
        )
    )
    return tuple(viz)
