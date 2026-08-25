"""MEL seam for result episodes — no global learning policy changes."""

from __future__ import annotations

from typing import Any

from app.modeling.mmm.results.contracts import MMMDecisionIntelligenceBrief, MMMResultsSnapshot


def result_episode_payload(
    snapshot: MMMResultsSnapshot,
    *,
    brief: MMMDecisionIntelligenceBrief | None = None,
) -> dict[str, Any]:
    """Structured episode suitable for MEL recording.

    Customer-specific numeric channel values are summarized, not re-exported as
    global learning policy inputs.
    """
    return {
        "episode_type": "MMM_RESULT_SNAPSHOT",
        "model_version_id": snapshot.model_version_id,
        "fit_run_id": snapshot.fit_run_id,
        "result_snapshot_id": snapshot.result_snapshot_id,
        "result_status": snapshot.result_status.value,
        "eligibility": snapshot.eligibility.value,
        "review_outcome": {
            "model_accepted": snapshot.fit_evidence.model_accepted,
            "review_source": snapshot.fit_evidence.official_review_source.value,
            "blocking_failures": list(snapshot.fit_evidence.blocking_failures),
            "review_items": list(snapshot.fit_evidence.review_items),
        },
        "metric_availability": {
            channel.channel_id: {
                "roi": channel.roi.availability.value,
                "marginal_roi": channel.marginal_roi.availability.value,
                "incremental_outcome": channel.incremental_outcome.availability.value,
                "contribution": channel.contribution.availability.value,
            }
            for channel in snapshot.channels
        },
        "recommendation_generated": bool(
            brief is not None and any(item.investment_action for item in brief.recommendations)
        ),
        "synthetic": snapshot.synthetic,
    }
