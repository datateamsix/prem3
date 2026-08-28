# Constraint validation and feasibility (P6-07)

Deterministic code proves a constraint set before native Meridian dispatch. Agent prose does not.

## ConstraintValidationReceipt

`validate_constraint_set` returns a metadata receipt (`ocval_` id) with checks:

- canonical refs (stable line ids / market × channel)
- units and currency
- period compatibility
- lower ≤ upper
- locked lines inside line bounds
- unsupported lines explicit
- group / reserve / total-bound feasibility

Status is `VALID`, `INVALID`, or `INFEASIBLE`. Amounts are not stored on the receipt.

## Feasibility

`assess_feasibility` / `prove_feasible` compute per-line intervals from locks, floors/ceilings, and movement limits, then test totals, reserves, market/quarter groups, and weighted funnels.

If no feasible allocation exists, dispatch is refused with `CONSTRAINT_SET_INFEASIBLE` and conflicting constraint ids when they are computable.

Infeasible sets never call `BudgetOptimizer.optimize`.

## Result post-validation

After native return, `validate_constraint_result` re-checks hard constraints. Violations → `RESULT_CONSTRAINT_VIOLATION`.

`binding_constraints[]` is emitted only from numeric evidence (`AT_LOWER` / `AT_UPPER` versus a one-cent quantum). The adapter does not invent binding labels from optimizer prose.

Flexible results do not require `sum(recommended) == fixed_budget`. They do require `B_min ≤ total ≤ B_max` when those bounds were pinned.
