from app.data_foundation.contracts import SourceContinuityPlan


def test_continuity_plan_does_not_auto_merge_disagreement() -> None:
    plan = SourceContinuityPlan(
        historical_source_id="dfsrc_drive",
        ongoing_source_id="dfsrc_bq",
        cutoff="2026-01-01",
        overlap_handling="REVIEW",
        reconciliation_required=True,
        canonical_precedence="ongoing_after_cutoff",
    )
    assert plan.reconciliation_required is True
    assert plan.overlap_handling == "REVIEW"
