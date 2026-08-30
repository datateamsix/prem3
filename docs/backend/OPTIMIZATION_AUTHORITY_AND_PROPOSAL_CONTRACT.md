# Optimization authority and proposal contract

Accepted MMM is the primary causal response engine for optimization.

MTA is supporting attribution/tactical evidence. MTA weights must not be substituted for MMM response curves.

Optimization creates an immutable `ScenarioArtifact` and a committee `OptimizationProposal`. It does not mutate the active Investment Plan. Human approval of a P6-06 `APPROVED` proposal authorizes a **new** governed Drive plan **draft** via P6-01 `revise` + ingest. Plan approval remains a separate act. It does not overwrite the baseline in place.

Solver kinds:

- `MERIDIAN_NATIVE_FIXED_BUDGET` — prove first (P6-05)
- `MERIDIAN_NATIVE_FLEXIBLE_BUDGET` — later
- `PREM3_RISK_AWARE_FRONTIER` — CVaR / risk-aware extension (P6-09), separately labeled

Reach, frequency, and exposure-integrity evidence remain separately governed. They may be model inputs, constraints, or scenario/approval guardrails only when methodologically supported. They are not a universal score.

`UnimplementedMeridianBudgetOptimizerAdapter` remains the P6-00 flexible/CVaR seam. P6-05 adds `NativeMeridianFixedBudgetAdapter` for `BudgetOptimizer.optimize(fixed_budget=True)`. Recommended amounts are `MODEL_RECOMMENDED` on an immutable GCS artifact and a private result endpoint. They do not mutate Drive and are not proposal approval.
