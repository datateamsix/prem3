"""One-shot live BQ repair/probe for M5-01A."""

from __future__ import annotations

from app.modeling.mta.bq_executor import client_for_project, run_query

PROJECT = "modelready-m3"


def main() -> None:
    client = client_for_project(PROJECT)
    client.delete_table(f"{PROJECT}.prem3_modeling.mta_journeys", not_found_ok=True)
    print("dropped mta_journeys if present")
    sql = f"""
    SELECT
      `{PROJECT}.prem3_modeling.channel_grouping_v1`('chatgpt.com','referral','x') AS chatgpt,
      `{PROJECT}.prem3_modeling.channel_grouping_v1`('perplexity.ai','referral',NULL) AS perplexity,
      `{PROJECT}.prem3_modeling.channel_grouping_v1`('gemini.google.com','referral','g') AS gemini
    """
    result = run_query(client, sql, fetch=True)
    print(result.rows)


if __name__ == "__main__":
    main()
