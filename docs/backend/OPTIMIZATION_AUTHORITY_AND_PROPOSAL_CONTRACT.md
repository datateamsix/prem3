# Optimization authority and proposal contract

Accepted MMM is the primary causal response engine for optimization.

MTA is supporting attribution/tactical evidence. MTA weights must not be substituted for MMM response curves.

Optimization creates an immutable `OptimizationProposalRef`. It does not mutate the active Investment Plan. Human approval of `RECOMMENDED` authorizes a **new** governed Drive plan version (P6-06). It does not overwrite the baseline in place.

Solver kinds:

- `MERIDIAN_NATIVE_FIXED_BUDGET` — prove first (P6-05)
- `MERIDIAN_NATIVE_FLEXIBLE_BUDGET` — later
- `PREM3_RISK_AWARE_FRONTIER` — CVaR / risk-aware extension (P6-09), separately labeled

Reach, frequency, and exposure-integrity evidence remain separately governed. They may be model inputs, constraints, or scenario/approval guardrails only when methodologically supported. They are not a universal score.

`UnimplementedMeridianBudgetOptimizerAdapter` freezes the seam. P6-00 does not invoke Meridian.
