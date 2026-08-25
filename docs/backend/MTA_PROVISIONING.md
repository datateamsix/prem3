# MTA Provisioning

MTA BigQuery assets are provisioned via a fingerprinted `MTAProvisioningPlan`, approved, then executed — same approve→execute pattern as Data Foundation (separate plan type; do not overload `FoundationPlan`).

## Plan contents

- Channel-grouping UDF DDL from `sql/mta/udf/`
- Operational + run-output DDL from `sql/mta/ddl/`
- Preview of MERGE/rebuild DML and scheduled-query templates
- Fingerprints of rendered SQL

## Approval

UDF versions and scheduled refresh require explicit approval. DDL inside the bound `prem3_modeling` dataset may auto-execute when marked safe in `sql/mta/manifest.yaml`.

## Authority

Destination GCP project and dataset are server-owned. Agents receive plan IDs and SQL previews — not raw SQL execution authority.

See also `MTA_BIGQUERY_ASSET_LIBRARY.md` and `MTA_MANAGED_REFRESH.md`.
