import pytest

from app.data_foundation.contracts import QueryBudgetPolicy
from app.data_foundation.discovery.query_budget import compile_profile_query, reject_arbitrary_sql


def test_compile_rejects_select_star_policy() -> None:
    with pytest.raises(ValueError, match="SELECT \\*"):
        compile_profile_query(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="google_ads",
            columns=("date", "spend"),
            partition_field=None,
            partition_start=None,
            policy=QueryBudgetPolicy(allow_select_star=True, require_partition_predicate=False),
        )


def test_compile_rejects_unsafe_identifier() -> None:
    with pytest.raises(ValueError, match="identifier"):
        compile_profile_query(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="google;drop",
            columns=("date",),
            partition_field=None,
            partition_start=None,
            policy=QueryBudgetPolicy(require_partition_predicate=False),
        )


def test_compile_enforces_partition_and_budget() -> None:
    compiled = compile_profile_query(
        project_id="acme_analytics",
        dataset_id="marketing",
        table_id="google_ads",
        columns=("date", "spend"),
        partition_field="date",
        partition_start="2026-01-01",
        policy=QueryBudgetPolicy(),
        estimated_bytes=10,
    )
    assert "SELECT date, spend" in compiled.sql
    assert "LIMIT" in compiled.sql
    assert compiled.partition_predicate is not None
    with pytest.raises(ValueError, match="budget"):
        compile_profile_query(
            project_id="acme_analytics",
            dataset_id="marketing",
            table_id="google_ads",
            columns=("date",),
            partition_field="date",
            partition_start="2026-01-01",
            policy=QueryBudgetPolicy(max_bytes_scanned=1),
            estimated_bytes=99,
        )


def test_agent_sql_rejected() -> None:
    with pytest.raises(ValueError, match="not accepted"):
        reject_arbitrary_sql("SELECT * FROM marketing.google_ads")
