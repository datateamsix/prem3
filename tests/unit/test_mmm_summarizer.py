from app.modeling.mmm.meridian.summarizer import structured_results


def test_structured_results_accepts_list_roi() -> None:
    summary = structured_results(
        html_ref="results.html",
        requested_date_range="2024-01-01/2024-03-18",
        effective_date_range="2024-01-01/2024-03-18",
        values={"roi": [[1.1, 1.2], [0.9, 1.0]]},
    )
    assert summary.roi == {"json": "[[1.1, 1.2], [0.9, 1.0]]"}


def test_structured_results_maps_analyzer_aliases() -> None:
    summary = structured_results(
        html_ref=None,
        requested_date_range=None,
        effective_date_range=None,
        values={
            "incremental_outcome": {"paid_search": 10},
            "contribution": {"paid_search": 0.4},
            "marginal_roi": {"paid_search": 0.2},
            "roi": {"paid_search": 1.4},
        },
    )
    assert summary.incremental_outcomes == {"paid_search": 10}
    assert summary.channel_contribution == {"paid_search": 0.4}
    assert summary.mroi == {"paid_search": 0.2}
    assert summary.roi == {"paid_search": 1.4}
