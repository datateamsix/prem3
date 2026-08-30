# P6-08 completion report

Exposure-risk / delivery-health evidence on the frozen P6-07 + P6-03A integration SHA. No universal quality score. No P6-07 constraint-family or native-compile changes. Actual spend is context only.

## Required lineage block

```text
P6-06 base: e1a9477b9ce57719d56f0d522d3cb85540823362
P6-07 final committed HEAD: be554242b8b64cc702545902949044b163db6030
P6-03A final committed HEAD: eced1acf144c0d469e2c3b316f5391398c879bd8
integration branch: integration/prem3-p6-post07-actuals
integration worktree: C:/Users/zroda/Desktop/prem3-p6-post07-actuals-integration
integration cherry-picked commit(s): eced1acf → a11c54344359f880418296de475b47b330b57cee
integration conflicts/resolution: none (app/service/app.py auto-merged; both AdvancedOptimizationService and BigQueryActualSpendAdapter kept)
P6_POST07_ACTUALS_INTEGRATION_READY_HEAD: 591d9969f7459ba7757fe2ca29d70138c92d39b7
P6-08 branch: feature/prem3-p6-08-exposure-risk-delivery-health
P6-08 worktree: C:/Users/zroda/Desktop/prem3-p6-08
P6-08 base HEAD: 591d9969f7459ba7757fe2ca29d70138c92d39b7
final P6-08 committed HEAD: uncommitted working tree on that base (commit only if asked)
```

Push: not done. `uv.lock` left untracked.

## Rebase note

The existing worktree had uncommitted P6-08 files on premature base `fd37bdf` (no P6-08 commits). Those files were stashed, the branch was reset to `591d9969`, and the stash was reapplied (auto-merge of `P6_00_ARCHITECTURE_DECISIONS.md`). P6-03A, P6-07, and the integration worktree were not modified.

Ancestry on this HEAD: `e1a9477`, `be55424`, and `a11c543` are all ancestors.

## Isolation

Implemented only in `prem3-p6-08`. Did not edit `prem3-p6-07`, `prem3-p6-03a`, or `prem3-p6-post07-actuals-integration`.

## Evidence path

```text
DF + provider evidence (TEST_ONLY adapter in unit tests)
  → IG market_id / channel_id / optional campaign_id
  → ExposureMetricObservation (transient)
  → DeliveryHealthEvidence
  → PortfolioExposureRiskProfile
  → role A MODEL_INPUT | B CONSTRAINT_OR_FEASIBILITY | C SCENARIO_OR_REVIEW_GUARDRAIL
```

Production `ExposureRiskService` uses `ProductionExposureObservationAdapter` (`EXPOSURE_SOURCE_NOT_READY` without a governed DF exposure binding). `TestOnlyExposureObservationAdapter` is not installed in `app/service/app.py`.

## Metric definitions

Catalog `exposure_metric_catalog/v1` keeps metrics distinct:

`SERVED_IMPRESSIONS`, `RENDERED_IMPRESSIONS`, `MEASURABLE_IMPRESSIONS`, `VIEWABLE_IMPRESSIONS`, `HUMAN_VALID_IMPRESSIONS`, `VIEWABILITY_RATE`, `IVT_RATE`, `IN_TARGET_RATE`, `UNIQUE_REACH`, `INCREMENTAL_REACH`, `AVERAGE_FREQUENCY`, `OVER_FREQUENCY_SHARE`, `UNDER_FREQUENCY_SHARE`, `VIDEO_COMPLETION_RATE`, `ATTENTION_RATE`, `INVENTORY_QUALITY_RATE`, `COST_PER_QUALIFIED_EXPOSURE`.

Forbidden: `EXPOSURE_QUALITY_SCORE`, `DELIVERY_CONFIDENCE`. Named proxy `human_viewable_in_target_impressions/v1` only when component denominators/populations are comparable.

## Source / provider coverage

`PortfolioExposureCoverage` dimensions: portfolio spend, channel, market, campaign-provider, freshness. Provider is context, not canonical channel. Missing evidence is not zero risk or quality.

## Role qualification proof

- Role A requires `ModelConsumptionContract` reach/frequency support; otherwise `EXPOSURE_MODEL_INPUT_UNSUPPORTED`. Qualified refs attach to `FutureScenarioAssumptions.source_refs`.
- Role B requires a policy `SpendQualityRelationship`; otherwise downgrades to Role C (`SPEND_QUALITY_RELATIONSHIP_REQUIRED`, `EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED`).
- Role C may attach `EXPOSURE_RISK_FLAGS_PRESENT` on `build_change_summary`. It does not mutate Meridian response curves.

## Hard-constraint boundary

`pin_constraint_set` (client `POST .../constraint-sets`) still rejects caller-supplied `exposure_guardrails`. P6-08 `attach_qualified_exposure_guardrails()` may write already-qualified Role B IDs onto the existing placeholder. No new `ConstraintFamily` values. No compile into native `spend_constraint_*`.

## Scenario evidence

`ExposureRiskScenario` pins source rationale, scope, period, metric-definition fingerprints, and bounded example deltas (CPM +10%, viewability −8%, incremental reach −15%, IVT +3pp, audience match −10%).

## P6-03A actuals linkage

`exposure_actuals.py` joins `ActualSpendAllocation` as execution context. Amounts are not rewritten. `HIGH_SPEND_LOW_QUALITY` is descriptive only.

## P6-07 linkage

Role A → `FutureScenarioAssumptions.source_refs` / limitation `EXPOSURE_MODEL_INPUT_PINNED`.
Role B → qualified `OptimizationConstraintSet.exposure_guardrails`.
Role C → proposal limitation `EXPOSURE_RISK_FLAGS_PRESENT`.
Flexible-budget compile, feasibility, and P6-06 proposal committee states are unchanged.

## P6-09 handoff

`ExposureRiskHandoff` carries evidence refs, qualified guardrail IDs, scenario IDs, coverage fingerprint, freshness, risk flags, and portfolio entity mapping. No CVaR. No delivery-confidence scalar.

## Privacy proof

Observations are `CUSTOMER_AMOUNT_TRANSIENT`. Firestore stores refs/policies/receipts only. HTTP `Cache-Control: private, no-store`. Logs/MEL carry ids, fingerprints, flags, and counts — not rates or spend. No person identity.

## HTTP

Under `/v1/projects/{project_id}/investment-portfolio/exposure-risk`:

- `GET .../`
- `GET .../coverage`
- `GET .../channels/{channel_id}`
- `GET .../markets/{market_id}`
- `GET .../guardrails`
- `POST .../guardrails/{id}/qualify`
- `POST .../scenarios`

No raw provider-row APIs.

## OpenAPI / schema

LF-normalized SHA-256 of the working tree (`--check` green):

| Artifact | SHA-256 |
|---|---|
| `contracts/openapi.yaml` | `c07d6f8ee3501eeb88346421661a2b42ab15dc00cbce186ed6a49a46b0b171de` |
| `contracts/schema/planning.schema.json` | `3a47d78a2c8e0443c8cbbf4b909611eaf06978d78845200c6d178196f01eb2a6` |
| `contracts/schema/api.schema.json` | `8f7d98f9724edc42a9dd829728337023102e69a3e4038130ce8e5191b5329628` |
| `contracts/schema/manifest.json` | `c73944d7992fedd5fd5c0ebeb679e6cae0901b9a827799f52b975aa33bce956b` |

Public planning roots added: `DeliveryHealthEvidence`, `PortfolioExposureCoverage`, `ExposureGuardrailQualificationReceipt`, `ExposureRiskHandoff`.

## Tests

Required names plus Role A/B/C wiring:

- `tests/unit/investment_planning/test_p6_08_metrics.py` (5)
- `tests/unit/investment_planning/test_p6_08_identity.py` (5)
- `tests/unit/investment_planning/test_p6_08_roles.py` (7)
- `tests/unit/investment_planning/test_p6_08_actuals.py` (3)
- `tests/unit/investment_planning/test_p6_08_privacy.py` (6)

**26 P6-08 tests.** Combined planning / optimization / DF / IG / OpenAPI / project-architecture suite: **483 collected, exit 0** (3 skipped, remainder passed). P6-03A `test_p6_03a_production_bq_actuals.py` (26) and P6-07 `test_p6_07_*.py` remain green.

```text
uv run --extra dev python -m pytest tests/unit/investment_planning tests/unit/investment_optimization tests/unit/data_foundation tests/unit/identity_graph tests/unit/test_prem3_api_openapi.py tests/unit/test_project_architecture.py
uv run --extra dev python scripts/export_openapi.py --check
uv run --extra dev python scripts/export_contracts.py --check
```

Ruff green on P6-08-owned paths. Pre-existing P6-01 `firestore.py` / `validator.py` / `markets.py` findings were not rewritten.

## Docs / ADRs

- [EXPOSURE_RISK_EVIDENCE.md](EXPOSURE_RISK_EVIDENCE.md)
- [DELIVERY_HEALTH_METRICS.md](DELIVERY_HEALTH_METRICS.md)
- [EXPOSURE_GUARDRAIL_QUALIFICATION.md](EXPOSURE_GUARDRAIL_QUALIFICATION.md)
- [EXPOSURE_RISK_SCENARIOS.md](EXPOSURE_RISK_SCENARIOS.md)
- ADR-P6-070 … ADR-P6-077 in [P6_00_ARCHITECTURE_DECISIONS.md](P6_00_ARCHITECTURE_DECISIONS.md) (titles match the P6-08 spec)

## Blockers

Live GCP exposure warehouse is not a closeout gate. CVaR / P6-09 frontier math is out of scope. Person identity is out of scope. P6-07 constraint families and P6-03A SQL/fiscal mapping are unchanged. P6-08 is uncommitted pending an explicit commit request.
